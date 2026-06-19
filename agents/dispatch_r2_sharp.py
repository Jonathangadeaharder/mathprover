#!/usr/bin/env python3
"""One-off fire-and-forget dispatch for the R2 sharp bound + cr_climb_fill_package assembly.

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

PROMPT = r"""GOAL: Close the single `sorry` in `proofs/CRN_constant_ratio_runtime/attempt.lean` at the lemma `CRNRuntime.cr_climb_fill_package` (declared at line 567, sorry at line 579). Do NOT modify any other file. Do NOT modify any theorem/lemma STATEMENT. The 8 helper lemmas from the previous run are ALREADY PRESENT in this staged tree (in `CRNRobustFillLemmas.lean` and in `attempt.lean` above the target). Build on them; do NOT re-prove them.

The staged `attempt.lean` already imports `CRNRobustFillLemmas`, `CRNRuntime`, `ConstantRatioLBT`.

STEP 1 — Prove R2 (sharp fixed-j reservoir loss). Add a lemma (place it in `CRNRobustFillLemmas.lean`, namespace `CRN_R2_FixedJHealthLoss`, since `attempt.lean` cannot be imported by robust-fill machinery) with EXACTLY this statement:

  lemma cr_fixed_j_health_loss_le {β : Type} [Fintype β]
      [MeasurableSpace β] [DiscreteMeasurableSpace β] [Nonempty β]
      {n mu lambda K : ℕ}
      (G : RLocalGame (BitString n) β) (hn : n ≥ 2) (hmu : mu > 0)
      (hle : mu ≤ lambda) (hlambda : 0 < lambda)
      (h_onemax : ∀ z, G.f z = onemax_fitness n z)
      (hsel : (9 : ℝ) ≤ (lambda : ℝ) / (mu : ℝ))
      (h_mu_tau : cr_lbt_tau n ≤ mu)
      (c : IdealCountState n mu) (j : ℕ)
      (hs : cr_lbt_tau n ≤ stateGeCount c j) :
      (ideal_count_kernel (K := K) G hmu hle h_onemax c)
        {s' | ¬ cr_lbt_tau n ≤ stateGeCount s' j}
        ≤ ENNReal.ofReal ((3 / 4 : ℝ) ^ cr_lbt_tau n) := by
    sorry

Do NOT change the RHS. The RHS `(3/4)^cr_lbt_tau n` is the contract.

