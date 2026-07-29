"""Aristotle cloud prover backend with async poll + download."""

from __future__ import annotations

import asyncio
import logging
import os
import shlex
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import trajectory  # noqa: E402
from config import ProverConfig
from lean_pipeline import (
    compile_lean_file,
    extract_tarball,
    find_attempt_lean,
    forbidden_placeholders,
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
    # Set when the local poll cap expired while the cloud task kept running. Not a failure.
    pending_reattach: str | None = None
    # Set when the prover never ran (transport or submit failure). Not a proof failure.
    dispatch_error: str | None = None


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


def _stage_project(project_root: Path, stage_root: Path) -> None:
    """Copy only the files Aristotle actually needs into a tiny staging tree."""
    keep_files = {
        "mathprover.toml",
        "lakefile.lean",
        "lean-toolchain",
        ".gitignore",
    }
    skip_roots = {".git", ".mathprover", ".claude", ".venv", "node_modules", "dist", "build"}
    for path in project_root.rglob("*"):
        rel = path.relative_to(project_root)
        if any(part in skip_roots for part in rel.parts):
            continue
        if path.is_dir():
            continue
        if path.suffix == ".lean" or path.name in keep_files:
            dest = stage_root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)

    lake_build_lib = project_root / ".lake" / "build" / "lib"
    if lake_build_lib.is_dir():
        shutil.copytree(
            lake_build_lib,
            stage_root / ".lake" / "build" / "lib",
            dirs_exist_ok=True,
            symlinks=True,
        )
    lake_config = project_root / ".lake" / "config"
    if lake_config.is_dir():
        shutil.copytree(
            lake_config,
            stage_root / ".lake" / "config",
            dirs_exist_ok=True,
            symlinks=True,
        )
    # Preserve the workspace marker without shipping the huge source cache.
    (stage_root / ".lake").mkdir(parents=True, exist_ok=True)


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

    with tempfile.TemporaryDirectory() as td:
        stage_root = Path(td) / project_root.name
        _stage_project(project_root, stage_root)
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"prompt:\n{prompt}\n\n")
            # Trajectory: record the prompt before submitting
            _traj_node = attempt_file.parent.name
            _traj_run = log_path.stem
            trajectory.record_proving_step(
                run_id=_traj_run,
                node_id=_traj_node,
                prover="aristotle",
                round=0,
                branch=-1,
                phase="generate",
                gate="query",
                prompt={"system": "", "user": prompt[:4000]},
                metadata={"phase": "submit"},
                project_root=project_root,
            )
            project = await Project.create_from_directory(prompt=prompt, project_dir=stage_root)
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
                # Client-side poll cap only: the CLOUD task keeps running, so tell the
                # caller how to re-attach. `uv run` is required because aristotlelib lives
                # in the agents venv, not in the ambient python3.
                reattach_cmd = (
                    f"cd agents && uv run python aristotle_attach.py "
                    f"--project-id {shlex.quote(str(project_id))} "
                    f"--task-id {shlex.quote(str(task.agent_task_id))} "
                    f"--node {shlex.quote(_traj_node)} "
                    f"--project-root {shlex.quote(str(project_root))} --wait"
                )
                msg = (
                    f"local poll stopped after {config.max_wait_minutes} min. "
                    f"Aristotle task is STILL RUNNING in the cloud (not cancelled). "
                    f"Re-attach with: {reattach_cmd}"
                )
                log.write(msg + "\n")
                return RunResult(
                    prover="aristotle",
                    success=False,
                    log_path=log_path,
                    output_path=log_path,
                    message=msg,
                    project_id=project_id,
                    pending_reattach=reattach_cmd,
                )
            await project.refresh()
            log.write(f"final_status={task.status.name}\n")
            if task.output_summary:
                log.write(f"summary:\n{task.output_summary}\n")

            # Trajectory: record the cloud result
            trajectory.record_proving_step(
                run_id=_traj_run,
                node_id=_traj_node,
                prover="aristotle",
                round=0,
                branch=-1,
                phase="compile",
                gate="aristotle_" + task.status.name.lower(),
                metadata={
                    "project_id": project_id,
                    "task_id": task.agent_task_id,
                    "final_status": task.status.name,
                    "output_summary": (task.output_summary or "")[:1000],
                },
                project_root=project_root,
            )

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

            destination.mkdir(parents=True, exist_ok=True)
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
            forbidden = forbidden_placeholders(candidate)
            if forbidden:
                return RunResult(
                    prover="aristotle",
                    success=False,
                    log_path=log_path,
                    output_path=log_path,
                    message="aristotle output still contains forbidden placeholders: "
                    + ", ".join(forbidden),
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
            dispatch_error=str(exc) or exc.__class__.__name__,
        )
