# Design: R2 Sharp Reservoir Bound + Package Assembly for `cr_climb_fill_package`

## Status

READ-ONLY design. No files modified. Produces the plan for: (a) cherry-picking 8 axiom-clean cloud lemmas from Aristotle project `92ba268e`, (b) a narrow custom Aristotle prompt to close R2 + R4+R5+R6, (c) a fire-and-forget dispatch script, (d) the verification sequence.

Self-review performed: scanned `mistake-log.md` 🔴 entries (last 30 days). Relevant patterns: `POINTWISE-UNIFORM` (union bound discipline for the R4 repeated-trials assembly), `FALSE-DECOMP` (oracle-first for R2 sharp bound — already done, oracle PASSES at `(3/4)^τ`), `2026-06-15 ROUTE-A` (fixed-j tail `ideal_level_vector_count_tail_fixed_j_real_le` is the R2 substrate — same reference frame). No new 🔴 risk if we keep R2's stated RHS and prove a *stronger* interior bound.

---

## Part 1: Cherry-pick Targets for the 8 Cloud Lemmas

### Import-graph constraint (decides placement)

- `attempt.lean` (line 3) imports `CRNRobustFillLemmas`. The reverse edge is FORBIDDEN.
- `CRNRobustFillLemmas.lean` (line 1) imports `ConstantRatioLBT`, which imports `A3aSurvival`, which imports `M10LevelCountCoupling`.
- Therefore: any lemma needed by a `CRNRobustFillLemmas`-resident lemma CANNOT live in `attempt.lean`. Engine/hitting lemmas consumed by robust-fill machinery must live at or below `CRNRobustFillLemmas`.

The cloud returned a single `attempt.lean` containing all 8 lemmas + the (already-present locally, line 3) `import CRNRobustFillLemmas`. Cherry-pick RELOCATES the reusable ones into `CRNRobustFillLemmas.lean` to match the existing R1/R3 architecture (heavy machinery in `CRNRobustFillLemmas`, thin node-specific wrappers in `attempt.lean`).

### Per-lemma placement

| # | Cloud lemma | Local home | Rationale / extends |
|---|---|---|---|
| 1 | `hit_before_S_super` | **`CRNRobustFillLemmas.lean`** (new section, after R3 / before `end`) | General multiplicative-supermartingale hitting bound `1 − hit_before_S K A B (k+1) c ≤ k·r + ρᵏ·V c`. It is an ENGINE lemma. The existing engine lemmas (`hit_prob_within_S_milestone_mul`, `hit_before_S_le_hit_prob_within_S`) live in `attempt.lean` lines 42–196 ONLY because R1/R3 did not need them. If F1/F2/assembly (which go to `CRNRobustFillLemmas`) cite `hit_before_S_super`, it MUST live below `attempt.lean`. **Dependency-check gate (post-download):** `rg -n "hit_before_S_super" <cloud attempt.lean>` — if cited only inside `cr_climb_fill_package`, keep in `attempt.lean` with the other hit_ lemmas (lines ~150–196 region); if cited by any `cr_combined_mass`/`cr_fill_F2_reservoir`/`cr_one_step`, relocate to `CRNRobustFillLemmas.lean`. Default (safe): relocate to `CRNRobustFillLemmas.lean`. |
| 2 | `cr_slot_ge_eq_coea` | **`CRNRobustFillLemmas.lean`** | Slot-weight ↔ `coea_measure` bridge. Direct sibling of the private helpers already copied verbatim at `CRNRobustFillLemmas.lean:108-146` (`ideal_offspring_slot_weight_ge_sum_eq_coea_measure`, `ideal_offspring_slot_weight_ge_sum_toReal_eq`). Land adjacent to those, same `CRN_R1_FixedJFounderMass` namespace (or a new `CRN_RobustFillBridges` namespace). |
| 3 | `cr_combined_mass` | **`CRNRobustFillLemmas.lean`** | Immigration-aware per-slot mass at level `j+1` (retention growth + frontier immigration). Refines `a3a_keep_mass_ge` at `A3aSurvival.lean:126`. Reusable across the fill DAG → robust-fill module. |
| 4 | `cr_genfunc_levelvec` | **`CRNRobustFillLemmas.lean`** | Immigration generating-function bound. Extends `a3a_genfunc_levelvec` at `A3aSurvival.lean:205-213`. Same module-level (A3aSurvival is importable from CRNRobustFillLemmas via ConstantRatioLBT). |
| 5 | `cr_one_step` | **`CRNRobustFillLemmas.lean`** | One-step kernel form of the immigration generating function. Extends `a3a_one_step` at `A3aSurvival.lean:444-450`. Pairs with `cr_genfunc_levelvec`. |
| 6 | `cr_fill_F1_seeding` | **`attempt.lean`** (above `cr_climb_fill_package`, near `cr_fill_H` at line 294 / `cr_one_shot_founder_to_health_ge` at line 351) | Per-generation founder seeding `(K c){≥1 at level j+1} ≥ min(τ·z,1)/2`. Node-specific: consumes the banked R1 `cr_fixed_j_founder_next_ge` (`CRNRobustFillLemmas.lean:407`, re-exported as `attempt.lean:329`). Pairs with `cr_fill_H` schedule (line 294). |
| 7 | `cr_fill_F2_reservoir` | **`attempt.lean`** (next to F1) — BUT see R2 note | Per-generation reservoir preservation `≤ exp(−9τ/32)`. This is the WEAK bound (the DIRECTION doc WARNING at lines 109-114 flags `exp(−9τ/32)` as insufficient for the oracle in small-n/large-μ). It is a stepping-stone, NOT the final R2. Land it in `attempt.lean` as a record of the weak attempt; the sharp R2 (`cr_fixed_j_health_loss_le`) supersedes it. If `cr_fill_F2_reservoir` is cited by `cr_combined_mass`/`cr_one_step` (i.e. needed at the robust-fill layer), relocate to `CRNRobustFillLemmas.lean` instead. |
| 8 | `cr_slot_prod_le_one` | **`CRNRobustFillLemmas.lean`** | Finiteness helper (slot-weight product `≠ ⊤` / `≤ 1`). Sibling of `ideal_offspring_slot_weight_pmf_ne_top` at `CRNRobustFillLemmas.lean:178-191`. Same region. |

