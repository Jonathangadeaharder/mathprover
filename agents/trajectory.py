#!/usr/bin/env python3
"""Structured JSONL trajectory recorder for MathProver proving sessions.

Records the full prompt->response->compiler-feedback loop at every round/branch
of the proving pipeline. This is the data that was previously LOST: the per-round
(prev_attempt, lean_feedback) state was transient (in-memory only), telemetry had
token counts but no content, and the DAG stored only 160-char feedback headlines.

Schema per row (event="proving_step"):
  ts                 ISO UTC timestamp
  event              "proving_step" | "dispatch_step" | "aristotle_step"
  run_id             dispatch run id (or pipeline session id)
  node_id            proof node / folder name
  prover             "oprover" | "lmstudio" | "qwen" | "aristotle"
  round              refinement round (1-based)
  branch             branch index within round (0-based; -1 for non-branched)
  phase              "generate" | "compile" | "gate" | "refute"
  prompt             {"system": ..., "user": ...}  (oprover/aristotle)
                     or {"messages": [...]}         (lmstudio dispatch)
  model_output       raw model output string
  candidate          extracted lean block (None if extraction failed)
  compile_ok         bool | None (None = not compiled)
  compile_feedback   compiler output (ANSI-stripped, truncated to 4000 chars)
  gate               "ok" | "no_block" | "statement_changed" |
                     "forbidden_placeholder" | "compile_fail" | "compile_ok" |
                     "chat_error" | "refute_negation_ok"
  prompt_tokens      int | None (from OpenAI usage)
  completion_tokens  int | None
  latency_s          float | None (wall time for this model call)
  temperature        float | None
  max_tokens         int | None
  metadata           dict  (catch-all: sample index for lmstudio, project_id for aristotle, etc.)

Storage: $MATHPROVER_TRAJECTORY_DIR/{YYYYMMDD}.jsonl
         (default: <project>/.mathprover/trajectories/)
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
MAX_FEEDBACK_CHARS = 4000


def _trajectory_dir(project_root: Path | None = None) -> Path:
    configured = os.environ.get("MATHPROVER_TRAJECTORY_DIR")
    if configured:
        return Path(configured).expanduser()
    if project_root:
        return project_root / ".mathprover" / "trajectories"
    project = os.environ.get("MATHPROVER_PROJECT_PATH")
    if project:
        return Path(project).expanduser() / ".mathprover" / "trajectories"
    return Path.home() / ".mathprover" / "trajectories"


def enabled() -> bool:
    value = os.environ.get("MATHPROVER_TRAJECTORY", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def _truncate(text: str | None, max_chars: int = MAX_FEEDBACK_CHARS) -> str | None:
    if text is None:
        return None
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return text[:half] + "\n\n[... truncated ...]\n\n" + text[-half:]


@dataclass
class ProvingStep:
    """One round of the compiler-in-the-loop proving trajectory."""

    ts: str
    event: str = "proving_step"
    run_id: str = ""
    node_id: str = ""
    prover: str = ""
    round: int = 0
    branch: int = -1
    phase: str = "generate"
    prompt: dict[str, Any] = field(default_factory=dict)
    model_output: str = ""
    candidate: str | None = None
    compile_ok: bool | None = None
    compile_feedback: str | None = None
    gate: str = ""
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    latency_s: float | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def record(step: ProvingStep, project_root: Path | None = None) -> None:
    """Append one trajectory step to the daily JSONL file. Never raises."""
    if not enabled():
        return
    try:
        d = _trajectory_dir(project_root)
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{time.strftime('%Y%m%d', time.gmtime())}.jsonl"
        # Truncate large text fields to avoid unbounded JSONL growth
        row = step.to_dict()
        row["model_output"] = _truncate(row.get("model_output", ""), MAX_FEEDBACK_CHARS)
        row["candidate"] = _truncate(row.get("candidate"), MAX_FEEDBACK_CHARS)
        row["compile_feedback"] = _truncate(row.get("compile_feedback"), MAX_FEEDBACK_CHARS)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    except Exception:
        # Trajectory recording is diagnostic; it must never perturb proof search.
        pass


def record_proving_step(
    *,
    run_id: str,
    node_id: str,
    prover: str,
    round: int,
    branch: int = -1,
    phase: str = "generate",
    prompt: dict[str, Any] | None = None,
    model_output: str = "",
    candidate: str | None = None,
    compile_ok: bool | None = None,
    compile_feedback: str | None = None,
    gate: str = "",
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    latency_s: float | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    metadata: dict[str, Any] | None = None,
    project_root: Path | None = None,
) -> None:
    """Convenience wrapper: build a ProvingStep and record it."""
    step = ProvingStep(
        ts=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        event="proving_step",
        run_id=run_id,
        node_id=node_id,
        prover=prover,
        round=round,
        branch=branch,
        phase=phase,
        prompt=prompt or {},
        model_output=model_output,
        candidate=candidate,
        compile_ok=compile_ok,
        compile_feedback=_strip_ansi(compile_feedback) if compile_feedback else None,
        gate=gate,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_s=latency_s,
        temperature=temperature,
        max_tokens=max_tokens,
        metadata=metadata or {},
    )
    record(step, project_root=project_root)


# ---------- session context (thread-local, set once per prove_leaf call) ----------

_session: dict[str, Any] = {}


def begin_session(
    *,
    run_id: str,
    node_id: str,
    prover: str,
    project_root: Path | None = None,
) -> None:
    """Start a new proving session context. Subsequent record_proving_step calls
    inherit run_id/node_id/prover from the session if not explicitly provided."""
    global _session
    _session = {
        "run_id": run_id,
        "node_id": node_id,
        "prover": prover,
        "project_root": project_root,
    }


def end_session() -> None:
    global _session
    _session = {}


def _session_defaults() -> dict[str, Any]:
    return dict(_session)


# ---------- bulk reader (for parse_logs / analysis) ----------


def read_trajectory_file(path: Path) -> list[dict[str, Any]]:
    """Read a trajectory JSONL file into a list of dicts. Skips malformed lines."""
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def list_trajectory_files(project_root: Path | None = None) -> list[Path]:
    """List all trajectory JSONL files, newest first."""
    d = _trajectory_dir(project_root)
    if not d.is_dir():
        return []
    return sorted(d.glob("*.jsonl"), reverse=True)


def load_all_trajectories(project_root: Path | None = None) -> list[dict[str, Any]]:
    """Load and merge all trajectory files, sorted by timestamp."""
    rows: list[dict[str, Any]] = []
    for path in list_trajectory_files(project_root):
        rows.extend(read_trajectory_file(path))
    rows.sort(key=lambda r: r.get("ts", ""))
    return rows
