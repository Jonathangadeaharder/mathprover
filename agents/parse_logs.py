#!/usr/bin/env python3
"""Retrospective log parser — extracts structured trajectory data from existing
pipeline logs and dispatch attempt logs.

MathProver's existing logs are free-form text (Python logging + markdown-like
attempt logs). This parser best-effort extracts the proving trajectory:

  pipeline logs  (.mathprover/pipeline/logs/*.log):
    "prove_leaf r3 b1: querying oprover-8b (gen<=24576, T=0.8)"
    "prove_leaf r3 b1: compile FAIL -> refine :: error: ..."
    "prove_leaf r3 b1: VERIFIED ..."

  attempt logs   (.mathprover/attempts/*/*.log):
    "## sample 1 round 0"
    "[lean error]\n..."
    "[VERIFIED] sample 1 round 0: lake-clean, placeholder-free"
    "[chat error] ..."
    "[no lean block extracted]"
    "[candidate still contains forbidden placeholders ...]"

Output: JSONL with the same schema as trajectory.py ProvingStep, so parsed
historical data is queryable alongside new structured recordings.

Usage:
  python3 agents/parse_logs.py --root /path/to/lean-project [--output trajectories.jsonl]
  python3 agents/parse_logs.py --root /path/to/lean-project --summary
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


# ---------- pipeline log patterns ----------

# "14:30:00 INFO   prove_leaf r3 b1: querying oprover-8b (gen<=24576, T=0.8)"
_RE_PROVE_QUERY = re.compile(
    r"(\d{2}:\d{2}:\d{2})\s+\w+\s+prove_leaf\s+r(\d+)\s+b(\d+):\s+querying\s+(\S+)\s+\(gen<=(\d+),\s+T=([\d.]+)\)"
)

# "14:30:15 INFO   prove_leaf r3 b1: compile FAIL -> refine :: error: ..."
_RE_PROVE_COMPILE = re.compile(
    r"(\d{2}:\d{2}:\d{2})\s+\w+\s+prove_leaf\s+r(\d+)\s+b(\d+):\s+compile FAIL"
)

# "14:30:15 INFO   prove_leaf r3 b1: REJECTED — statement changed (soundness guard)"
_RE_PROVE_STATEMENT = re.compile(
    r"(\d{2}:\d{2}:\d{2})\s+\w+\s+prove_leaf\s+r(\d+)\s+b(\d+):\s+REJECTED"
)

# "14:30:15 INFO   prove_leaf r3 b1: candidate still has placeholders ..."
_RE_PROVE_FORBIDDEN = re.compile(
    r"(\d{2}:\d{2}:\d{2})\s+\w+\s+prove_leaf\s+r(\d+)\s+b(\d+):\s+candidate still has placeholders"
)

# "14:30:15 INFO   prove_leaf r3 b1: no lean block extracted -> retry"
_RE_PROVE_NO_BLOCK = re.compile(
    r"(\d{2}:\d{2}:\d{2})\s+\w+\s+prove_leaf\s+r(\d+)\s+b(\d+):\s+no lean block extracted"
)

# "14:30:15 INFO   prove_leaf r3 b1: VERIFIED (lake-clean, sorry-free, statement preserved) -> ..."
_RE_PROVE_VERIFIED = re.compile(
    r"(\d{2}:\d{2}:\d{2})\s+\w+\s+prove_leaf\s+r(\d+)\s+b(\d+):\s+VERIFIED"
)

# "14:30:15 INFO   prove_leaf r3 b1: chat failed (...) -> keep prior state"
_RE_PROVE_CHAT_FAIL = re.compile(
    r"(\d{2}:\d{2}:\d{2})\s+\w+\s+prove_leaf\s+r(\d+)\s+b(\d+):\s+chat failed"
)

# "prove_leaf: exhausted N refinement rounds on M branches, UNPROVED"
_RE_PROVE_EXHAUSTED = re.compile(
    r"(\d{2}:\d{2}:\d{2})\s+\w+\s+prove_leaf:\s+exhausted\s+(\d+)\s+refinement\s+rounds"
)

# General: "=== pipeline run 20260617T143000  log=... ==="
_RE_PIPELINE_RUN = re.compile(
    r"===\s+pipeline run\s+(\S+)\s+log="
)


# ---------- attempt log patterns ----------

# "## sample 1 round 0"
_RE_SAMPLE_ROUND = re.compile(r"^##\s+sample\s+(\d+)\s+round\s+(\d+)")

# "[VERIFIED] sample 1 round 0: lake-clean, placeholder-free"
_RE_ATTEMPT_VERIFIED = re.compile(r"\[VERIFIED\]\s+sample\s+(\d+)\s+round\s+(\d+)")

# "[lean error]"
_RE_ATTEMPT_LEAN_ERROR = re.compile(r"\[lean error\]")

# "[chat error] ..."
_RE_ATTEMPT_CHAT_ERROR = re.compile(r"\[chat error\]")

# "[no lean block extracted]"
_RE_ATTEMPT_NO_BLOCK = re.compile(r"\[no lean block extracted\]")

# "[candidate still contains forbidden placeholders ...]"
_RE_ATTEMPT_FORBIDDEN = re.compile(r"\[candidate still contains forbidden placeholders")

# "# oprover @ http://... model=oprover-8b"
_RE_ATTEMPT_HEADER = re.compile(r"^#\s+(\S+)\s+@\s+(\S+)\s+model=(\S+)")

# "prompt:" (Aristotle)
_RE_ARISTOTLE_PROMPT = re.compile(r"^prompt:\s*", re.MULTILINE)

# "project_id=..."
_RE_ARISTOTLE_PROJECT = re.compile(r"project_id=(\S+)")

# "final_status=..."
_RE_ARISTOTLE_STATUS = re.compile(r"final_status=(\S+)")


@dataclass
class ParsedStep:
    """One extracted proving step from a text log."""
    ts: str = ""
    event: str = "parsed_step"
    source: str = ""          # "pipeline_log" | "attempt_log"
    source_file: str = ""
    run_id: str = ""
    node_id: str = ""
    prover: str = ""
    round: int = 0
    branch: int = -1
    sample: int = -1          # lmstudio dispatch sample index
    sample_round: int = -1    # lmstudio dispatch correction round
    gate: str = ""            # "query" | "compile_fail" | "compile_ok" | "statement_changed" |
                              # "forbidden_placeholder" | "no_block" | "chat_error" | "verified"
    feedback_head: str = ""   # first line of compile feedback (pipeline logs only)
    model: str = ""
    max_tokens: int | None = None
    temperature: float | None = None
    aristotle_project_id: str = ""
    aristotle_final_status: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_pipeline_log(path: Path) -> list[ParsedStep]:
    """Parse a pipeline log file into structured steps."""
    steps: list[ParsedStep] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    current_run_id = ""
    date_prefix = ""

    # Try to extract date from filename (e.g., 20260617T143000.log)
    fname = path.stem
    if fname[:8].isdigit():
        date_prefix = fname[:8]

    for line in lines:
        # Pipeline run header
        m = _RE_PIPELINE_RUN.search(line)
        if m:
            current_run_id = m.group(1)
            continue

        # Query
        m = _RE_PROVE_QUERY.search(line)
        if m:
            ts_time = m.group(1)
            rnd = int(m.group(2))
            brn = int(m.group(3))
            model = m.group(4)
            mt = int(m.group(5))
            temp = float(m.group(6))
            steps.append(ParsedStep(
                ts=_make_ts(date_prefix, ts_time),
                source="pipeline_log",
                source_file=str(path),
                run_id=current_run_id,
                prover="oprover",
                round=rnd,
                branch=brn,
                gate="query",
                model=model,
                max_tokens=mt,
                temperature=temp,
            ))
            continue

        # Compile fail
        m = _RE_PROVE_COMPILE.search(line)
        if m:
            ts_time = m.group(1)
            rnd = int(m.group(2))
            brn = int(m.group(3))
            # Extract feedback head from after "::"
            feedback_head = ""
            after = line.split("::", 1)
            if len(after) > 1:
                feedback_head = after[1].strip()[:200]
            steps.append(ParsedStep(
                ts=_make_ts(date_prefix, ts_time),
                source="pipeline_log",
                source_file=str(path),
                run_id=current_run_id,
                prover="oprover",
                round=rnd,
                branch=brn,
                gate="compile_fail",
                feedback_head=feedback_head,
            ))
            continue

        # Statement changed
        m = _RE_PROVE_STATEMENT.search(line)
        if m:
            ts_time = m.group(1)
            rnd = int(m.group(2))
            brn = int(m.group(3))
            steps.append(ParsedStep(
                ts=_make_ts(date_prefix, ts_time),
                source="pipeline_log",
                source_file=str(path),
                run_id=current_run_id,
                prover="oprover",
                round=rnd,
                branch=brn,
                gate="statement_changed",
            ))
            continue

        # Forbidden placeholder
        m = _RE_PROVE_FORBIDDEN.search(line)
        if m:
            ts_time = m.group(1)
            rnd = int(m.group(2))
            brn = int(m.group(3))
            steps.append(ParsedStep(
                ts=_make_ts(date_prefix, ts_time),
                source="pipeline_log",
                source_file=str(path),
                run_id=current_run_id,
                prover="oprover",
                round=rnd,
                branch=brn,
                gate="forbidden_placeholder",
            ))
            continue

        # No lean block
        m = _RE_PROVE_NO_BLOCK.search(line)
        if m:
            ts_time = m.group(1)
            rnd = int(m.group(2))
            brn = int(m.group(3))
            steps.append(ParsedStep(
                ts=_make_ts(date_prefix, ts_time),
                source="pipeline_log",
                source_file=str(path),
                run_id=current_run_id,
                prover="oprover",
                round=rnd,
                branch=brn,
                gate="no_block",
            ))
            continue

        # Verified
        m = _RE_PROVE_VERIFIED.search(line)
        if m:
            ts_time = m.group(1)
            rnd = int(m.group(2))
            brn = int(m.group(3))
            steps.append(ParsedStep(
                ts=_make_ts(date_prefix, ts_time),
                source="pipeline_log",
                source_file=str(path),
                run_id=current_run_id,
                prover="oprover",
                round=rnd,
                branch=brn,
                gate="verified",
            ))
            continue

        # Chat error
        m = _RE_PROVE_CHAT_FAIL.search(line)
        if m:
            ts_time = m.group(1)
            rnd = int(m.group(2))
            brn = int(m.group(3))
            steps.append(ParsedStep(
                ts=_make_ts(date_prefix, ts_time),
                source="pipeline_log",
                source_file=str(path),
                run_id=current_run_id,
                prover="oprover",
                round=rnd,
                branch=brn,
                gate="chat_error",
            ))
            continue

    return steps


def parse_attempt_log(path: Path, node_id: str = "") -> list[ParsedStep]:
    """Parse a dispatch attempt log into structured steps."""
    steps: list[ParsedStep] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    current_prover = ""
    current_model = ""
    current_sample = -1
    current_round = -1
    run_id = path.stem  # filename = run_id
    is_aristotle = False
    aristotle_project_id = ""
    aristotle_final_status = ""

    for line in lines:
        # Header
        m = _RE_ATTEMPT_HEADER.search(line)
        if m:
            current_prover = m.group(1)
            current_model = m.group(3)
            is_aristotle = False
            continue

        # Aristotle project id
        m = _RE_ARISTOTLE_PROJECT.search(line)
        if m:
            aristotle_project_id = m.group(1)
            is_aristotle = True
            continue

        # Aristotle final status
        m = _RE_ARISTOTLE_STATUS.search(line)
        if m:
            aristotle_final_status = m.group(1)
            continue

        # Sample/round header
        m = _RE_SAMPLE_ROUND.search(line)
        if m:
            current_sample = int(m.group(1))
            current_round = int(m.group(2))
            steps.append(ParsedStep(
                source="attempt_log",
                source_file=str(path),
                run_id=run_id,
                node_id=node_id,
                prover=current_prover,
                sample=current_sample,
                sample_round=current_round,
                gate="query",
                model=current_model,
            ))
            continue

        # Verified
        m = _RE_ATTEMPT_VERIFIED.search(line)
        if m:
            steps.append(ParsedStep(
                source="attempt_log",
                source_file=str(path),
                run_id=run_id,
                node_id=node_id,
                prover=current_prover,
                sample=int(m.group(1)),
                sample_round=int(m.group(2)),
                gate="verified",
                model=current_model,
            ))
            continue

        # Lean error
        if _RE_ATTEMPT_LEAN_ERROR.search(line):
            steps.append(ParsedStep(
                source="attempt_log",
                source_file=str(path),
                run_id=run_id,
                node_id=node_id,
                prover=current_prover,
                sample=current_sample,
                sample_round=current_round,
                gate="compile_fail",
                model=current_model,
            ))
            continue

        # Chat error
        if _RE_ATTEMPT_CHAT_ERROR.search(line):
            steps.append(ParsedStep(
                source="attempt_log",
                source_file=str(path),
                run_id=run_id,
                node_id=node_id,
                prover=current_prover,
                sample=current_sample,
                sample_round=current_round,
                gate="chat_error",
                model=current_model,
            ))
            continue

        # No block
        if _RE_ATTEMPT_NO_BLOCK.search(line):
            steps.append(ParsedStep(
                source="attempt_log",
                source_file=str(path),
                run_id=run_id,
                node_id=node_id,
                prover=current_prover,
                sample=current_sample,
                sample_round=current_round,
                gate="no_block",
                model=current_model,
            ))
            continue

        # Forbidden placeholder
        if _RE_ATTEMPT_FORBIDDEN.search(line):
            steps.append(ParsedStep(
                source="attempt_log",
                source_file=str(path),
                run_id=run_id,
                node_id=node_id,
                prover=current_prover,
                sample=current_sample,
                sample_round=current_round,
                gate="forbidden_placeholder",
                model=current_model,
            ))
            continue

    # Aristotle summary step
    if is_aristotle:
        steps.append(ParsedStep(
            source="attempt_log",
            source_file=str(path),
            run_id=run_id,
            node_id=node_id,
            prover="aristotle",
            gate="aristotle_result",
            aristotle_project_id=aristotle_project_id,
            aristotle_final_status=aristotle_final_status,
        ))

    return steps


def _make_ts(date_prefix: str, time_str: str) -> str:
    """Best-effort ISO timestamp from date prefix + HH:MM:SS."""
    if date_prefix and len(date_prefix) >= 8:
        return f"{date_prefix[:4]}-{date_prefix[4:6]}-{date_prefix[6:8]}T{time_str}Z"
    return time_str


def parse_project(project_root: Path) -> list[ParsedStep]:
    """Parse all logs under a project root."""
    steps: list[ParsedStep] = []

    # Pipeline logs
    pipeline_dir = project_root / ".mathprover" / "pipeline" / "logs"
    if pipeline_dir.is_dir():
        for log_file in sorted(pipeline_dir.glob("*.log")):
            steps.extend(parse_pipeline_log(log_file))

    # Attempt logs (organized by node folder)
    attempts_dir = project_root / ".mathprover" / "attempts"
    if attempts_dir.is_dir():
        for node_dir in sorted(attempts_dir.iterdir()):
            if not node_dir.is_dir():
                continue
            node_id = node_dir.name
            for log_file in sorted(node_dir.glob("*.log")):
                steps.extend(parse_attempt_log(log_file, node_id=node_id))

    # Sort by timestamp (best-effort)
    steps.sort(key=lambda s: s.ts)
    return steps


def summary(steps: list[ParsedStep]) -> str:
    """Printable summary of parsed trajectory data."""
    total = len(steps)
    by_gate: dict[str, int] = {}
    by_prover: dict[str, int] = {}
    by_source: dict[str, int] = {}
    verified = 0
    rounds_seen: set[tuple[str, int, int]] = set()  # (run_id, round, branch)
    max_round = 0

    for s in steps:
        by_gate[s.gate] = by_gate.get(s.gate, 0) + 1
        by_prover[s.prover] = by_prover.get(s.prover, 0) + 1
        by_source[s.source] = by_source.get(s.source, 0) + 1
        if s.gate == "verified":
            verified += 1
        if s.round > 0:
            rounds_seen.add((s.run_id, s.round, s.branch))
            max_round = max(max_round, s.round)

    lines = [
        f"Parsed {total} steps from logs",
        f"Verified (proved): {verified}",
        f"By gate: {by_gate}",
        f"By prover: {by_prover}",
        f"By source: {by_source}",
        f"Max round seen: {max_round}",
        f"Unique (run_id, round, branch) triples: {len(rounds_seen)}",
    ]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Parse MathProver text logs into structured JSONL")
    ap.add_argument("--root", required=True, help="Lean project root")
    ap.add_argument("--output", default=None, help="Output JSONL path (default: stdout)")
    ap.add_argument("--summary", action="store_true", help="Print summary instead of JSONL")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    steps = parse_project(root)

    if args.summary:
        print(summary(steps))
        return

    rows = [s.to_dict() for s in steps]
    out = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
    if args.output:
        Path(args.output).write_text(out + "\n", encoding="utf-8")
        print(f"Wrote {len(rows)} rows to {args.output}", file=sys.stderr)
    else:
        print(out)


if __name__ == "__main__":
    main()