### Existing-lemma anchors (exact file:line) the cherry-pick must preserve

- `a3a_keep_mass_ge` — `A3aSurvival.lean:126` (consumed by `cr_combined_mass`).
- `a3a_genfunc_levelvec` — `A3aSurvival.lean:205` (extended by `cr_genfunc_levelvec`).
- `a3a_one_step` — `A3aSurvival.lean:444` (extended by `cr_one_step`).
- `a3a_miss_bound` — `A3aSurvival.lean:473`, `a3a_iteration_bound` — `A3aSurvival.lean:269` (the supermartingale comparison `hit_before_S_super` mirrors).
- `ideal_level_vector_count_tail_fixed_j_real_le` — `M10LevelCountCoupling.lean:2666` (the R2 substrate; gives `exp(−λ·m/(32μ))`, weak).
- `ideal_count_kernel_ge_count_mass` — `M10LevelCountCoupling.lean:2739` (kernel↔level-vector mass bridge, consumed by `cr_one_step`).
- `cr_fixed_j_founder_next_ge` — `CRNRobustFillLemmas.lean:407` (R1, re-exported `attempt.lean:329`; consumed by F1).
- `cr_lbt_a3a_survival_ge_positive` — `CRNRobustFillLemmas.lean:482` (R3, consumed by F1→health).
- `cr_fill_H` / `cr_fill_H_eq_of_lt` / `cr_fill_H_lower` / `cr_fill_H_upper` / `cr_fill_H_pos` — `attempt.lean:294-323` (the schedule; F1/F2/assembly build on these).
- `cr_one_shot_founder_to_health_ge` — `attempt.lean:351` (the single-attempt core; the package amplifies this).
- `cr_climb_compose` — `attempt.lean:246` (the consumer of the package's `hfill`).
- `ideal_count_hit_prob_constant_ratio` — `attempt.lean:448` (downstream, already wired, calls `cr_climb_fill_package` at line 460).

### `import` / `open` state of `CRNRobustFillLemmas.lean`

Current (lines 1-5): `import ConstantRatioLBT`; `open MeasureTheory ProbabilityTheory ProbabilityTheory.Kernel Real Set Finset`; `open scoped ENNReal BigOperators`; `open Classical M10 A3aSurvival`. The cloud's `import CRNRobustFillLemmas` (in attempt.lean) is ALREADY present locally (line 3) — no new import line needed in either file. The 8 lemmas need no new `open` (all namespaces already open). The `cr_slot_prod_le_one` / `cr_slot_ge_eq_coea` helpers may need `MultiplicativeChernoff` (already in scope via `M10`) — verify post-download.

### Cherry-pick procedure (no Lean execution in this design; for the plan)

1. `aristotle download 92ba268e-534d-4cc6-b9d8-0c2fe521c9de --destination <scratch>/r2_cloud` (download is free; Codex credits only gate `submit`).
2. Extract; locate the returned `attempt.lean`; `diff` against local `attempt.lean:1-546`.
3. For each of the 8 lemmas: copy the decl + its `private` helpers (if any) to the target file per the table above. Preserve docstrings.
4. Run the verification block (Part 4) after EACH file edit (incremental — avoids 9k-line cascade diagnostics).
5. `#print axioms` on each of the 8 by name; record in `references/mistake-log.md` `[ARISTOTLE]` block.

---

## Part 2: Narrow Aristotle Prompt for R2 + Assembly

### The R2 target — which RHS?

- `DIRECTION_ROBUST_FILL.md:95-101` pins R2's stated RHS: `ENNReal.ofReal ((3 / 4 : ℝ) ^ cr_lbt_tau n)`.
- `oracle_climb_fill.py:72` checks `(3/4)^tau` and PASSES the grid (lines 33-35, `n=2..512`).
- The public fixed-j tail `ideal_level_vector_count_tail_fixed_j_real_le` (`M10LevelCountCoupling.lean:2666`) yields `exp(−λ·m/(32μ))`; at `λ/μ=9, m=τ` this is `exp(−9τ/32) ≈ 0.7548^τ > (3/4)^τ` — **too weak** (DIRECTION WARNING lines 109-114).
- Aristotle's own diagnosis: generating function at deviation `t=4/9` + Markov yields `exp(−τ/3)` (exp(−1/3)≈0.7165 < 0.75), which DISCHARGES `(3/4)^τ` since `exp(−τ/3) ≤ (3/4)^τ ⟺ exp(1/3) ≥ 4/3` (true; `Real.exp_one_third_ge_four_thirds`-style lemma, derivable from `exp 1 ≥ 4/3`).

**Decision:** R2 statement stays EXACTLY as in `DIRECTION_ROBUST_FILL.md:95-101` (RHS `(3/4)^cr_lbt_tau n`). The PROOF establishes the stronger interior bound `exp(−(1/3)·(cr_lbt_tau n : ℝ))` then relaxes to `(3/4)^τ` via `Real.exp_neg_one_third_le_three_quarters_pow` (a new helper, or `exp_le_pow` chain). This keeps the statement contract intact (no E2 weakening) and matches the oracle.

### Derivation of the sharp bound (pen-and-paper, for the prompt's "follow this route")

Let `τ = cr_lbt_tau n`, `m = stateGeCount c j ≥ τ`, `ρ = λ/(4μ) ≥ 9/4` (from `hsel : 9 ≤ λ/μ`). The bad event is `B = {N' < τ}` where `N' = stateGeCount c' j` under one `ideal_count_kernel` step.

1. `a3a_one_step` (`A3aSurvival.lean:444`) / banked `cr_one_step`: for `t ∈ [0,1]`,
   `E[t^{N'} · 1_{N'<τ}] ≤ exp(−(1−t)·ρ·m) ≤ exp(−(1−t)·ρ·τ)`.
2. Markov: `1_{N'<τ} ≤ t^{N'−(τ−1)} · 1_{N'<τ}` (since `N' ≤ τ−1 ⟹ t^{N'} ≥ t^{τ−1}` for `t∈(0,1]`). Hence
   `P(N' < τ) ≤ E[t^{N'} · 1_{N'<τ}] / t^{τ−1} ≤ t^{−(τ−1)} · exp(−(1−t)·ρ·τ)`.
3. Optimize `t`: minimize `g(t) = −(τ−1)·log t − (1−t)·ρ·τ`. `g'(t) = −(τ−1)/t + ρ·τ = 0 ⟹ t = (τ−1)/(ρ·τ) ≈ 1/ρ ≈ 4/9` (at `ρ=9/4`). Use `t = 4/9` (the cloud's deviation).
4. At `t = 4/9, ρ = 9/4`: per-`τ` base `= exp(−(5/9)·(9/4)) / (4/9) = exp(−5/4)·(9/4)`. `log = −5/4 + log(9/4) = −1.25 + 0.8109 = −0.4391`. Base `≈ 0.6447 < exp(−1/3) ≈ 0.7165 < 3/4`. So `P(B) ≤ (0.6447)^{τ-ish} ≤ exp(−τ/3) ≤ (3/4)^τ`.
5. Bridge to kernel mass: `ideal_count_kernel_ge_count_mass` (`M10LevelCountCoupling.lean:2739`) turns the level-vector expectation into `ideal_count_kernel c {c' | ¬ τ ≤ stateGeCount c' j}`.

This is the route the prompt PRESCRIBES. It reuses `a3a_one_step` + `ideal_count_kernel_ge_count_mass` (both public, axiom-clean) plus the banked `cr_one_step` (which wraps `a3a_one_step` in the immigration form). No new axiom.

### The exact prompt text

```
GOAL: Close the single `sorry` in `proofs/CRN_constant_ratio_runtime/attempt.lean` at the lemma `CRNRuntime.cr_climb_fill_package` (declared ~line 415, sorry at ~line 427). Do NOT modify any other file. Do NOT modify any theorem/lemma STATEMENT. The 8 helper lemmas from the previous run are ALREADY PRESENT in this staged tree (in `CRNRobustFillLemmas.lean` and in `attempt.lean` above the target). Build on them; do NOT re-prove them.

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
  Use `m9a_level_budget`, `m9a_two_div_z_le`, `cr_fill_H_lower`/`cr_fill_H_upper` (attempt.lean:304-315).
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
```

---

## Part 3: Dispatch Mechanism — `agents/dispatch_r2_sharp.py`

Read `agents/backends/aristotle.py` for the real API (do NOT invent). Confirmed in the file:
- `from aristotlelib.agent_task import TaskStatus as AristotleTaskStatus` (line 96) — not needed for fire-and-forget.
- `from aristotlelib.project import Project` (line 97).
- `Project.create_from_directory(prompt=..., project_dir=stage_root)` (line 126) — async, returns a Project.
- `project.project_id` (line 127).
- `project.get_tasks(limit=1)` (line 130) — async, returns `(tasks, _)`.
- `task.agent_task_id`, `task.status.name` (line 142).
- `_stage_project(project_root, stage_root)` (line 47) — module-level function, copies the lean tree.
- `from config import ProverConfig` (line 14); `preflight(config)` (line 34) checks env + binary.

The dispatch script reuses `_stage_project` (importable from `agents.backends.aristotle`) and calls `Project.create_from_directory` directly with the custom prompt. It does NOT poll (fire-and-forget); prints `project_id` + `task_id` for `aristotle show`.

```python
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

# Make the mathprover package importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.backends.aristotle import _stage_project, preflight  # noqa: E402
from config import load_config  # noqa: E402

PROMPT = r"""<paste the Part 2 prompt text verbatim here>"""


async def main() -> int:
    project_root = Path("/Users/jonathangadeaharder/projects/lean-runtime-analysis")
    cfg = load_config(project_root)
    prover = cfg.provers["aristotle"]  # type=cloud, command=aristotle, requires_env=[ARISTOTLE_API_KEY]
    preflight(prover)  # checks ARISTOTLE_API_KEY env + `aristotle` binary on PATH

    attempt_file = (
        project_root / "proofs" / "CRN_constant_ratio_runtime" / "attempt.lean"
    )

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
```

Notes for the implementer (the plan file will carry these):
- `ProverConfig` constructor RESOLVED (read `agents/config.py`): it is a plain dataclass with no `.load()` method. The real loader is `load_config(project_root)` (from `config.py`) returning a `MathProverConfig` with a `.provers` dict; the aristotle prover is `cfg.provers["aristotle"]` (confirmed in `lean-runtime-analysis/mathprover.toml` `[provers.aristotle]`: `type=cloud, command=aristotle, requires_env=[ARISTOTLE_API_KEY], poll_interval_seconds=30, max_wait_minutes=120`). The script above uses this loader. `preflight(prover)` then checks the env var + binary.
- The staging tempdir is deleted on script exit (the `with tempfile.TemporaryDirectory()` block). Aristotle holds its own server-side copy after `create_from_directory` returns — the local staging tree is only needed for the upload, not for monitoring. This matches `_run_aristotle_async` (line 106-128) which also uses a tempdir.
- Fire-and-forget is intentional: a long Aristotle run must not block the shell. Re-attach via `aristotle_attach.py --wait` (referenced at `aristotle.py:158`).
- Record the submission in `references/mistake-log.md` under `[ARISTOTLE]` (project ID, prompt hash, outcome) per §2b hygiene.

---

## Part 4: Verification Sequence

### After cherry-pick (each of the 8 lemmas banked)

Run after EACH file edit to localize failures (per OS §3 "module hygiene" — avoid 9k-line cascade):

```bash
cd /Users/jonathangadeaharder/projects/lean-runtime-analysis

# 1. Compile the touched file (fast feedback, no full build).
lake env lean CRNRobustFillLemmas.lean
lake env lean proofs/CRN_constant_ratio_runtime/attempt.lean

# 2. Build the module + reverse deps (CRNRuntime depends on both).
lake build LBTCoupling

# 3. Axiom census on each banked lemma (all 8) — must be [propext, Classical.choice, Quot.sound].
#    (Replace the names as confirmed post-download.)
for L in \
  hit_before_S_super cr_slot_ge_eq_coea cr_combined_mass cr_genfunc_levelvec \
  cr_one_step cr_fill_F1_seeding cr_fill_F2_reservoir cr_slot_prod_le_one ; do
  echo "=== $L ==="
  lake env lean --run -e "#print axioms CRN_R1_FixedJFounderMass.$L" 2>/dev/null \
    || lake env lean --run -e "#print axioms CRN_R2_FixedJHealthLoss.$L" 2>/dev/null \
    || lake env lean --run -e "#print axioms CRNRuntime.$L"
done

# 4. Forbidden-placeholder grep over both touched files (zero matches required).
rg -n "sorry|admit|sorryAx|exact\?|axiom|@\[implemented_by\]" \
  CRNRobustFillLemmas.lean proofs/CRN_constant_ratio_runtime/attempt.lean
```

Note on `#print axioms`: the project accepts the `[propext, Classical.choice, Quot.sound]` triple. If a banked lemma transitively depends on the R1/R3 lemmas (which are already axiom-clean), the cone stays clean. The `#print axioms` of a downstream decl lists the UNION of its dependency cone, so it suffices to check the 8 new decls + the two downstream theorems.

### After Aristotle returns R2 + assembly (final gate — `DIRECTION_ROBUST_FILL.md:205-222`)

```bash
cd /Users/jonathangadeaharder/projects/lean-runtime-analysis

# A. Compile the target file.
lake env lean proofs/CRN_constant_ratio_runtime/attempt.lean

# B. Build module + reverse deps.
lake build LBTCoupling

# C. Axiom cone of the closed lemma AND the top theorem — both must be exactly
#    [propext, Classical.choice, Quot.sound].
lake env lean --run -e "
import proofs/CRN_constant_ratio_runtime/attempt.lean
#print axioms CRNRuntime.cr_climb_fill_package
#print axioms CRNRuntime.crn_runtime_onemax_constant_ratio
"

# D. Forbidden-placeholder grep — zero matches in attempt.lean (the sorry at line 427 must be GONE).
rg -n "sorry|admit|sorryAx|exact\?|axiom|@\[implemented_by\]" \
  proofs/CRN_constant_ratio_runtime/attempt.lean CRNRobustFillLemmas.lean

# E. Oracle re-run (independent of Lean) — must still PASS with the (3/4)^tau constant.
python3 proofs/CRN_constant_ratio_runtime/oracle_climb_fill.py --max-n 512
```

Expected outputs:
- `lake env lean … attempt.lean`: exit 0, no errors.
- `lake build LBTCoupling`: green.
- `#print axioms CRNRuntime.cr_climb_fill_package` → `[propext, Classical.choice, Quot.sound]`.
- `#print axioms CRNRuntime.crn_runtime_onemax_constant_ratio` → `[propext, Classical.choice, Quot.sound]`.
- `rg` grep → no output (zero forbidden tokens).
- `oracle_climb_fill.py` → `PASS: product-level route fits the checked grid.`

### Definition of Done checklist (per OS §7)

- [ ] Statement Contract §1 passed for R2 (`cr_fixed_j_health_loss_le`): semantic payload is the kernel mass of `{s' | ¬ τ ≤ stateGeCount s' j}` — NOT vacuous (fails the `use 1; norm_num` test: RHS `(3/4)^τ < 1` for τ ≥ 1, and the LHS is a genuine per-step loss probability). Trivializing-hypothesis model exhibited: `λ/μ = 9, μ ≥ τ, stateGeCount c j = τ` — noise present (offspring sampling is stochastic), bound non-trivial.
- [ ] Pen-and-paper chain + oracle committed and passing (`oracle_climb_fill.py` already PASSES; sharp `exp(-τ/3)` is STRONGER, so oracle still passes).
- [ ] `lake build` green incl. reverse deps; sorry/axiom cone listed (`[propext, Classical.choice, Quot.sound]`).
- [ ] Linter PASS, no suppressions, no `have _ := h` discard patterns.
- [ ] Ledger (`paper_theorems.json`) + `status.md` same-commit; honest status (REAL_PROVEN only after the §4 block passes; PARTIAL with "modulo R2 sharp interior" otherwise). `required_conclusion_tokens` set to `["cr_climb_fill_package", "crn_runtime_onemax_constant_ratio"]`.
- [ ] Open items + "NOT claimed" list in the report.
- [ ] Zero contract-statement edits without planner sign-off (R2 RHS stays `(3/4)^cr_lbt_tau n`; the sharp `exp(-τ/3)` is INTERIOR to the proof, not in the statement — no E2 breach).

---

## Open Items / Risks

1. **`hit_before_S_super` placement is download-dependent.** Resolved by the post-download `rg` gate in Part 1. If the cloud's `cr_fill_F2_reservoir` or `cr_combined_mass` cites it, it MUST move to `CRNRobustFillLemmas.lean` (import graph). Default: relocate there.
2. **`ProverConfig` constructor.** RESOLVED. `load_config(project_root).provers["aristotle"]` is the real loader (`config.py:90`, plain dataclass). The dispatch script in Part 3 uses it. No API guessing.
3. **The `exp(-1/3) ≤ 3/4` numeric lemma.** Needs a proof. Pattern exists in `mathlib-api.md` (2026-06-16): `Real.exp_lt_exp.mpr` + `Real.log` bounds. Specifically: `exp(1/3) ≥ 4/3 ⟺ log(4/3) ≤ 1/3`. `log(4/3) = log 4 - log 3 ≤ 2·log 2 - log 3`; bound `log 2 < 0.7` and `log 3 > 1` (both in mathlib ExponentialBounds) gives `log(4/3) < 1.4 - 1 = 0.4 > 1/3`?? — NEEDS CHECK. Actually `log(4/3) ≈ 0.2877 < 1/3 ≈ 0.3333`, so the inequality is TRUE but the crude bound `log 2 < 0.7, log 3 > 1` gives `log(4/3) < 0.4` which is NOT tight enough. The plan must find tighter mathlib bounds (e.g. `Real.log_two_lt_d9` = `log 2 < 0.6932` and a `log 3` lower bound) OR prove `exp(1/3) ≥ 4/3` directly via the Taylor series / `exp 1 ≥ 8/3`-style. This is a minor numeric-lemma risk; if Aristotle cannot close it, the fallback is the `(9/4)·exp(-5/4) ≤ 3/4` direct numeric (base ≈ 0.6447 < 0.75, more slack). Flagged for the prompt's numeric helper.
4. **R4 union bound.** The repeated-trials recursion must pay the union bound over `H = cr_fill_H n mu j` attempts EXPLICITLY (mistake-log POINTWISE-UNIFORM). The prompt forbids pointwise-as-uniform; if Aristotle produces a proof without the explicit `H * eps` term, reject and re-submit. This is the highest-risk step for a hidden false-proof.
5. **R5 arithmetic.** The oracle PASSES, but the formal arithmetic (`∑ cr_fill_H ≤ ⌊Φ_max⌋`, `p^n ≥ 1/4`) may need `m9a_level_budget` / `m9a_two_div_z_le` lemmas not yet located. If these don't exist, escalate E3 (do NOT improvise an axiom). Grep `M10LevelCountCoupling.lean` / `ConstantRatioLBT.lean` for `m9a_level_budget` first.
