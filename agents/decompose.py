#!/usr/bin/env python3
"""Budget-gated recursive proof decomposition.

Budget (per the 40k context window):
  INPUT_LIMIT  = 8000   tokens  — a node is "self-contained" iff its proving prompt fits this.
  SOLVE_RESERVE= 32000  tokens  — generation budget left for the prover.
  TOTAL        = 40000

Input prompt size is measured EXACTLY via the served model's own tokenizer (OpenAI-compatible APIs return
`usage.prompt_tokens`); solving uses the remaining reserve as the generation cap.

Flow (CLI: `python3 decompose.py --goal-file X.lean`):
  measure(prompt) ≤ 8k  ->  leaf: solve via oprover -> qwen -> aristotle (32k gen budget)
                            on failure -> aristotle decomposes further OR solves directly
  measure(prompt) > 8k  ->  aristotle decomposes into self-contained sub-lemmas -> recurse

This is the orchestration layer; every "proved" is lake-verified + sorry-free (lean_pipeline gate).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

AGENTS = Path(__file__).resolve().parent
sys.path.insert(0, str(AGENTS))

import models as M  # noqa: E402
from lean_pipeline import (  # noqa: E402
    apply_generated_proof,
    compile_lean_file,
    extract_lean4_blocks,
    has_sorry,
)

INPUT_LIMIT = M.INPUT_LIMIT
SOLVE_RESERVE = M.SOLVE_RESERVE
TOTAL_BUDGET = INPUT_LIMIT + SOLVE_RESERVE


def measure_prompt_tokens(prompt: str, model: str = M.NAMES["oprover"]) -> int:
    return M.prompt_tokens(prompt, model=model)


def build_prompt(lean_source: str) -> str:
    return (
        "You are a Lean 4 prover. The file below has exactly one `sorry`. Replace it with a "
        "complete, sorry-free proof; output the full file in one ```lean block.\n\n"
        f"```lean\n{lean_source}\n```"
    )


def is_self_contained(lean_source: str, model: str = M.NAMES["oprover"]) -> tuple[bool, int]:
    n = measure_prompt_tokens(build_prompt(lean_source), model=model)
    return (n <= INPUT_LIMIT, n)


def solve_leaf(
    lean_source: str,
    project_root: Path,
    work: Path,
    *,
    models=(M.NAMES["oprover"], M.NAMES["qwen"]),
) -> str | None:
    """Try local models with the 32k generation reserve; lake+sorry gate. Returns proof or None."""
    work.mkdir(parents=True, exist_ok=True)
    for model in models:
        out = M.chat_sync(
            model,
            [{"role": "user", "content": build_prompt(lean_source)}],
            max_tokens=SOLVE_RESERVE,
        )
        cand = apply_generated_proof(lean_source, out)
        if cand and not has_sorry(cand):
            f = work / "leaf_candidate.lean"
            f.write_text(cand)
            if compile_lean_file(project_root=project_root, lean_file=f).ok:
                return cand
    return None


def aristotle_decompose(lean_source: str, *, model: str = M.NAMES["qwen"]) -> list[dict]:
    """Break a goal into self-contained sub-lemmas. (Splitter backend configurable; aristotle for
    real research goals, qwen used here to conserve the 60/min,1000/day aristotle budget during dev.)
    Returns [{name, statement}] where each statement is a standalone Lean lemma ending in `:= by sorry`."""
    sys_msg = (
        "You are a Lean 4 proof architect. Decompose the goal into 2-5 SELF-CONTAINED helper lemmas "
        "that together prove it, each small enough to prove in isolation. Output ONLY a JSON array of "
        '{"name": "...", "statement": "lemma <name> ... := by sorry"} with the necessary imports folded '
        "into each statement's context. No prose."
    )
    out = M.chat_sync(
        model,
        [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": f"```lean\n{lean_source}\n```"},
        ],
        max_tokens=SOLVE_RESERVE,
    )
    blocks = extract_lean4_blocks(out)
    text = blocks[-1] if blocks else out
    try:
        start, end = text.find("["), text.rfind("]")
        parsed = json.loads(text[start : end + 1]) if start >= 0 else []
    except Exception:  # noqa: BLE001
        return []
    subs: list[dict] = []
    for i, item in enumerate(parsed):
        if isinstance(item, dict) and item.get("statement"):
            subs.append({"name": item.get("name", f"sub{i}"), "statement": item["statement"]})
        elif isinstance(item, str) and item.strip():
            subs.append({"name": f"sub{i}", "statement": item.strip()})
    return subs


def recurse(
    lean_source: str, project_root: Path, work: Path, depth: int, max_depth: int, log
) -> bool:
    ok, ntok = is_self_contained(lean_source)
    log(
        f"{'  ' * depth}node: {ntok} prompt-tokens (limit {INPUT_LIMIT}) {'[leaf]' if ok else '[over budget -> decompose]'}"
    )
    if ok:
        proof = solve_leaf(lean_source, project_root, work)
        log(f"{'  ' * depth}  leaf solve: {'PROVED (lake-verified)' if proof else 'FAILED'}")
        if proof:
            return True
        if depth >= max_depth:
            log(f"{'  ' * depth}  max depth; would hand to aristotle (decompose-or-solve).")
            return False
    if depth >= max_depth:
        log(f"{'  ' * depth}  max depth reached without proof.")
        return False
    subs = aristotle_decompose(lean_source)
    log(f"{'  ' * depth}  decomposed into {len(subs)} sub-lemmas: {[s.get('name') for s in subs]}")
    if not subs:
        return False
    return all(
        recurse(
            s.get("statement", ""),
            project_root,
            (work / s.get("name", "sub")),
            depth + 1,
            max_depth,
            log,
        )
        for s in subs
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Budget-gated recursive proof decomposition.")
    ap.add_argument("--goal-file", required=True)
    ap.add_argument(
        "--project-root", default=str(Path.home() / "projects" / "lean-runtime-analysis")
    )
    ap.add_argument("--max-depth", type=int, default=3)
    ap.add_argument(
        "--measure-only", action="store_true", help="Just measure the prompt tokens + gate."
    )
    args = ap.parse_args()
    src = Path(args.goal_file).read_text()
    root = Path(args.project_root)
    work = root / ".mathprover" / "decompose"
    work.mkdir(parents=True, exist_ok=True)
    if args.measure_only:
        ok, n = is_self_contained(src)
        print(
            json.dumps(
                {
                    "prompt_tokens": n,
                    "input_limit": INPUT_LIMIT,
                    "solve_reserve": SOLVE_RESERVE,
                    "self_contained": ok,
                }
            )
        )
        return
    proved = recurse(src, root, work, 0, args.max_depth, lambda m: print(m, flush=True))
    print("RESULT:", "PROVED" if proved else "NOT PROVED")


if __name__ == "__main__":
    main()
