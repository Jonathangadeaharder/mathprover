#!/usr/bin/env python3
"""Low-noise JSONL telemetry for local model calls and residency events."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


def _telemetry_dir() -> Path:
    configured = os.environ.get("MATHPROVER_TELEMETRY_DIR")
    if configured:
        return Path(configured).expanduser()
    project = os.environ.get("MATHPROVER_PROJECT_PATH")
    if project:
        return Path(project).expanduser() / ".mathprover" / "telemetry"
    return Path.home() / ".mathprover" / "telemetry"


def enabled() -> bool:
    value = os.environ.get("MATHPROVER_TELEMETRY", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


def record(event: str, **fields: Any) -> None:
    if not enabled():
        return
    row = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": event,
        **fields,
    }
    try:
        path = _telemetry_dir() / f"{time.strftime('%Y%m%d', time.gmtime())}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    except Exception:
        # Telemetry is diagnostic only; it must never perturb proof search.
        return
