#!/usr/bin/env python3
"""Reindex a Lean project's MathProver graph (bootstrap/build + run backfill)."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

HOME = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "project",
        nargs="?",
        default=os.environ.get("MATHPROVER_PROJECT_PATH", "."),
        help="Lean project root (lakefile.lean + mathprover.toml)",
    )
    ap.add_argument(
        "--decorators",
        action="store_true",
        help="Use build_graph.py instead of the project's bootstrap_graph.py",
    )
    args = ap.parse_args()

    root = Path(args.project).expanduser().resolve()
    if not (root / "lakefile.lean").is_file():
        print(f"error: not a Lean project: {root}", file=sys.stderr)
        return 2

    project_script = root / "scripts" / "reindex_graph.py"
    if project_script.is_file() and not args.decorators:
        env = {**os.environ, "MATHPROVER_HOME": str(HOME)}
        return subprocess.run([sys.executable, str(project_script)], cwd=root, env=env).returncode

    steps: list[list[str]] = []
    bootstrap = root / "scripts" / "bootstrap_graph.py"
    build = HOME / "scripts" / "build_graph.py"
    index = HOME / "scripts" / "index_runs.py"

    if args.decorators:
        steps.append([sys.executable, str(build), "--root", str(root), "--strict"])
    elif bootstrap.is_file():
        steps.append([sys.executable, str(bootstrap)])
    else:
        steps.append([sys.executable, str(build), "--root", str(root)])

    steps.append([sys.executable, str(index), "--root", str(root), "--backfill"])

    env = {**os.environ, "MATHPROVER_HOME": str(HOME)}
    for cmd in steps:
        proc = subprocess.run(cmd, cwd=HOME if cmd[1].startswith(str(HOME)) else root, env=env)
        if proc.returncode != 0:
            return proc.returncode

    graph_proc = subprocess.run(
        [sys.executable, str(index), "--root", str(root), "--graph"],
        cwd=HOME,
        env=env,
        capture_output=True,
        text=True,
    )
    if graph_proc.returncode != 0:
        print(graph_proc.stderr or graph_proc.stdout, file=sys.stderr)
        return graph_proc.returncode

    out = root / ".mathprover" / "graph.json"
    if graph_proc.stdout.strip():
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(graph_proc.stdout.strip() + "\n", encoding="utf-8")
    print(f"[reindex_project] updated {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
