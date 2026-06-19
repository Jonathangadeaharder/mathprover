#!/usr/bin/env python3
"""Dispatch Aristotle to mechanize the Artificial Fitness Levels (AFL) method.

Paper: "Drift Analysis with Fitness Levels for Elitist Evolutionary Algorithms"
(He & Zhou, arXiv:2309.00851v3, 2024)

Goal: Create DriftTheorems/ArtificialFitnessLevels.lean with:
- Fitness level partition definition
- Transition probability bounds between levels
- Hitting time upper/lower bounds via sum of 1/p_i
- Integration with existing drift theorems (Additive, Multiplicative, Negative)
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.backends.aristotle import _stage_project, preflight  # noqa: E402
from config import load_config  # noqa: E402

PROMPT = r"""Mechanize the Artificial Fitness Levels (AFL) method in Lean 4.

## Context
The AFL method (also called "fitness level method" or "Wegener's method") analyzes hitting times of elitist evolutionary algorithms by:
1. Partitioning the search space into fitness levels A_1, ..., A_m (where A_1 contains the optimum)
2. Bounding the transition probability p_i of leaving level A_i (i.e., finding a better solution)
3. Deriving runtime bounds as sum_{i=1}^{m} 1/p_i

## Reference Paper
"Drift Analysis with Fitness Levels for Elitist Evolutionary Algorithms" (He & Zhou, 2024)
Key ideas from the paper:
- Combine drift analysis with fitness levels for tighter bounds
- Define tightest metric bounds from fitness levels
- Derive linear bounds from metric bounds
- Framework for different types of linear bounds (without shortcuts, with shortcuts)

## Existing Infrastructure
Your project already has:
- `DriftTheorems/AdditiveDrift.lean` (FULL, compiles, sorry-free)
- `DriftTheorems/MultiplicativeDrift.lean` (FULL, compiles, sorry-free)
- `DriftTheorems/NegativeDrift.lean` (PARTIAL, being completed)

## Task
Create `DriftTheorems/ArtificialFitnessLevels.lean` with:

1. **Fitness level partition**: Define a partition of the search space into levels A_1, ..., A_m
   - `FitnessLevel (α : Type) (m : ℕ)` with levels indexed by `Fin m`
   - Partition property: disjoint, covering the state space

2. **Transition probabilities**: For each level A_i, bound p_i = P(transition from A_i to ∪_{j<i} A_j)
   - `transition_prob (X : MarkovChain α) (levels : FitnessLevel α m) (i : Fin m) : ℝ`
   - Lower bound: `p_i ≥ p_min i` for some known function `p_min`

3. **Hitting time bounds**:
   - Upper bound theorem: `E[T] ≤ ∑ i, 1 / p_min i` (when all p_min > 0)
   - Lower bound theorem: `E[T] ≥ ∑ i, 1 / p_max i` (under appropriate conditions)
   - Tightness: show bounds are tight when transition probabilities are exactly p_min/p_max

4. **Integration with drift**: Show AFL is a special case of additive drift when drift is constant within each level
   - `afl_implies_additive_drift`: if drift on level A_i is exactly δ_i, then p_i = δ_i / (level_width_i)

5. **Example**: OneMax function
   - Levels: A_i = {x : |x| = n - i} (i = number of zeros remaining)
   - Transition probability: p_i = i/n (flip one of the i zeros)
   - Runtime bound: E[T] ≤ ∑_{i=1}^{n} n/i = n·H_n = O(n log n)

## Requirements
- NO sorry/admit/axiom (except standard [propext, Classical.choice, Quot.sound])
- Use existing drift theorem infrastructure where possible
- Prove the bounds are tight under the paper's conditions
- The file must compile with `lake build DriftTheorems.ArtificialFitnessLevels`

## Verification
After implementation, run:
```bash
lake build DriftTheorems.ArtificialFitnessLevels
```
Ensure 0 errors, 0 sorry.

Start by reading the existing drift theorems (AdditiveDrift.lean, MultiplicativeDrift.lean) to understand the patterns and imports, then implement AFL.
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
            f"--task-id {task.agent_task_id} --node DriftTheorems --wait"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
