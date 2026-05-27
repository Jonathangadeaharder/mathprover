"""Aristotle cloud prover backend with async poll + download."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from config import ProverConfig
from lean_pipeline import (
    compile_lean_file,
    extract_tarball,
    find_attempt_lean,
    has_sorry,
)
from prompts import build_aristotle_prompt


@dataclass
class RunResult:
    prover: str
    success: bool
    log_path: Path
    output_path: Path | None
    message: str
    project_id: str | None = None


def preflight(config: ProverConfig) -> None:
    for var in config.requires_env:
        if not os.environ.get(var):
            raise RuntimeError(
                f"{var} is not set. Revoke any exposed key, create a new one at "
                "https://aristotle.harmonic.fun/dashboard/keys and add to ~/.zshrc."
            )
    if shutil.which(config.command) is None:
        raise RuntimeError(
            f"{config.command!r} not found. Install with: uv tool install aristotlelib"
        )


async def _run_aristotle_async(
    *,
    config: ProverConfig,
    project_root: Path,
    proof_dir: Path,
    attempt_file: Path,
    log_path: Path,
    destination: Path,
) -> RunResult:
    from aristotlelib.agent_task import TaskStatus as AristotleTaskStatus
    from aristotlelib.project import Project

    logging.getLogger("aristotle").setLevel(logging.WARNING)
    prompt = build_aristotle_prompt(
        proof_dir=proof_dir,
        attempt_file=attempt_file,
        project_root=project_root,
    )

    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"prompt:\n{prompt}\n\n")
        project = await Project.create_from_directory(prompt=prompt, project_dir=project_root)
        project_id = project.project_id
        log.write(f"project_id={project_id}\n\n")

        tasks, _ = await project.get_tasks(limit=1)
        if not tasks:
            return RunResult(
                prover="aristotle",
                success=False,
                log_path=log_path,
                output_path=log_path,
                message="aristotle created project but returned no tasks",
                project_id=project_id,
            )

        task = tasks[0]
        log.write(f"task_id={task.agent_task_id} status={task.status.name}\n")
        try:
            await asyncio.wait_for(
                task.wait_for_completion(
                    num_events=0,
                    poll_interval_seconds=config.poll_interval_seconds,
                ),
                timeout=config.max_wait_minutes * 60,
            )
        except asyncio.TimeoutError:
            return RunResult(
                prover="aristotle",
                success=False,
                log_path=log_path,
                output_path=log_path,
                message=f"aristotle timed out after {config.max_wait_minutes} minutes",
                project_id=project_id,
            )
        await project.refresh()
        log.write(f"final_status={task.status.name}\n")
        if task.output_summary:
            log.write(f"summary:\n{task.output_summary}\n")

        if task.status not in (
            AristotleTaskStatus.COMPLETE,
            AristotleTaskStatus.COMPLETE_WITH_ERRORS,
        ):
            return RunResult(
                prover="aristotle",
                success=False,
                log_path=log_path,
                output_path=log_path,
                message=f"aristotle task ended with {task.status.name}",
                project_id=project_id,
            )

        archive = await project.get_files(destination=destination / f"{project_id}.tar.gz")
        log.write(f"downloaded={archive}\n")
        extract_root = destination / "extracted"
        extract_tarball(archive, extract_root)

        rel_hint = attempt_file.relative_to(project_root).as_posix()
        found = find_attempt_lean(extract_root, rel_hint=rel_hint)
        if found is None:
            return RunResult(
                prover="aristotle",
                success=False,
                log_path=log_path,
                output_path=log_path,
                message="aristotle download did not contain attempt.lean",
                project_id=project_id,
            )

        candidate = found.read_text(encoding="utf-8")
        log.write(f"found={found}\n")
        if has_sorry(candidate):
            return RunResult(
                prover="aristotle",
                success=False,
                log_path=log_path,
                output_path=log_path,
                message="aristotle output still contains sorry",
                project_id=project_id,
            )

        attempt_file.write_text(candidate, encoding="utf-8")
        compile_result = compile_lean_file(project_root=project_root, lean_file=attempt_file)
        log.write("\n--- compile attempt.lean ---\n")
        log.write(compile_result.combined)
        if not compile_result.ok:
            return RunResult(
                prover="aristotle",
                success=False,
                log_path=log_path,
                output_path=log_path,
                message="aristotle proof downloaded but local compile failed",
                project_id=project_id,
            )

        return RunResult(
            prover="aristotle",
            success=True,
            log_path=log_path,
            output_path=found,
            message="aristotle pipeline succeeded",
            project_id=project_id,
        )


def run_aristotle(
    *,
    config: ProverConfig,
    project_root: Path,
    proof_dir: Path,
    attempt_file: Path,
    log_path: Path,
) -> RunResult:
    preflight(config)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("", encoding="utf-8")
    destination = log_path.parent / "aristotle"
    try:
        return asyncio.run(
            _run_aristotle_async(
                config=config,
                project_root=project_root,
                proof_dir=proof_dir,
                attempt_file=attempt_file,
                log_path=log_path,
                destination=destination,
            )
        )
    except Exception as exc:
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"\nerror: {exc}\n")
        return RunResult(
            prover="aristotle",
            success=False,
            log_path=log_path,
            output_path=log_path,
            message=f"aristotle failed: {exc}",
        )
