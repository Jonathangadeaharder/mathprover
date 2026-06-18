"""Local OpenAI-compatible backend — serves oprover, qwen/MTPLX, and other local roles.

Replaces the Goedel MLX backend. Best-of-N drafting + self-correction, with a SOUND gate:
a candidate counts as success only if `lake env lean` compiles AND the file is `sorry`-free
(`lean_pipeline.has_sorry`). This closes the soundness hole in the old standalone `oprover.py`,
which accepted `sorry`-laden non-proofs (a `sorry` is a warning, not an `error:`).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

AGENTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AGENTS))

import models as M  # noqa: E402
import trajectory  # noqa: E402
from config import ProverConfig  # noqa: E402
from lean_pipeline import (  # noqa: E402
    apply_generated_proof,
    compile_lean_file,
    forbidden_placeholders,
)


@dataclass
class RunResult:
    prover: str
    success: bool
    log_path: Path
    output_path: Path | None
    message: str


_SYSTEM = (
    "You are a Lean 4 theorem prover. You are given a Lean source file containing exactly one "
    "`sorry`. Replace the `sorry` with a correct, complete proof. Output the full updated file "
    "(or the proved declaration) inside a single ```lean code block. Do not leave any `sorry`, "
    "`admit`, or `sorryAx`. No prose outside the code block."
)


def _chat(
    base_url: str,
    model: str,
    messages: list[dict],
    *,
    temperature: float,
    max_tokens: int,
    timeout_s: int,
) -> str:
    return M.chat_sync(
        model,
        messages,
        max_tokens=max_tokens,
        temperature=temperature,
        base_url=base_url,
        phase="dispatch",
    )


def run_lmstudio(
    *,
    config: ProverConfig,
    attempt_file: Path,
    proof_dir: Path,  # noqa: ARG001 — kept for backend-protocol parity
    project_root: Path,
    log_path: Path,
    max_tokens: int | None = None,
    resource_limits=None,  # noqa: ARG001 — local API needs no MLX lock
) -> RunResult:
    base_url = config.base_url or M.base_url_for_model(config.model or config.name)
    model = config.model or config.name
    tok = max_tokens or config.max_tokens
    timeout_s = max(60, config.max_wait_minutes * 60 // 4)
    original = attempt_file.read_text(encoding="utf-8")

    log_path.parent.mkdir(parents=True, exist_ok=True)
    succeeded = False
    final_msg = f"{config.name}: no compiling sorry-free proof in {config.max_attempts} samples"

    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"# {config.name} @ {base_url} model={model}\n\n")
        # Derive node_id and run_id from the attempt path for trajectory recording
        _traj_node = attempt_file.parent.name
        _traj_run = log_path.stem
        for sample in range(1, config.max_attempts + 1):
            messages = [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": f"```lean\n{original}\n```"},
            ]
            for rnd in range(config.correction_rounds + 1):
                log.write(f"## sample {sample} round {rnd}\n")
                log.flush()
                try:
                    out = _chat(
                        base_url,
                        model,
                        messages,
                        temperature=config.temperature,
                        max_tokens=tok,
                        timeout_s=timeout_s,
                    )
                except Exception as exc:  # noqa: BLE001 — log + try next sample
                    log.write(f"[chat error] {exc}\n\n")
                    trajectory.record_proving_step(
                        run_id=_traj_run,
                        node_id=_traj_node,
                        prover=config.name,
                        round=rnd,
                        branch=sample - 1,
                        phase="generate",
                        gate="chat_error",
                        prompt={"messages_count": len(messages)},
                        metadata={"sample": sample, "error": str(exc)[:200]},
                        temperature=config.temperature,
                        max_tokens=tok,
                        project_root=project_root,
                    )
                    break
                candidate = apply_generated_proof(original, out)
                if candidate is None:
                    log.write("[no lean block extracted]\n\n")
                    trajectory.record_proving_step(
                        run_id=_traj_run,
                        node_id=_traj_node,
                        prover=config.name,
                        round=rnd,
                        branch=sample - 1,
                        phase="generate",
                        gate="no_block",
                        prompt={"messages_count": len(messages)},
                        model_output=out[:4000],
                        metadata={"sample": sample},
                        temperature=config.temperature,
                        max_tokens=tok,
                        project_root=project_root,
                    )
                    messages += [
                        {"role": "assistant", "content": out},
                        {
                            "role": "user",
                            "content": "No ```lean block found. Output the full file in one ```lean block.",
                        },
                    ]
                    continue
                forbidden = forbidden_placeholders(candidate)
                if forbidden:
                    log.write(
                        f"[candidate still contains forbidden placeholders {forbidden} — rejected]\n\n"
                    )
                    trajectory.record_proving_step(
                        run_id=_traj_run,
                        node_id=_traj_node,
                        prover=config.name,
                        round=rnd,
                        branch=sample - 1,
                        phase="gate",
                        gate="forbidden_placeholder",
                        prompt={"messages_count": len(messages)},
                        model_output=out[:4000],
                        candidate=candidate[:4000],
                        metadata={"sample": sample, "forbidden": forbidden},
                        temperature=config.temperature,
                        max_tokens=tok,
                        project_root=project_root,
                    )
                    messages += [
                        {"role": "assistant", "content": out},
                        {
                            "role": "user",
                            "content": "Your proof still contains placeholders (`sorry`, `admit`, `exact?`, `sorryAx`, or `axiom`). Provide a complete proof with none.",
                        },
                    ]
                    continue
                candidate = _ensure_imports(original, candidate)
                result = compile_lean_file(
                    project_root=project_root, lean_file=_scratch(log_path, candidate)
                )
                if result.ok and not forbidden_placeholders(candidate):
                    attempt_file.write_text(candidate, encoding="utf-8")
                    log.write(
                        f"[VERIFIED] sample {sample} round {rnd}: lake-clean, placeholder-free\n"
                    )
                    trajectory.record_proving_step(
                        run_id=_traj_run,
                        node_id=_traj_node,
                        prover=config.name,
                        round=rnd,
                        branch=sample - 1,
                        phase="compile",
                        gate="compile_ok",
                        prompt={"messages_count": len(messages)},
                        model_output=out[:4000],
                        candidate=candidate[:4000],
                        compile_ok=True,
                        compile_feedback=result.combined[:4000],
                        metadata={"sample": sample},
                        temperature=config.temperature,
                        max_tokens=tok,
                        project_root=project_root,
                    )
                    succeeded = True
                    final_msg = f"{config.name}: verified (sample={sample}, round={rnd})"
                    break
                err = result.error_excerpt(2000)
                log.write(f"[lean error]\n{err}\n\n")
                trajectory.record_proving_step(
                    run_id=_traj_run,
                    node_id=_traj_node,
                    prover=config.name,
                    round=rnd,
                    branch=sample - 1,
                    phase="compile",
                    gate="compile_fail",
                    prompt={"messages_count": len(messages)},
                    model_output=out[:4000],
                    candidate=candidate[:4000],
                    compile_ok=False,
                    compile_feedback=err,
                    metadata={"sample": sample},
                    temperature=config.temperature,
                    max_tokens=tok,
                    project_root=project_root,
                )
                messages += [
                    {"role": "assistant", "content": out},
                    {
                        "role": "user",
                        "content": f"That proof failed to compile. Lean reported:\n```\n{err}\n```\nFix it and output the full file in one ```lean block.",
                    },
                ]
            if succeeded:
                break

    return RunResult(
        prover=config.name,
        success=succeeded,
        log_path=log_path,
        output_path=attempt_file if succeeded else log_path,
        message=final_msg,
    )


def _ensure_imports(original: str, candidate: str) -> str:
    """Premise injection: re-prepend any `import`/`open` lines from the original goal that the
    model dropped, so a content-self-contained task stays compilable."""
    head = [ln for ln in original.splitlines() if ln.strip().startswith(("import ", "open "))]
    missing = [ln for ln in head if ln.strip() not in candidate]
    return ("\n".join(missing) + "\n" + candidate) if missing else candidate


def _scratch(log_path: Path, candidate: str) -> Path:
    work = log_path.parent / "work"
    work.mkdir(parents=True, exist_ok=True)
    f = work / "candidate.lean"
    f.write_text(candidate, encoding="utf-8")
    return f
