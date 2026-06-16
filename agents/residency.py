#!/usr/bin/env python3
"""Turn-based single-model residency guard (plan §Components.1).

One machine, three big models that cannot co-reside. JIT is on but does not auto-evict, so a second
model loaded while another is resident OOMs (observed: gemma `Model has not started loading/has been
unloaded`). This guard enforces ONE model in memory at a time: before a model's turn, unload all then
load the target. `lms load` blocks until the model is ready, so no polling needed.

Call ONLY at phase boundaries (CONTEXT/PLAN/PROVE/REASSESS), never per chat() call — a process-wide
cache makes `use(same_model)` a no-op, so the defensive call in pipeline.chat() is free in-phase.
Best-effort: a failed `lms` invocation logs and continues (chat() retry-on-400 covers load races).
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path

LOG = logging.getLogger("mathprover.pipeline")  # share pipeline's handlers (init_log) so swaps log

_LMS = str(Path.home() / ".local" / "bin" / "lms")
_TTL = 3600          # seconds idle before LM Studio auto-unloads (insurance)
_LOAD_TIMEOUT = 240  # generous: gemma-26B / qwen-27B cold load
_current: str | None = None

try:
    import telemetry
except Exception:  # noqa: BLE001
    telemetry = None


def _env() -> dict:
    env = os.environ.copy()
    local_bin = str(Path.home() / ".local" / "bin")
    if local_bin not in env.get("PATH", ""):
        env["PATH"] = local_bin + os.pathsep + env.get("PATH", "")
    return env


def _lms(args: list[str], timeout: int) -> tuple[bool, str]:
    cmd = ([_LMS] if Path(_LMS).exists() else ["lms"]) + args
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=_env())
        return p.returncode == 0, (p.stdout or "") + (p.stderr or "")
    except Exception as e:  # noqa: BLE001 — never let residency bookkeeping crash a run
        return False, f"{type(e).__name__}: {e}"


def current() -> str | None:
    return _current


def _lms_managed(model: str) -> bool:
    lower = model.lower()
    if model.startswith("Youssofal/") or "mtplx" in lower:
        return False
    return True


def _memory_snapshot() -> str:
    try:
        p = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=5)
        return (p.stdout or p.stderr or "").splitlines()[0][:160]
    except Exception:
        return ""


def use(model: str) -> None:
    """Make `model` the sole resident model. No-op if already current (the in-phase common case)."""
    global _current
    if not _lms_managed(model):
        LOG.info("residency: %s served externally; skipping lms load", model)
        if telemetry:
            telemetry.record(
                "residency",
                model=model,
                action="external_skip",
                success=True,
                memory=_memory_snapshot(),
            )
        return
    if model == _current:
        return
    t0 = time.time()
    ok_u, out_u = _lms(["unload", "--all"], timeout=60)
    ok_l, out_l = _lms(["load", model, "-y", "--ttl", str(_TTL)], timeout=_LOAD_TIMEOUT)
    latency = time.time() - t0
    if ok_l:
        _current = model
        LOG.info("residency: swapped to %s in %.1fs", model, latency)
    else:
        # Load failed; leave _current unset so the next use() retries the swap. chat() will still
        # try the request (JIT may load it) and its retry-on-400 covers the race.
        _current = None
        LOG.warning("residency: load %s failed (unload ok=%s): %s", model, ok_u, out_l.strip()[:200])
    if telemetry:
        telemetry.record(
            "residency",
            model=model,
            action="swap",
            unload_ok=ok_u,
            load_ok=ok_l,
            success=ok_l,
            latency_s=round(latency, 3),
            memory=_memory_snapshot(),
        )


def free() -> None:
    """Unload everything (end of run / between unrelated nodes)."""
    global _current
    t0 = time.time()
    ok, out = _lms(["unload", "--all"], timeout=60)
    _current = None
    LOG.info("residency: unloaded all")
    if telemetry:
        telemetry.record(
            "residency",
            action="free",
            unload_ok=ok,
            success=ok,
            latency_s=round(time.time() - t0, 3),
            memory=_memory_snapshot(),
            output_head=out.strip()[:160],
        )
