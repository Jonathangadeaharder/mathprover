#!/usr/bin/env python3
"""Batch-dispatch MathProver proof folders.

This replaces the old one-off `mathrover.py`/`solve_all.py` experiment that
lived in Lean projects. It keeps the valuable behavior — retry a list of goals
until they are closed — but routes every attempt through MathProver's real
dispatch, logging, rate limits, and final verification gates.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _has_forbidden_placeholder(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    return any(token in text for token in ("sorry", "admit", "exact?", "sorryAx"))


def _attempt_file(project_root: Path, folder: str) -> Path:
    return project_root / "proofs" / folder / "attempt.lean"


def dispatch_once(project_root: Path, folder: str, prover: str) -> subprocess.CompletedProcess[str]:
    cmd = [
        sys.executable,
        str(Path(__file__).resolve().parent / "dispatch.py"),
        "--root",
        str(project_root),
        "--node",
        folder,
        "--prover",
        prover,
    ]
    return subprocess.run(
        cmd,
        cwd=Path(__file__).resolve().parent,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch-dispatch MathProver proof folders.")
    parser.add_argument("--project-root", required=True, help="Lean project root")
    parser.add_argument("--node", action="append", default=[], help="proofs/<folder> to dispatch")
    parser.add_argument("--node-file", default=None, help="newline-delimited list of proof folders")
    parser.add_argument(
        "--prover", default="auto", choices=["auto", "oprover", "qwen", "aristotle"]
    )
    parser.add_argument("--max-rounds", type=int, default=1)
    parser.add_argument("--stop-on-fail", action="store_true")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    nodes = list(args.node)
    if args.node_file:
        nodes.extend(
            line.strip()
            for line in Path(args.node_file).read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
    if not nodes:
        raise SystemExit("provide at least one --node or --node-file")

    failed: list[str] = []
    for folder in nodes:
        attempt = _attempt_file(project_root, folder)
        if not attempt.exists():
            print(f"{folder}: missing {attempt}", flush=True)
            failed.append(folder)
            if args.stop_on_fail:
                break
            continue

        for round_idx in range(1, args.max_rounds + 1):
            if not _has_forbidden_placeholder(attempt):
                print(f"{folder}: already closed", flush=True)
                break
            print(f"{folder}: round {round_idx}/{args.max_rounds} via {args.prover}", flush=True)
            proc = dispatch_once(project_root, folder, args.prover)
            print(proc.stdout, end="" if proc.stdout.endswith("\n") else "\n")
            if proc.returncode == 0 and not _has_forbidden_placeholder(attempt):
                print(f"{folder}: proved", flush=True)
                break
        else:
            if _has_forbidden_placeholder(attempt):
                failed.append(folder)
                if args.stop_on_fail:
                    break

    if failed:
        print("failed: " + ", ".join(failed), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
