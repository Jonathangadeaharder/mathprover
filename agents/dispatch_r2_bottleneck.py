#!/usr/bin/env python3
"""One-off fire-and-forget dispatch for cr_fill_bottleneck_ge (the last sorry).

Reuses _stage_project from agents.backends.aristotle to stage the lean project, then submits a
CUSTOM narrow prompt (not build_aristotle_prompt) via Project.create_from_directory.
Does NOT poll — monitor with:
    aristotle show <project_id> --task <task_id>
    python3 agents/aristotle_attach.py --project-id <project_id> --task-id <task_id> \
        --node CRN_constant_ratio_runtime --wait
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.backends.aristotle import _stage_project, preflight  # noqa: E402
from config import load_config  # noqa: E402

PROMPT = r"""Close ONLY the `sorry` in `proofs/CRN_constant_ratio_runtime/attempt.lean` at the lemma `cr_fill_bottleneck_ge` (line 651). Do not modify any other lemma, theorem, or file.

The lemma `cr_fill_bottleneck_ge` handles the weak-drift case `¬ (Real.exp 1 * (n : ℝ) / 4 ≤ (n : ℝ) - (j : ℝ))` where the per-step growth rate `ρ = λ(1/4 - z)/μ` falls in the moderate band `(9/8, 2)`. The goal is to show:

  ENNReal.ofReal (1 - 1 / (n : ℝ)) ≤
    hit_prob_within_S (ideal_count_kernel (K := K) G hmu hle h_onemax)
      (cr_lbt_a3a_health n mu (j + 1)) (cr_fill_H n mu j) s

FORBIDDEN approaches (these are the dead-ends from prior runs):
- Do NOT prove a generic ENNReal Lyapunov supermartingale over ∞-valued potentials.
- Do NOT apply `hit_before_S_super` with `v0 = ∞` or `V c = ∞`.
- Do NOT chase false side-goals: `1 ≤ rho^k`, `∞ ≤ rho`, `1 ≤ (k+1)*r`.
- Do NOT attempt the full package or any other lemma. ONLY `cr_fill_bottleneck_ge`.

PRESCRIBED route:
1. The deep band (ρ ≥ 2) is already handled by `CRN_R4_Fill.cr_fill_miss_bound` (the immigration generating-function miss-bound recursion). For the moderate band (9/8 < ρ < 2), you need a sharper multi-step concentration.
2. Use the existing `cr_genfunc_levelvec` and `cr_one_step` (in CRNRobustFillLemmas, namespace CRN_R2_SharpFill) to get the per-step level-(j+1) count generating function.
3. Track the level-(j+1) count growth across `cr_fill_H n mu j` steps. The per-step growth rate ρ > 9/8 gives multiplicative drift. Use a multiplicative Chernoff bound (or the existing `MultiplicativeChernoff` lemmas in the project) to show the count reaches `cr_lbt_tau n` within the horizon with probability ≥ 1 - 1/n, after accounting for reservoir loss via `cr_fixed_j_health_loss_le` (the sharp (3/4)^τ bound).
4. The budget horizon `cr_fill_H n mu j = ceil(2 / r_local_z_corus n (Fin.castSucc ⟨j, hj⟩) + log2 mu)` is tight. Use `cr_fill_F1_seeding` for the initial founder seed and `cr_fill_F2_reservoir` / `cr_fixed_j_health_loss_le` for reservoir preservation across the horizon.
5. The key constant: `cr_fill_H` steps × reservoir loss per step must be ≤ 1/n. The sharp `(3/4)^τ` bound (not the weaker `exp(-9τ/32)`) is needed. The oracle `oracle_climb_fill.py` confirms the budget closes.

FALLBACK: If the sharp Chernoff concentration cannot be formalized for all n, split into finite small-n cases (n ≤ 32) with explicit computation and large-n (n > 32) with the analytic bound. Do NOT weaken the lemma statement.

CONSTRAINTS:
- Output must be axiom-clean: no `sorry`, `admit`, `sorryAx`, `exact?`, `axiom`, or `@[implemented_by]`.
- Only standard axioms `[propext, Classical.choice, Quot.sound]` allowed.
- Mark the completed proof with `-- PROVIDED SOLUTION` immediately above.
- Use existing definitions and helper lemmas already in the file and in `CRNRobustFillLemmas.lean`.
- The file already compiles with 0 errors except for this one sorry. Do not break any other lemma.
"""


async def main() -> int:
    project_root = Path("/Users/jonathangadeaharder/projects/lean-runtime-analysis")
    cfg = load_config(project_root)
    prover = cfg.provers["aristotle"]
    preflight(prover)

    with tempfile.TemporaryDirectory() as td:
        stage_root = Path(td) / project_root.name
        _stage_project(project_root, stage_root)

        from aristotlelib.project import Project  # noqa: E402

        project = await Project.create_from_directory(
            prompt=PROMPT, project_dir=stage_root
        )
        project_id = project.project_id
        tasks, _ = await project.get_tasks(limit=1)
        if not tasks:
            print(f"project_id={project_id}  (no tasks returned)")
            return 1
        task = tasks[0]
        print(f"project_id={project_id}")
        print(f"task_id={task.agent_task_id}")
        print(f"initial_status={task.status.name}")
        print(
            "Monitor with:\n"
            f"  aristotle show {project_id} --task {task.agent_task_id}\n"
            f"  python3 agents/aristotle_attach.py --project-id {project_id} "
            f"--task-id {task.agent_task_id} --node CRN_constant_ratio_runtime --wait"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
