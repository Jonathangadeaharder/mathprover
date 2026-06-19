#!/usr/bin/env python3
"""Dispatch Aristotle for Negative Multiplicative Drift theorem.

Negative Multiplicative Drift (Doerr et al., 2005) provides LOWER bounds
on hitting times when the process tends to move AWAY from the target.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.backends.aristotle import _stage_project, preflight

from config import load_config

PROMPT = r"""Mechanize the Negative Multiplicative Drift theorem in Lean 4.

## Context
Negative Multiplicative Drift (Doerr, Johannsen, Winzen 2005) provides
exponential LOWER bounds on hitting times. The theorem states:

If (X_t) is a stochastic process on R+ with X_0 = x_0, and there exists
δ > 0 such that E[X_{t+1} | X_t = x] >= (1+δ)·x (the process tends to
grow multiplicatively), then the hitting time T = min{t : X_t <= b} for
some threshold b < x_0 satisfies:
  E[T] >= (1/δ) · ln(x_0/b)

More precisely, if the process starts at x_0 and we want to hit [0, b],
the expected time is at least (1/δ) · ln(x_0/b).

## Existing Infrastructure
The project already has:
- DriftTheorems/AdditiveDrift.lean (197 lines, FULL, sorry-free)
- DriftTheorems/MultiplicativeDrift.lean (148 lines, FULL, sorry-free)
- DriftTheorems/NegativeDrift.lean (595 lines, FULL, sorry-free) — additive version

## Task
Create DriftTheorems/NegativeMultiplicativeDrift.lean that mechanizes:

1. **NegMultDriftSetup** structure:
   - State space: ℝ≥0
   - Growth rate δ > 0
   - Drift condition: E[X_{t+1} | X_t = x] >= (1+δ)·x
   - Initial state x_0, target threshold b

2. **neg_mult_drift_lower_bound** theorem:
   E[T] >= (1/δ) · ln(x_0/b)
   where T = min{t : X_t <= b}

3. **neg_mult_drift_tail_bound** theorem:
   P(T <= t) <= exp(-δ·t) · (x_0/b)
   (exponential tail bound on hitting time)

## Requirements
- Use Mathlib's MeasureTheory and ProbabilityTheory
- Use ENNReal for extended non-negative reals where appropriate
- Follow the style of existing DriftTheorems/*.lean files
- NO sorry/admit/sorryAx/axiom/exact?/@[implemented_by]
- Only standard axioms allowed: [propext, Classical.choice, Quot.sound]
- Namespace: DriftTheorems

## Key Technical Points
- The proof uses a supermartingale argument on (1+δ)^{-t} · X_t
- You need to show this is a supermartingale given the drift condition
- Then apply optional stopping theorem
- The logarithm appears naturally from the exponential growth
- Use Real.log for natural logarithm
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
