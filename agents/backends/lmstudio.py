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
from config import ProverConfig  # noqa: E402
from lean_pipeline import apply_generated_proof, compile_lean_file, forbidden_placeholders  # noqa: E402


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


def _chat(base_url: str, model: str, messages: list[dict], *, temperature: float,
          max_tokens: int, timeout_s: int) -> str:
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
        for sample in range(1, config.max_attempts + 1):
            messages = [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": f"```lean\n{original}\n```"},
            ]
            for rnd in range(config.correction_rounds + 1):
                log.write(f"## sample {sample} round {rnd}\n")
                log.flush()
                try:
                    out = _chat(base_url, model, messages, temperature=config.temperature,
                                max_tokens=tok, timeout_s=timeout_s)
                except Exception as exc:  # noqa: BLE001 — log + try next sample
                    log.write(f"[chat error] {exc}\n\n")
                    break
                candidate = apply_generated_proof(original, out)
                if candidate is None:
                    log.write("[no lean block extracted]\n\n")
                    messages += [
                        {"role": "assistant", "content": out},
                        {"role": "user", "content": "No ```lean block found. Output the full file in one ```lean block."},
                    ]
                    continue
                forbidden = forbidden_placeholders(candidate)
                if forbidden:
                    log.write(f"[candidate still contains forbidden placeholders {forbidden} — rejected]\n\n")
                    messages += [
                        {"role": "assistant", "content": out},
                        {"role": "user", "content": "Your proof still contains placeholders (`sorry`, `admit`, `exact?`, `sorryAx`, or `axiom`). Provide a complete proof with none."},
                    ]
                    continue
                candidate = _ensure_imports(original, candidate)
                result = compile_lean_file(project_root=project_root, lean_file=_scratch(log_path, candidate))
                if result.ok and not forbidden_placeholders(candidate):
                    attempt_file.write_text(candidate, encoding="utf-8")
                    log.write(f"[VERIFIED] sample {sample} round {rnd}: lake-clean, placeholder-free\n")
                    succeeded = True
                    final_msg = f"{config.name}: verified (sample={sample}, round={rnd})"
                    break
                err = result.error_excerpt(2000)
                log.write(f"[lean error]\n{err}\n\n")
                messages += [
                    {"role": "assistant", "content": out},
                    {"role": "user", "content": f"That proof failed to compile. Lean reported:\n```\n{err}\n```\nFix it and output the full file in one ```lean block."},
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
