#!/usr/bin/env python3
"""Re-attach to an already-submitted Aristotle task and monitor / retrieve it.

The dispatch backend creates a fresh project per run and stops polling at its client-side
`max_wait_minutes` cap — but the *cloud task keeps running*. This tool re-attaches by project/task
id (`Project.from_id`), so a long run is never lost when the local poller exits.

Modes:
  --status                 print current status and exit (non-destructive; default)
  --wait                   poll to completion (no artificial timeout), then download + verify
With --wait, the downloaded proof is written to the node's attempt.lean ONLY if it passes the
gate: no forbidden placeholders, compiles, and (best-effort) axiom-clean.

Usage:
  cd agents && uv run python aristotle_attach.py --project-id <PID> [--task-id <TID>] \
      --node <FOLDER> --project-root ~/projects/lean-runtime-analysis [--wait]

`uv run` is required: aristotlelib lives in the agents venv, not in the ambient interpreter.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

AGENTS = Path(__file__).resolve().parent
if str(AGENTS) not in sys.path:
    sys.path.insert(0, str(AGENTS))

from lean_pipeline import (  # noqa: E402
    compile_lean_file,
    extract_tarball,
    find_attempt_lean,
    forbidden_placeholders,
)


async def _amain(args: argparse.Namespace) -> int:
    from aristotlelib.agent_task import TaskStatus
    from aristotlelib.project import Project

    project = Project.from_id(args.project_id)
    if asyncio.iscoroutine(project):
        project = await project
    await project.refresh()
    tasks, _ = await project.get_tasks(limit=10)
    task = None
    if args.task_id:
        task = next((t for t in tasks if t.agent_task_id == args.task_id), None)
    task = task or (tasks[0] if tasks else None)
    if task is None:
        print("no task found on project")
        return 2
    print(f"project={args.project_id} status={getattr(project, 'status', '?')}")
    print(f"task={task.agent_task_id} status={task.status.name}")

    if not args.wait:
        return 0

    await task.wait_for_completion(num_events=0, poll_interval_seconds=args.poll)
    await project.refresh()
    print(f"final_status={task.status.name}")
    if getattr(task, "output_summary", None):
        print(f"summary:\n{task.output_summary}")
    if task.status not in (TaskStatus.COMPLETE, TaskStatus.COMPLETE_WITH_ERRORS):
        print(f"task ended with {task.status.name}; nothing to download")
        return 1

    root = Path(args.project_root).resolve()
    dest = root / ".mathprover" / "attempts" / args.node / "aristotle_attach"
    dest.mkdir(parents=True, exist_ok=True)
    archive = await project.get_files(destination=dest / f"{args.project_id}.tar.gz")
    extract_root = dest / "extracted"
    extract_tarball(archive, extract_root)

    node_attempt = root / "proofs" / args.node / "attempt.lean"
    rel_hint = node_attempt.relative_to(root).as_posix()
    found = find_attempt_lean(extract_root, rel_hint=rel_hint)
    if found is None:
        print("download did not contain attempt.lean")
        return 1
    candidate = found.read_text(encoding="utf-8")
    forbidden = forbidden_placeholders(candidate)
    if forbidden:
        print(f"REJECTED — forbidden placeholders in returned proof: {', '.join(forbidden)}")
        print(f"(downloaded proof left at {found}, NOT written to {node_attempt})")
        return 1
    # Verify in a scratch copy first; only overwrite the node on success.
    scratch = dest / "verify.lean"
    scratch.write_text(candidate, encoding="utf-8")
    r = compile_lean_file(project_root=root, lean_file=scratch)
    if not r.ok:
        print("REJECTED — returned proof does not compile locally")
        print(r.error_excerpt(800))
        return 1
    node_attempt.write_text(candidate, encoding="utf-8")
    print(f"VERIFIED + written to {node_attempt}")
    print(
        "NEXT: confirm #print axioms = [propext, Classical.choice, Quot.sound] and statement unchanged"
    )
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project-id", required=True)
    ap.add_argument("--task-id", default=None)
    ap.add_argument(
        "--node", default=None, help="proofs/<FOLDER> for writeback+verify (with --wait)"
    )
    ap.add_argument(
        "--project-root", default=str(Path.home() / "projects" / "lean-runtime-analysis")
    )
    ap.add_argument("--wait", action="store_true", help="poll to completion, then download+verify")
    ap.add_argument("--poll", type=int, default=30, help="poll interval seconds")
    args = ap.parse_args()
    if args.wait and not args.node:
        ap.error("--wait requires --node (to locate attempt.lean for writeback+verify)")
    raise SystemExit(asyncio.run(_amain(args)))


if __name__ == "__main__":
    main()