PRESCRIBED ROUTE (follow exactly; this is the route that closes):

  Let τ := cr_lbt_tau n, m := stateGeCount c j (so τ ≤ m), ρ := (lambda : ℝ)/(4*(mu : ℝ)) ≥ 9/4 (from hsel).
  Bad event B := {c' | ¬ τ ≤ stateGeCount c' j} = {c' | stateGeCount c' j < τ}.

  (a) Use `A3aSurvival.a3a_one_step` (or the banked `cr_one_step`) at t = 4/9 :
      ∫⁻ c', (if τ ≤ stateGeCount c' j then 0 else ENNReal.ofReal ((4/9) ^ stateGeCount c' j))
        ∂(ideal_count_kernel K G hmu hle h_onemax c)
      ≤ ENNReal.ofReal (Real.exp (-((1 - 4/9) * (lambda : ℝ) * (stateGeCount c j : ℝ) / (4 * (mu : ℝ)))))
      ≤ ENNReal.ofReal (Real.exp (-((5/9) * (9/4) * (τ : ℝ))))   -- using ρ ≥ 9/4, m ≥ τ
      = ENNReal.ofReal (Real.exp (-(5/4 : ℝ) * (τ : ℝ))).

  (b) Markov / Chebyshev flip: on B, stateGeCount c' j ≤ τ - 1, so (4/9)^{stateGeCount c' j} ≥ (4/9)^{τ-1}.
      Hence 1_B ≤ (4/9)^{-(τ-1)} · (4/9)^{stateGeCount c' j}.
      Integrate: μ(B) ≤ (4/9)^{-(τ-1)} · (the bound from (a)).

  (c) Assemble: μ(B) ≤ (9/4)^{τ-1} · Real.exp (-(5/4)·τ).
      Per-τ base = (9/4) · exp(-5/4) = exp(log(9/4) - 5/4).
      Prove the numeric lemma: exp(log(9/4) - 5/4) ≤ exp(-1/3) ≤ 3/4.
        - exp(log(9/4) - 5/4) ≤ exp(-1/3) ⟺ log(9/4) - 5/4 ≤ -1/3 ⟺ log(9/4) ≤ 23/12 ≈ 1.9167 (true; log(9/4)≈0.811).
        - exp(-1/3) ≤ 3/4 ⟺ exp(1/3) ≥ 4/3 (true; derivable from Real.exp_one_gt_d9 / exp_le/exp_lt_exp + log bounds, see mathlib-api 2026-06-16 pattern).
      Conclude μ(B) ≤ exp(-τ/3) ≤ (3/4)^τ = ENNReal.ofReal ((3/4)^τ).

  (d) Bridge to kernel mass: use `M10LevelCountCoupling.ideal_count_kernel_ge_count_mass` (and the
      `a3a_kernel_count_expectation` form in A3aSurvival) to express the kernel mass of the SET
      {c' | ¬ τ ≤ stateGeCount c' j} as the level-vector expectation in (a). The set-mass pattern is
      in proof-patterns.md (2026-06-15 "mass-of-a-set on a discrete-fintype weighted-dirac kernel"):
      `rw [kernel_eval, measure_sum_apply]` then per-term indicator. Do NOT fight `measure_biUnion`.

  (e) Edge cases: τ = 0 is impossible (cr_lbt_tau_pos : 1 ≤ cr_lbt_tau n, attempt.lean:221). Handle
      τ = 1 by direct numeric check if the Markov flip's (τ-1) exponent needs it.

STEP 2 — R4: repeated-trials recursion with safe reservoir. Add `hit_prob_within_S_repeated_attempts_with_bad`
  (generic Markov form) in `CRNRobustFillLemmas.lean`. Concrete instance per DIRECTION_ROBUST_FILL.md:156-166:
    Safe = cr_lbt_a3a_health n mu j, Founder = {s | 1 ≤ stateGeCount s (j+1)},
    Target = cr_lbt_a3a_health n mu (j+1), q = min(τ·z_j,1)/2, r = 5/9, eps = (3/4)^τ, H = cr_fill_H n mu j.
  Use the banked `hit_prob_within_S_milestone_mul` (attempt.lean:107) + `hit_prob_within_S_mono_depth`.
  Pay the union bound EXPLICITLY over the H attempts (DIRECTION forbids pointwise-as-uniform — see
  mistake-log POINTWISE-UNIFORM). The bad-event term is `H * eps` (capped at 1).

STEP 3 — R5: arithmetic package. Prove in `attempt.lean`:
    `cr_fill_budget_sum_le_phi : 1 + ∑ j ∈ Finset.range n, cr_fill_H n mu j ≤ ⌊m9a_phi_max_real hn hmu⌋₊`
    `cr_fill_phase_success_pow : (1/4 : ℝ) ≤ p ^ n`  (p = uniform lower bound from R4)
  Use `m9a_level_budget`, `m9a_two_div_z_le`, `cr_fill_H_lower`/`cr_fill_H_upper` (attempt.lean:304-310).
  The oracle `oracle_climb_fill.py` already PASSES with these constants — the arithmetic is TRUE.

STEP 4 — R6: assembly. Set Hs := cr_fill_H n mu, p := <proved uniform bound>. Close
  `cr_climb_fill_package` using R1 (cr_fixed_j_founder_next_ge, attempt.lean:329) + R2 (cr_fixed_j_health_loss_le)
  + R3 (cr_lbt_a3a_survival_ge_positive, CRNRobustFillLemmas.lean:482) + R4 + R5. Provide `Hs` and `p`
  via `use` / `exists` with the proved witnesses.

HARD CONSTRAINTS:
- AXIOM-CLEAN. No `sorry`, `admit`, `sorryAx`, `exact?`, `axiom`, `@[implemented_by]`. Final
  `#print axioms CRNRuntime.cr_climb_fill_package` and `#print axioms CRNRuntime.crn_runtime_onemax_constant_ratio`
  must be exactly `[propext, Classical.choice, Quot.sound]`.
- Mark the proof region of `cr_climb_fill_package` with a comment `-- PROVIDED SOLUTION` immediately
  above the completed proof (project convention, see agents/prompts.py:76).
- Do NOT assume `h_c9_le`. Do NOT call `m9a_ideal_count_runtime`. Do NOT use the quarantined LBT theorem.
  Do NOT introduce a new `axiom`.

EXPLICITLY FORBIDDEN dead-ends (these all failed in the previous run):
- Generic ENNReal Lyapunov supermartingale over ∞-valued potentials. The potential V c must be FINITE
  (≠ ⊤) before any `.toReal` (⊤.toReal = 0 silently destroys conclusions — mistake-log ENNReal.toReal).
- `hit_before_S_super` applied with `v0 = ⊤` or `V c = ⊤`. The supermartingale bound is only valid for
  finite V; if V can be ⊤ the conclusion is vacuous.
- False side-goals: `1 ≤ ρ^k`, `∞ ≤ ρ`, `1 ≤ (k+1)*r`. These were artifacts of ∞-valued potentials;
  do NOT attempt to prove them — they indicate a type/∞ confusion, fix the root cause instead.
- Monolithic full-package attacks. Decompose as R2 → R4 → R5 → R6 (the DIRECTION doc's 6-node DAG;
  R1, R3 are already done). One lemma per node, then one assembly lemma.

FALLBACK (only if the sharp exp(-τ/3) interior bound cannot be formalized after 30 min of attempt):
- Do NOT weaken the R2 RHS. Instead, SPLIT finite small-n cases: prove `cr_fixed_j_health_loss_le` for
  `n ≥ N0` (some explicit bound, e.g. N0 = 16) via the sharp bound, and handle `n < N0` by explicit
  finite case enumeration (each `n` checked by `norm_num` + the existing tail lemma). Record a
  replacement oracle entry in `oracle_climb_fill.py` documenting the split. The statement stays
  identical; only the proof strategy branches on `n`.

The oracle `proofs/CRN_constant_ratio_runtime/oracle_climb_fill.py` (run with `--max-n 512`) PASSES with
`(3/4)^τ` as the reservoir-loss constant. The target is arithmetically sound; the work is formal plumbing.
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

        project = await Project.create_from_directory(prompt=PROMPT, project_dir=stage_root)
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
