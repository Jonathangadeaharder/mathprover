"""Persistent rate-limit guard for the Aristotle cloud prover.

Personal account limits: 60 requests/minute, 1000 requests/day. State is a small JSON file
under the project's .mathprover/, so limits survive across dispatch invocations and the UI.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

PER_MINUTE = 60
PER_DAY = 1000


class RateLimitError(RuntimeError):
    pass


def _state_path(project_root: Path) -> Path:
    p = project_root / ".mathprover" / "aristotle_ratelimit.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load(path: Path) -> list[float]:
    if not path.exists():
        return []
    try:
        return [float(t) for t in json.loads(path.read_text())]
    except Exception:  # noqa: BLE001 — corrupt file -> start fresh
        return []


def check_and_record(
    project_root: Path, *, per_minute: int = PER_MINUTE, per_day: int = PER_DAY
) -> None:
    """Raise RateLimitError if a new Aristotle request would exceed limits; else record it."""
    path = _state_path(project_root)
    now = time.time()
    stamps = [t for t in _load(path) if now - t < 86400.0]  # keep last day
    last_minute = sum(1 for t in stamps if now - t < 60.0)
    if last_minute >= per_minute:
        raise RateLimitError(
            f"Aristotle per-minute limit reached ({per_minute}/min); retry shortly."
        )
    if len(stamps) >= per_day:
        raise RateLimitError(f"Aristotle daily limit reached ({per_day}/day); resets within 24h.")
    stamps.append(now)
    path.write_text(json.dumps(stamps))


def remaining(project_root: Path, *, per_minute: int = PER_MINUTE, per_day: int = PER_DAY) -> dict:
    path = _state_path(project_root)
    now = time.time()
    stamps = [t for t in _load(path) if now - t < 86400.0]
    return {
        "minute_remaining": max(0, per_minute - sum(1 for t in stamps if now - t < 60.0)),
        "day_remaining": max(0, per_day - len(stamps)),
    }
