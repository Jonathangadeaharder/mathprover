"""Goedel-Prover-V2-32B MLX backend with pass@N and self-correction."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from config import ProverConfig
from resource_guard import ResourceLimits, require_goedel_capacity


@dataclass
class RunResult:
    prover: str
    success: bool
    log_path: Path
    output_path: Path | None
    message: str


def _pipeline_runner(config: ProverConfig) -> Path:
    if not config.command.strip():
        raise RuntimeError(
            "Goedel prover command is not configured. Set GOEDEL_PROVER_PATH to your run.sh path."
        )
    run_sh = Path(os.path.expanduser(config.command)).resolve()
    pipeline = run_sh.parent / "run_pipeline.sh"
    if pipeline.exists():
        return pipeline
    return run_sh.parent / "run_pipeline.py"


def preflight(config: ProverConfig, resource_limits: ResourceLimits | None = None) -> None:
    require_goedel_capacity(resource_limits)
    runner = _pipeline_runner(config)
    if not runner.exists():
        raise RuntimeError(f"Goedel pipeline runner not found: {runner}")
    preflight_py = runner.parent / "preflight.py"
    if preflight_py.exists():
        subprocess.run(
            [sys.executable, str(preflight_py), "--check-exclusive"],
            check=True,
            cwd=runner.parent,
        )


def run_goedel(
    *,
    config: ProverConfig,
    attempt_file: Path,
    proof_dir: Path,
    project_root: Path,
    log_path: Path,
    max_tokens: int | None = None,
    resource_limits: ResourceLimits | None = None,
) -> RunResult:
    preflight(config, resource_limits)
    runner = _pipeline_runner(config)
    agents_dir = Path(__file__).resolve().parents[1]
    work_dir = log_path.parent / "work"
    env = os.environ.copy()
    env["MATHPROVER_AGENTS"] = str(agents_dir)

    cmd = [
        str(runner),
        "--agents-dir",
        str(agents_dir),
        "--lean-file",
        str(attempt_file),
        "--project-root",
        str(project_root),
        "--proof-dir",
        str(proof_dir),
        "--work-dir",
        str(work_dir),
        "--log-file",
        str(log_path),
        "--run-id",
        log_path.stem,
        "--num-samples",
        str(config.max_attempts),
        "--correction-rounds",
        str(config.correction_rounds),
        "--initial-max-tokens",
        str(max_tokens or config.initial_max_tokens),
        "--correction-max-tokens",
        str(config.correction_max_tokens),
        "--temp",
        str(config.temperature),
        "--top-p",
        str(config.top_p),
    ]

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"$ {' '.join(cmd)}\n\n")
        log.flush()
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=runner.parent,
            env=env,
        )
        log.write(proc.stdout or "")

    ok = proc.returncode == 0
    message = "goedel pipeline finished"
    if proc.stdout:
        for line in reversed(proc.stdout.splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    payload = json.loads(line)
                    if payload.get("success"):
                        message = (
                            f"goedel pipeline succeeded "
                            f"(sample={payload.get('sample')}, round={payload.get('round')})"
                        )
                    break
                except json.JSONDecodeError:
                    continue
    if not ok:
        message = f"goedel pipeline exited {proc.returncode}"

    return RunResult(
        prover="goedel",
        success=ok,
        log_path=log_path,
        output_path=log_path,
        message=message,
    )
