"""Exclusive Goedel lock and memory safety checks."""

from __future__ import annotations

import fcntl
import os
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ResourceLimits:
    max_concurrent_goedel: int = 1
    min_free_memory_gib: float = 12.0


class ResourceGuardError(RuntimeError):
    pass


def _memory_stats_gib() -> tuple[float, float]:
    """Return (total_gib, free_gib) best-effort on macOS."""
    try:
        total_bytes = int(
            subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()
        )
    except (subprocess.CalledProcessError, ValueError) as exc:
        raise ResourceGuardError(f"Could not read system memory: {exc}") from exc

    total_gib = total_bytes / (1024**3)
    free_gib = total_gib
    try:
        out = subprocess.check_output(["vm_stat"], text=True)
        page_size = 4096
        for line in out.splitlines():
            if line.startswith("Mach Virtual Memory Statistics:"):
                parts = line.split("(page size of")
                if len(parts) == 2:
                    page_size = int(parts[1].split()[0])
            if "Pages free:" in line:
                free_pages = int(line.split(":")[1].strip().rstrip("."))
                free_gib = free_pages * page_size / (1024**3)
                break
    except (subprocess.CalledProcessError, ValueError):
        pass
    return total_gib, free_gib


def _goedel_pids() -> list[int]:
    patterns = (
        "run_prover.py",
        "run_pipeline.py",
        "Goedel-Prover-V2-32B",
        "goedel-prover-v2-32b/run",
    )
    pids: set[int] = set()
    for pattern in patterns:
        try:
            out = subprocess.check_output(["pgrep", "-f", pattern], text=True)
        except subprocess.CalledProcessError:
            continue
        for line in out.splitlines():
            line = line.strip()
            if line.isdigit():
                pid = int(line)
                if pid != os.getpid():
                    pids.add(pid)
    return sorted(pids)


def require_goedel_capacity(limits: ResourceLimits | None = None) -> None:
    limits = limits or ResourceLimits()
    running = _goedel_pids()
    if len(running) >= limits.max_concurrent_goedel:
        raise ResourceGuardError(
            "Goedel MLX is already running (PIDs: "
            f"{', '.join(map(str, running))}). "
            "Only one local 32B run is allowed at a time (~35 GiB weights). "
            "Wait for it to finish or stop it before dispatching again."
        )

    total_gib, free_gib = _memory_stats_gib()
    if free_gib < limits.min_free_memory_gib:
        raise ResourceGuardError(
            f"Insufficient free memory: {free_gib:.1f} GiB free, "
            f"{limits.min_free_memory_gib:.1f} GiB required before loading Goedel "
            f"(system total {total_gib:.1f} GiB). Close other heavy apps and retry."
        )


@contextmanager
def goedel_exclusive_lock(project_root: Path, limits: ResourceLimits | None = None):
    """Hold an exclusive flock for the duration of a Goedel dispatch."""
    limits = limits or ResourceLimits()
    require_goedel_capacity(limits)

    lock_dir = project_root / ".mathprover" / "locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / "goedel.lock"
    handle = lock_path.open("a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        handle.close()
        holder = lock_path.read_text(encoding="utf-8").strip() if lock_path.exists() else "unknown"
        raise ResourceGuardError(
            "Another Goedel dispatch holds the exclusive lock "
            f"({lock_path}; holder={holder or 'unknown'}). "
            "Parallel Goedel runs are forbidden."
        ) from exc

    handle.seek(0)
    handle.truncate()
    handle.write(f"pid={os.getpid()} ppid={os.getppid()}\n")
    handle.flush()

    try:
        yield lock_path
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()
            try:
                lock_path.unlink(missing_ok=True)
            except OSError:
                pass
