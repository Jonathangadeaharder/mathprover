"""Runtime run index under .mathprover/runs/ — shared by dispatch and the UI."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def runs_dir(project_root: Path) -> Path:
    return project_root / ".mathprover" / "runs"


@dataclass
class RunRecord:
    id: str
    node_id: str
    proof_folder: str
    prover: str
    route_reason: str
    status: str  # pending | running | ok | failed | error
    started_at: str
    log_path: str
    ended_at: str | None = None
    result: str | None = None  # PROVEN | FAILED | PROGRESS
    verify_ok: bool | None = None
    message: str | None = None
    pid: int | None = None
    phase: str | None = None
    detail: str | None = None
    tokens_generated: int | None = None
    tokens_per_sec: float | None = None
    heartbeat_at: str | None = None
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunRecord:
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


def run_path(project_root: Path, run_id: str) -> Path:
    return runs_dir(project_root) / f"{run_id}.json"


def write_run(project_root: Path, record: RunRecord) -> None:
    path = run_path(project_root, record.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record.to_dict(), indent=2) + "\n", encoding="utf-8")


def read_run(project_root: Path, run_id: str) -> RunRecord | None:
    path = run_path(project_root, run_id)
    if not path.exists():
        return None
    return RunRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))


def list_runs(project_root: Path) -> list[RunRecord]:
    root = runs_dir(project_root)
    if not root.is_dir():
        return []
    runs: list[RunRecord] = []
    for path in sorted(root.glob("*.json")):
        try:
            runs.append(RunRecord.from_dict(json.loads(path.read_text(encoding="utf-8"))))
        except (json.JSONDecodeError, TypeError):
            continue
    runs.sort(key=lambda r: r.started_at, reverse=True)
    return runs


def active_run(project_root: Path) -> RunRecord | None:
    for run in list_runs(project_root):
        if run.status in {"pending", "running"}:
            return run
    return None


def set_graph_active_agent(project_root: Path, *, run: RunRecord | None) -> None:
    graph_path = project_root / ".mathprover" / "graph.json"
    if not graph_path.exists():
        return
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    if run is None:
        graph["activeAgent"] = None
    else:
        graph["activeAgent"] = {
            "node": run.node_id,
            "agent": run.prover,
            "started": run.started_at,
            "step": 0,
            "totalSteps": 4,
            "runId": run.id,
            "log": [],
        }
    graph_path.write_text(json.dumps(graph, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def update_run_progress(
    project_root: Path,
    run_id: str,
    *,
    phase: str,
    detail: str = "",
    tokens_generated: int | None = None,
    tokens_per_sec: float | None = None,
) -> None:
    record = read_run(project_root, run_id)
    if record is None:
        return
    record.phase = phase
    record.detail = detail
    record.heartbeat_at = utc_now()
    if tokens_generated is not None:
        record.tokens_generated = tokens_generated
    if tokens_per_sec is not None:
        record.tokens_per_sec = round(tokens_per_sec, 2)
    write_run(project_root, record)
    # Keep graph activeAgent in sync for UI polling.
    if record.status in {"pending", "running"}:
        graph_path = project_root / ".mathprover" / "graph.json"
        if not graph_path.exists():
            return
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        agent = graph.get("activeAgent") or {}
        if agent.get("runId") == run_id:
            agent["step"] = _phase_step(phase)
            agent["phase"] = phase
            agent["detail"] = detail
            agent["tokensGenerated"] = tokens_generated
            agent["tokensPerSec"] = tokens_per_sec
            agent["heartbeatAt"] = record.heartbeat_at
            graph["activeAgent"] = agent
            graph_path.write_text(json.dumps(graph, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _phase_step(phase: str) -> int:
    mapping = {
        "loading_model": 0,
        "generating": 1,
        "compiling": 2,
        "correcting": 3,
        "verifying": 4,
        "done": 4,
    }
    return mapping.get(phase, 1)


def resolve_node_id(project_root: Path, folder: str, theorem: str) -> str:
    graph_path = project_root / ".mathprover" / "graph.json"
    if graph_path.exists():
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        for entry in graph.get("nodes", []):
            if entry.get("proof_folder") == folder:
                return entry.get("id", folder)
            node_id = entry.get("id", "")
            lean = entry.get("lean_theorem", "")
            if lean and lean in folder:
                return node_id
            if node_id in folder or folder.endswith(node_id):
                return node_id
    return folder
