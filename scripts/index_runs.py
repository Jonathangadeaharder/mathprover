#!/usr/bin/env python3
"""Index dispatch logs into .mathprover/runs/ and node attemptsLog metadata."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

MATHPROVER_HOME = Path(
    os.environ.get("MATHPROVER_HOME", Path(__file__).resolve().parents[1])
).resolve()
AGENTS = MATHPROVER_HOME / "agents"
if str(AGENTS) not in sys.path:
    sys.path.insert(0, str(AGENTS))

from run_registry import (  # noqa: E402
    RunRecord,
    list_runs,
    read_run,
    resolve_node_id,
    runs_dir,
    write_run,
)

STATUS_LINE = re.compile(r"^state:\s*(\S+)", re.MULTILINE)
DISPATCH_LINE = re.compile(
    r"^\-\s+\[([^\]]+)\]\s+(\w+):\s+(ok|failed)\s+—\s+log\s+`([^`]+)`",
    re.MULTILINE,
)
RUN_ID_FROM_LOG = re.compile(r"(\d{8}T\d{6}Z)\.log$")


def parse_status_md(path: Path) -> str | None:
    if not path.exists():
        return None
    m = STATUS_LINE.search(path.read_text(encoding="utf-8"))
    return m.group(1) if m else None


def infer_proof_folder(project_root: Path, theorem: str, node_id: str) -> str | None:
    proofs = project_root / "proofs"
    if not proofs.is_dir():
        return None
    for folder in proofs.iterdir():
        if not folder.is_dir():
            continue
        if theorem and theorem in folder.name:
            return folder.name
        if node_id in folder.name:
            return folder.name
    return None


def attach_proof_folders(project_root: Path, nodes: list[dict]) -> None:
    for node in nodes:
        if node.get("proof_folder"):
            continue
        folder = infer_proof_folder(project_root, node.get("lean_theorem", ""), node.get("id", ""))
        if folder:
            node["proof_folder"] = folder
        status_path = project_root / "proofs" / folder / "status.md" if folder else None
        if status_path and status_path.exists():
            ws = parse_status_md(status_path)
            if ws:
                node["worker_state"] = ws


def log_run_id(log_path: Path) -> str:
    m = RUN_ID_FROM_LOG.search(log_path.name)
    if m:
        return m.group(1)
    return log_path.stem


def backfill_run_from_log(project_root: Path, log_path: Path, proof_folder: str) -> RunRecord | None:
    run_id = log_run_id(log_path)
    existing = read_run(project_root, run_id)
    if existing:
        return existing

    text = log_path.read_text(encoding="utf-8", errors="replace")
    theorem = proof_folder.split("_", 2)[-1] if "_" in proof_folder else proof_folder
    node_id = resolve_node_id(project_root, proof_folder, theorem)

    prover = "goedel"
    if "aristotle" in text.lower():
        prover = "aristotle"

    ok = "compile: ok" in text or '"success": true' in text
    failed = "pipeline exhausted" in text or (text and "error:" in text[:500])
    lock_path = project_root / ".mathprover" / "locks" / "goedel.lock"
    lock_active = lock_path.exists()
    if not text.strip() and lock_active:
        status = "running"
    elif ok:
        status = "ok"
    elif failed or log_path.stat().st_size > 0:
        status = "failed"
    else:
        status = "failed"

    mtime = datetime.fromtimestamp(log_path.stat().st_mtime, tz=timezone.utc)
    started = datetime.fromtimestamp(log_path.stat().st_ctime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ended = mtime.strftime("%Y-%m-%dT%H:%M:%SZ")

    record = RunRecord(
        id=run_id,
        node_id=node_id,
        proof_folder=proof_folder,
        prover=prover,
        route_reason="backfill",
        status=status,
        started_at=started,
        ended_at=ended,
        log_path=log_path.relative_to(project_root).as_posix(),
        result="PROVEN" if ok else "FAILED",
        verify_ok=ok,
        message="backfilled from log",
    )
    write_run(project_root, record)
    return record


def backfill_all(project_root: Path) -> list[RunRecord]:
    attempts = project_root / ".mathprover" / "attempts"
    created: list[RunRecord] = []
    if not attempts.is_dir():
        return created
    for folder_dir in sorted(attempts.iterdir()):
        if not folder_dir.is_dir():
            continue
        for log_path in sorted(folder_dir.glob("*.log")):
            rec = backfill_run_from_log(project_root, log_path, folder_dir.name)
            if rec:
                created.append(rec)
    return created


def run_to_attempt(run: RunRecord) -> dict:
    started = run.started_at.replace("T", " ").replace("Z", " UTC")
    ended = (run.ended_at or run.started_at).replace("T", " ").replace("Z", " UTC")
    result = run.result or ("PROVEN" if run.status == "ok" else "FAILED" if run.status == "failed" else "PROGRESS")
    return {
        "id": run.id,
        "agent": run.prover,
        "started": started,
        "ended": ended,
        "duration": "—",
        "tokens": 0,
        "cost": 0.0,
        "strategy": run.route_reason,
        "result": result,
        "why": run.message or "",
        "logPath": run.log_path,
    }


def merge_attempts_into_graph(project_root: Path, graph: dict) -> dict:
    runs = list_runs(project_root)
    by_node: dict[str, list[dict]] = {}
    for run in runs:
        if run.status not in {"ok", "failed", "error"}:
            continue
        by_node.setdefault(run.node_id, []).append(run_to_attempt(run))

    for node in graph.get("nodes", []):
        nid = node.get("id", "")
        attempts = by_node.get(nid, [])
        if attempts:
            node["attemptsLog"] = sorted(attempts, key=lambda a: a["started"], reverse=True)
            node["attempts"] = len(attempts)
        attach_proof_folders(project_root, [node])

    active = next((r for r in runs if r.status in {"pending", "running"}), None)
    if active:
        graph["activeAgent"] = {
            "node": active.node_id,
            "agent": active.prover,
            "started": active.started_at,
            "step": 0,
            "totalSteps": 4,
            "runId": active.id,
            "log": [],
        }
    elif graph.get("activeAgent") and not active:
        pass  # keep existing unless stale — cleared by dispatch end

    return graph


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".", help="Project root")
    ap.add_argument("--backfill", action="store_true", help="Create run records from attempt logs")
    ap.add_argument("--graph", action="store_true", help="Print enriched graph JSON to stdout")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if args.backfill:
        created = backfill_all(root)
        print(f"[index_runs] backfilled {len(created)} runs", file=sys.stderr)

    if args.graph:
        graph_path = root / ".mathprover" / "graph.json"
        if not graph_path.exists():
            print("{}", end="")
            return 0
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        attach_proof_folders(root, graph.get("nodes", []))
        graph = merge_attempts_into_graph(root, graph)
        print(json.dumps(graph, ensure_ascii=False))
        return 0

    runs = list_runs(root)
    print(f"[index_runs] {len(runs)} run records in {runs_dir(root)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
