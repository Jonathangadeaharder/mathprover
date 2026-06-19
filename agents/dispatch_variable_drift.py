#!/usr/bin/env python3
"""Dispatch Aristotle for Variable Drift theorem (Witt 1108.4386).

Variable Drift generalizes additive and multiplicative drift by allowing
the drift to depend on the current state through a monotone function h(x).
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.backends.aristotle import _stage_project, preflight
from config import load_config

PROMPT = r"""Mechanize the Variable Drift theorem in Lean 4.

## Context
Variable Drift (Witt 2013, arXiv:1108.4386) is the most general drift theorem,
subsuming both additive and multiplicative drift. The theorem states:

If (X_t) is a stochastic process on R+ with X_0 = x_0, and there exists a
monotone function h: R+ -> R+ such that E[X_t - X_{t+1} | X_t = x] >= h(x),
then the expected hitting time T = min{t : X_t = 0} satisfies:
  E[T] <= integral from x_0 to x_max of 1/h(z) dz

## Existing Infrastructure
The project already has:
- DriftTheorems/AdditiveDrift.lean (197 lines, FULL, sorry-free)
- DriftTheorems/MultiplicativeDrift.lean (148 lines, FULL, sorry-free)
- DriftTheorems/NegativeDrift.lean (595 lines, FULL, sorry-free)

## Task
Create DriftTheorems/VariableDrift.lean that mechanizes:

1. **VariableDriftSetup** structure:
   - State space: ℝ≥0 (or ℝ≥0∞)
   - Monotone drift function h: ℝ≥0 → ℝ≥0
   - Drift condition: E[X_t - X_{t+1} | X_t = x] ≥ h(x)
   - Initial state x_0, maximum state x_max

2. **variable_drift_upper_bound** theorem:
   E[T] ≤ ∫_{x_0}^{x_max} 1/h(z) dz

3. **variable_drift_additive_special_case**:
   When h(x) = δ (constant), reduces to additive drift bound x_0/δ

4. **variable_drift_multiplicative_special_case**:
   When h(x) = δ·x, reduces to multiplicative drift bound ln(x_0)/δ

## Requirements
- Use Mathlib's MeasureTheory and ProbabilityTheory
- Use ENNReal for extended non-negative reals where appropriate
- Follow the style of existing DriftTheorems/*.lean files
- NO sorry/admit/sorryAx/axiom/exact?/@[implemented_by]
- Only standard axioms allowed: [propext, Classical.choice, Quot.sound]
- Namespace: DriftTheorems

## Key Technical Points
- The integral ∫ 1/h(z) dz requires h to be measurable and positive
- For the special cases, you need to show the integral simplifies correctly
- Use Mathlib's interval integrals (MeasureTheory.integral)
- The monotonicity of h is crucial for the bound
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
