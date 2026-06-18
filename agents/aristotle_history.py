#!/usr/bin/env python3
"""Aristotle event stream analyzer — pull and parse event history from past projects.

Aristotle (by Harmonic) is the cloud theorem prover. Its CLI exposes:
  aristotle list [--status RUNNING|IDLE] [--limit N]
  aristotle show <project_id>
  aristotle tasks <project_id>
  aristotle download <project_id> [--destination <path>]

Event types observed in the feed: PROVING, THINKING, RUNNING_COMMAND, EDITING_FILE, REVIEWING.
This module parses those events into a structured format compatible with the trajectory schema.

Usage:
  python3 agents/aristotle_history.py --list               # list all projects
  python3 agents/aristotle_history.py --pull <project_id>  # pull + parse events
  python3 agents/aristotle_history.py --pull-all            # pull all completed projects
  python3 agents/aristotle_history.py --export              # export all to JSONL
  python3 agents/aristotle_history.py --summary             # summary of all known projects
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _aristotle_cli(*args: str, timeout: int = 60) -> str:
    """Run an aristotle CLI command, return stdout."""
    cmd = ["aristotle", *args]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "ARISTOTLE_API_KEY": os.environ.get("ARISTOTLE_API_KEY", "")},
        )
        return result.stdout
    except FileNotFoundError:
        print("ERROR: `aristotle` CLI not found. Install with: uv tool install aristotlelib",
              file=sys.stderr)
        raise SystemExit(1)
    except subprocess.TimeoutExpired:
        print(f"ERROR: aristotle {' '.join(args)} timed out after {timeout}s", file=sys.stderr)
        return ""


# ---------- structured event types ----------

@dataclass
class AristotleEvent:
    """One event from the Aristotle cloud prover event stream."""
    ts: str
    event_type: str          # PROVING | THINKING | RUNNING_COMMAND | EDITING_FILE | REVIEWING | UNKNOWN
    content: str             # raw event text
    project_id: str = ""
    task_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AristotleProjectSummary:
    """Summary of one Aristotle project."""
    project_id: str
    status: str              # RUNNING | IDLE | UNKNOWN
    name: str = ""
    task_count: int = 0
    event_count: int = 0
    proving_pct: float = 0.0  # fraction of events that are PROVING
    events: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------- parsing ----------

_EVENT_TYPE_RE = re.compile(
    r"\b(PROVING|THINKING|RUNNING_COMMAND|EDITING_FILE|REVIEWING)\b"
)


def parse_event_stream(raw: str, project_id: str = "") -> list[AristotleEvent]:
    """Parse the text output of `aristotle show <id>` into structured events.

    The aristotle CLI output format is semi-structured text. We extract:
    - Event type (PROVING, THINKING, etc.)
    - Timestamp if present
    - Content text
    """
    events: list[AristotleEvent] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _EVENT_TYPE_RE.search(line)
        event_type = m.group(1) if m else "UNKNOWN"
        # Skip boring lines (headers, separators, etc.)
        if event_type == "UNKNOWN" and len(line) < 20:
            continue
        events.append(AristotleEvent(
            ts=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            event_type=event_type,
            content=line[:2000],
            project_id=project_id,
        ))
    return events


def list_projects(*, status: str = "", limit: int = 100) -> list[dict[str, str]]:
    """List Aristotle projects via CLI. Returns list of {id, status, name} dicts."""
    args = ["list", "--limit", str(limit)]
    if status:
        args += ["--status", status]
    raw = _aristotle_cli(*args)
    projects: list[dict[str, str]] = []
    # Parse project list output (format varies; best-effort extraction)
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith(("Usage", "Error", "No projects")):
            continue
        # Try to extract project ID (typically a UUID or short hash)
        # Aristotle list output format: lines with project_id and status
        parts = line.split()
        if len(parts) >= 2:
            projects.append({
                "id": parts[0],
                "status": parts[1] if len(parts) > 1 else "UNKNOWN",
                "name": " ".join(parts[2:]) if len(parts) > 2 else "",
            })
    return projects


def pull_project(project_id: str, *, event_limit: int = 200) -> AristotleProjectSummary:
    """Pull events for one Aristotle project and return a structured summary."""
    raw = _aristotle_cli("show", project_id, "--limit", str(event_limit))
    events = parse_event_stream(raw, project_id=project_id)

    # Compute event-type distribution
    by_type: dict[str, int] = {}
    for e in events:
        by_type[e.event_type] = by_type.get(e.event_type, 0) + 1
    total = len(events) or 1
    proving_pct = by_type.get("PROVING", 0) / total * 100

    return AristotleProjectSummary(
        project_id=project_id,
        status="IDLE" if events else "UNKNOWN",
        event_count=len(events),
        proving_pct=round(proving_pct, 1),
        events=[e.to_dict() for e in events],
    )


def pull_all_projects(*, limit: int = 50, event_limit: int = 200) -> list[AristotleProjectSummary]:
    """Pull events for all known Aristotle projects."""
    projects = list_projects(limit=limit)
    summaries: list[AristotleProjectSummary] = []
    for p in projects:
        pid = p["id"]
        print(f"Pulling {pid}...", file=sys.stderr)
        try:
            s = pull_project(pid, event_limit=event_limit)
            s.status = p.get("status", s.status)
            s.name = p.get("name", s.name)
            summaries.append(s)
        except Exception as exc:
            print(f"  ERROR pulling {pid}: {exc}", file=sys.stderr)
            summaries.append(AristotleProjectSummary(
                project_id=pid, status=p.get("status", "ERROR"),
            ))
    return summaries


# ---------- storage ----------

def _history_dir(project_root: Path | None = None) -> Path:
    if project_root:
        return project_root / ".mathprover" / "aristotle_history"
    configured = os.environ.get("MATHPROVER_PROJECT_PATH")
    if configured:
        return Path(configured).expanduser() / ".mathprover" / "aristotle_history"
    return Path.home() / ".mathprover" / "aristotle_history"


def save_project_history(
    summary: AristotleProjectSummary,
    project_root: Path | None = None,
) -> Path:
    """Save a project's event history to JSON."""
    d = _history_dir(project_root)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{summary.project_id}.json"
    path.write_text(json.dumps(summary.to_dict(), indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return path


def load_project_history(
    project_id: str,
    project_root: Path | None = None,
) -> AristotleProjectSummary | None:
    """Load a previously saved project history."""
    path = _history_dir(project_root) / f"{project_id}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return AristotleProjectSummary(
        project_id=data["project_id"],
        status=data.get("status", "UNKNOWN"),
        name=data.get("name", ""),
        event_count=data.get("event_count", 0),
        proving_pct=data.get("proving_pct", 0.0),
        events=data.get("events", []),
    )


def list_saved_histories(project_root: Path | None = None) -> list[Path]:
    d = _history_dir(project_root)
    if not d.is_dir():
        return []
    return sorted(d.glob("*.json"))


# ---------- export to trajectory-compatible JSONL ----------

def export_to_trajectory_jsonl(
    summaries: list[AristotleProjectSummary],
    output_path: Path | None = None,
) -> str:
    """Export Aristotle event histories as trajectory-compatible JSONL rows.

    Each event becomes one row with event="aristotle_step" so it can be
    queried alongside proving_step rows from trajectory.py.
    """
    rows: list[dict[str, Any]] = []
    for s in summaries:
        for ev in s.events:
            rows.append({
                "ts": ev.get("ts", ""),
                "event": "aristotle_step",
                "run_id": s.project_id,
                "node_id": "",
                "prover": "aristotle",
                "round": 0,
                "branch": -1,
                "phase": "aristotle",
                "prompt": {},
                "model_output": "",
                "candidate": None,
                "compile_ok": None,
                "compile_feedback": None,
                "gate": ev.get("event_type", "UNKNOWN").lower(),
                "prompt_tokens": None,
                "completion_tokens": None,
                "latency_s": None,
                "temperature": None,
                "max_tokens": None,
                "metadata": {
                    "project_id": s.project_id,
                    "project_status": s.status,
                    "event_content": ev.get("content", "")[:1000],
                    "proving_pct": s.proving_pct,
                },
            })
    output = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n"
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
    return output


# ---------- CLI ----------

def main() -> None:
    ap = argparse.ArgumentParser(description="Aristotle event stream analyzer")
    ap.add_argument("--root", default=None, help="Lean project root (for storage)")
    ap.add_argument("--list", action="store_true", help="List all Aristotle projects")
    ap.add_argument("--pull", metavar="PROJECT_ID", help="Pull events for one project")
    ap.add_argument("--pull-all", action="store_true", help="Pull events for all projects")
    ap.add_argument("--export", action="store_true", help="Export saved histories to trajectory JSONL")
    ap.add_argument("--summary", action="store_true", help="Summary of saved histories")
    ap.add_argument("--output", default=None, help="Output path (for --export)")
    ap.add_argument("--event-limit", type=int, default=200, help="Max events per project (default: 200)")
    args = ap.parse_args()

    root = Path(args.root).resolve() if args.root else None

    if args.list:
        projects = list_projects()
        if not projects:
            print("No Aristotle projects found.")
        for p in projects:
            print(f"  {p['id']}  {p['status']}  {p['name']}")
        return

    if args.pull:
        s = pull_project(args.pull, event_limit=args.event_limit)
        path = save_project_history(s, project_root=root)
        print(f"Pulled {s.event_count} events for {s.project_id} -> {path}")
        print(f"  Proving: {s.proving_pct}%  Events by type: "
              + ", ".join(f"{k}={sum(1 for e in s.events if e.get('event_type') == k)}"
                          for k in ("PROVING", "THINKING", "RUNNING_COMMAND", "EDITING_FILE", "REVIEWING")))
        return

    if args.pull_all:
        summaries = pull_all_projects(event_limit=args.event_limit)
        for s in summaries:
            path = save_project_history(s, project_root=root)
            print(f"  {s.project_id}: {s.event_count} events, {s.proving_pct}% proving -> {path}")
        return

    if args.export:
        histories = list_saved_histories(project_root=root)
        summaries: list[AristotleProjectSummary] = []
        for h in histories:
            data = json.loads(h.read_text(encoding="utf-8"))
            summaries.append(AristotleProjectSummary(
                project_id=data["project_id"],
                status=data.get("status", "UNKNOWN"),
                name=data.get("name", ""),
                event_count=data.get("event_count", 0),
                proving_pct=data.get("proving_pct", 0.0),
                events=data.get("events", []),
            ))
        output_path = Path(args.output) if args.output else None
        out = export_to_trajectory_jsonl(summaries, output_path=output_path)
        if not output_path:
            print(out)
        else:
            print(f"Exported {len(summaries)} projects to {output_path}", file=sys.stderr)
        return

    if args.summary:
        histories = list_saved_histories(project_root=root)
        if not histories:
            print("No saved Aristotle histories. Run --pull or --pull-all first.")
            return
        total_events = 0
        total_proving = 0.0
        by_status: dict[str, int] = {}
        for h in histories:
            data = json.loads(h.read_text(encoding="utf-8"))
            total_events += data.get("event_count", 0)
            total_proving += data.get("proving_pct", 0.0)
            st = data.get("status", "UNKNOWN")
            by_status[st] = by_status.get(st, 0) + 1
        n = len(histories) or 1
        print(f"Projects: {len(histories)}")
        print(f"Total events: {total_events}")
        print(f"Avg proving %: {total_proving / n:.1f}")
        print(f"By status: {by_status}")
        return

    ap.print_help()


if __name__ == "__main__":
    main()
