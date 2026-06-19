#!/usr/bin/env python3
"""Dispatch Aristotle for Co-Evolutionary Level-Based Theorem (Lehre 2022, arXiv:2206.15238).

This mechanizes the two-population LBT framework and the product binomial drift lemma.
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.backends.aristotle import _stage_project, preflight
from config import load_config

PROMPT = r"""Mechanize the Co-Evolutionary Level-Based Theorem in Lean 4.

## Context
From "Runtime Analysis of Competitive co-Evolutionary Algorithms for Maximin
Optimisation of a Bilinear Function" (Lehre, 2022, arXiv:2206.15238).

The co-evolutionary LBT (Theorem 3) extends the classical single-population LBT
to two populations P ∈ X^λ, Q ∈ Y^λ with product-space levels (A_j × B_j).

## Existing Infrastructure
The project already has:
- DriftTheorems/AdditiveDrift.lean (FULL, sorry-free) — `additive_drift_theorem`
- DriftTheorems/NegativeDrift.lean (FULL, sorry-free)
- CoEALevelBased.lean (399 lines) — `ZeroSumGame`, `CoEAState`, `CoEALevelPartition`, `LevelBasedBound`
- LBTCoupling.lean (9424 lines) — `ConditionG1`, `ConditionG2`, `ConditionG3`, kernel drift framework
- LBTPreconditions.lean — `ConditionG1`, `ConditionG2`, `ConditionG3` (non-measure-theoretic)
- GameTheoryMinimax.lean — `MixedStrategy`, `minimax_existence`
- MultiplicativeChernoff.lean — `chernoff_lower_tail_explicit`
- Hoeffding.lean — `hoeffding_inequality_iid_bounded`

## Task
Create DriftTheorems/CoEvolutionaryLBT.lean that mechanizes:

### 1. Two-population framework
- Two populations P : Fin λ → X, Q : Fin λ → Y
- Product-space levels: A_j ⊆ X, B_j ⊆ Y for j ∈ [m]
- Current level: j := max{i ∈ [m] | |(P × Q) ∩ (A_i × B_i)| ≥ γ₀λ²}
- Product count process: Z_t := |(P_t × Q_t) ∩ (A × B)|

### 2. Co-evolutionary LBT (Theorem 3)
Preconditions:
- (G1): Pr(x ∈ A_{j+1}) · Pr(y ∈ B_{j+1}) ≥ z_j
- (G2a): If |(P×Q) ∩ (A_{j+1} × B_{j+1})| ≥ γλ², then Pr(x ∈ A_{j+1}) · Pr(y ∈ B_{j+1}) ≥ (1+δ)γ
- (G2b): Pr(x ∈ A_j) · Pr(y ∈ B_j) ≥ (1+δ)γ₀
- (G3): λ ≥ c'·log(m/z*) for sufficiently large c', z* := min_i z_i

Conclusion: For any r > 0:
  Pr(T ≥ r·[c''λ²(m) + λ²·Σ 1/z_i]) ≤ (1+o(1))^r
where T := min{tλ | (P_t × Q_t) ∩ (A_m × B_m) ≠ ∅}

### 3. Lemma 1 (Product binomial drift)
Z_t = |(P_t × Q_t) ∩ (A × B)|. Under Pr(x∈A)Pr(y∈B) ≥ (1+δ)γ:
1. E[Z_{t+1} | F_t] ≥ λ(λ-1)(1+δ)γ
2. E[exp(-η·Z_{t+1}) | F_t] ≤ exp(-η·λ·(γλ-1)) for 0 < η ≤ (1-(1+δ)^{-1/2})/λ
3. Pr(Z_{t+1} < λ(γλ-1) | F_t) ≤ exp(-δ₁(1-√((1+δ₁)/(1+δ)))·γλ) for δ₁ ∈ (0,δ)

Key insight: Z_{t+1} = X'·Y' where X' ~ Bin(λ,p), Y' ~ Bin(λ,q) with pq ≥ (1+δ)γ,
but X',Y' not independent. Use stochastic dominance.

### 4. Level function (Definition 2)
g : [0..λ²] × [m] → ℝ is a level function if:
1. ∀x ∈ [0..λ²], ∀y ∈ [m-1]: g(x,y) ≥ g(x,y+1)
2. ∀x ∈ [0..λ²-1], ∀y ∈ [m]: g(x,y) ≥ g(x+1,y)
3. ∀y ∈ [m-1]: g(λ²,y) ≥ g(0,y+1)

## Key Technical Points
- The proof uses additive drift (Theorem 26 in paper = existing `additive_drift_theorem`)
  with a level-function potential
- The product count Z_t involves correlated binomials (not independent)
- Use stochastic dominance: Z_{t+1} ⪰ X·Y - Σ X_i·Y_i
- The Chernoff bound in Lemma 1 uses the MGF of the product
- Follow the style of existing proofs/M7_level_based_theorem_faithful/attempt.lean (1109 lines)
  which mechanizes the classical single-population LBT

## Requirements
- Use Mathlib's MeasureTheory and ProbabilityTheory
- Follow the style of existing DriftTheorems/*.lean files
- NO sorry/admit/sorryAx/axiom/exact?/@[implemented_by]
- Only standard axioms allowed: [propext, Classical.choice, Quot.sound]
- Namespace: DriftTheorems
- Register in lakefile.lean

Return the complete CoEvolutionaryLBT.lean file.
"""


async def main() -> int:
    project_root = Path("/Users/jonathangadeaharder/projects/lean-runtime-analysis")
    cfg = load_config(project_root)
    prover = cfg.provers["aristotle"]
    preflight(prover)

    with tempfile.TemporaryDirectory() as td:
        stage_root = Path(td) / project_root.name
        _stage_project(project_root, stage_root)

        from aristotlelib.project import Project

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
            f"--task-id {task.agent_task_id} --node DriftTheorems --wait"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
