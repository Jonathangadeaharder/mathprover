#!/usr/bin/env python3
"""Dispatch Aristotle for Variance Drift theorem (Lehre & Lin 2024, arXiv:2405.04480).

This mechanizes the core engine: Lemma 1 (bounded conditional increments),
Theorem 1 (variance overcomes negative drift), and the recurrence engine.
A detailed plan exists at docs/plans/variance-drift-mechanization.md.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.backends.aristotle import _stage_project, preflight

from config import load_config

PROMPT = r"""Mechanize the Variance Drift theorem with exponential tail bounds in Lean 4.

## Context
This mechanizes the core results from "Concentration Tail-Bound Analysis of
Coevolutionary and Bandit Learning Algorithms" (Lehre & Lin, 2024, arXiv:2405.04480).

The paper provides a unified recurrence method for proving exponential tail bounds
on hitting times of stochastic processes with variance conditions. This is the
key missing piece connecting the existing additive/multiplicative/negative drift
theorems to high-probability bounds.

## Existing Infrastructure
The project already has:
- DriftTheorems/AdditiveDrift.lean (197 lines, FULL, sorry-free) — `additive_drift_theorem`
- DriftTheorems/MultiplicativeDrift.lean (148 lines, FULL, sorry-free)
- DriftTheorems/NegativeDrift.lean (595 lines, FULL, sorry-free)
- DriftTheorems/VariableDrift.lean (409 lines, FULL, sorry-free)
- DriftTheorems/NegativeMultiplicativeDrift.lean (306 lines, FULL, sorry-free)
- DriftTheorems/VarianceDrift.lean (119 lines, SCAFFOLD with sorries — REPLACE THIS FILE)

There is also a scaffold file DriftTheorems/VarianceDrift.lean with:
- `varianceTransform b X t ω = b^2 - (b - X t ω)^2` (defined, works)
- `variance_transform_identity` (proved by ring)
- `kthHitTime` (defined)
- 4 sorries: `kthHitTime_is_stopping`, `bounded_conditional_increments_discrete`, `variance_drift_tail_bound`

## Task
REPLACE DriftTheorems/VarianceDrift.lean with a complete, sorry-free mechanization of:

### Lemma 1 (Bounded conditional increments)
For stochastic process (X_t) over R≥0 with stopping time T, if there exist r, η > 0
such that for any j ≥ 0:
  E[1_{T>t} · 1_{|X_t - X_{t+1}| ≥ j} | F_t] ≤ r / (1+η)^j
then there exists c > 0 such that:
  E[|X_{t+1} - X_t| · 1_{T>t} | F_t] ≤ c for all t

### Theorem 1 (Variance overcomes negative drift — MAIN)
Let (X_t) adapted to (F_t) in finite state space S ⊆ R, T = inf{t ≥ 0 | X_t ≤ 0}. Suppose:
- (A1) exists δ > 0, for all t < T: E_t[(X_{t+1}-X_t)^2 - 2(X_{t+1}-X_t)(b-X_t)] ≥ δ
- (A2) for all t ≤ T: 0 ≤ X_t ≤ b
- Geometric step tail condition (from Lemma 1)

Then for τ > 0: P(T > τ) ≤ exp(-τ·δ/(e·b²))

### Recurrence engine lemma (reusable)
The intersection-decomposition recurrence:
  {T_0 > (k+1)·θ} = {T_0 > k·θ} ∩ {T_{k·θ} - k·θ > θ}
Tower property + conditional bound → P(T_0 > (k+1)·θ) ≤ P(T_0 > k·θ) · e^{-1}
By induction: P(T_0 ≥ τ) ≤ e^{-τ/θ}

### Theorem 2 (Standard variance drift)
(X_t) over R≥0, finite expectation. Conditions:
- (C1*) geometric step tail
- (C2) E(X_{t+1} - X_t | F_t) ≥ 0
- (C3) exists δ > 0, E((X_{t+1}-X_t)^2 | F_t) ≥ δ
For b > 0, T = inf{t ≥ 0 | X_t ≥ b}, X_0 ∈ [0, b]:
- E(T) ≤ (b² - X_0²) / δ
- P(T ≥ τ) ≤ exp(-τ·δ/(e·b²))

### Theorem 5 (Additive drift with tail bound)
(X_t) over R, finite expectation. (C1*) and E[X_{t+1}-X_t | F_t] ≥ ε for ε > 0.
For b > 0, T = inf{t ≥ 0 | X_t ≥ b}, X_0 ∈ [0, b]:
- E(T) ≤ (b - X_0) / ε
- P(T ≥ τ) ≤ exp(-τ·ε/(e·b))

## Key Technical Points
- The variance-transformed process is Y_t = b² - (b - X_t)² (polynomial, NOT exponential)
- The auxiliary martingale is Z_t = Y_t + δ·t (supermartingale)
- The key identity (already proved): Y_t - Y_{t+1} = (ΔX)² - 2·ΔX·(b - X_t)
- The recurrence engine is the reusable core — factor it as a lemma
- Use the existing `additive_drift_theorem` for the E(T) < ∞ step (finiteness for OST)
- Use the existing stopping time helpers from AdditiveDrift.lean: `measurableSet_F_tau_gt`, `min_eq_sum_indicator`
- Mathlib's `condExp` algebra is used throughout (condExp_mono, condExp_add, condExp_sub, condExp_smul, condExp_stronglyMeasurable_mul_of_bound)

## Requirements
- Use Mathlib's MeasureTheory and ProbabilityTheory
- Follow the style of existing DriftTheorems/*.lean files (especially NegativeDrift.lean)
- Use the existing condExp algebra pattern from NegativeDrift.lean
- NO sorry/admit/sorryAx/axiom/exact?/@[implemented_by]
- Only standard axioms allowed: [propext, Classical.choice, Quot.sound]
- Namespace: DriftTheorems
- Register the file in lakefile.lean (add `DriftTheorems.VarianceDrift` to the roots)

Return the complete VarianceDrift.lean file.
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
            f"--task-id {task.agent_task_id} --node DriftTheorems --wait"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
