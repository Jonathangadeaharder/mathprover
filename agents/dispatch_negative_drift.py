#!/usr/bin/env python3
"""One-off fire-and-forget dispatch to complete the Negative Drift Theorem.

The current NegativeDrift.lean proves the exponential supermartingale bound
  ∀ N, E[exp(-c·X_{min N τ})] ≤ E[exp(-c·X_0)]
but is missing the final hitting-time lower bound:
  E[τ] ≥ exp(c·(b-a)) - 1  where c = ε/c_step²

Reuses _stage_project from agents.backends.aristotle.
Does NOT poll — monitor with:
    aristotle show <project_id> --task <task_id>
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.backends.aristotle import _stage_project, preflight  # noqa: E402

from config import load_config  # noqa: E402

PROMPT = r"""Complete the Negative Drift Theorem in `DriftTheorems/NegativeDrift.lean`.

CURRENT STATE: The file already proves the exponential supermartingale bound:
  ∀ N : ℕ, E[exp(-c·X_{min N τ})] ≤ E[exp(-c·X_0)]  where c = ε/c_step²

This is the core Hajek/Oliveto-Witt machinery (lines 99-328). The theorem `negative_drift_theorem` at line 83 has this as its conclusion.

MISSING PIECE: The final hitting-time lower bound. Add the following after the existing proof:

1. Add a new hypothesis to the theorem (or a new theorem): `h_tau_hit : ∀ ω, τ ω > 0 → X (τ ω) ω ≤ a` (the hitting boundary condition).

2. Prove the tail bound: `P(τ ≤ T) ≤ exp(-c·(b-a))` for all T. The proof is:
   - From the supermartingale bound: E[exp(-c·X_{min T τ})] ≤ E[exp(-c·X_0)] ≤ exp(-c·b) (since X_0 ≥ b)
   - Split on {τ ≤ T} and {τ > T}:
     On {τ ≤ T}: min T τ = τ, and X(τ) ≤ a (by h_tau_hit), so exp(-c·X(τ)) ≥ exp(-c·a)
     On {τ > T}: exp(-c·X_T) ≥ 0 (since X_T ≥ 0)
   - Therefore: exp(-c·a) · P(τ ≤ T) ≤ exp(-c·b)
   - Hence: P(τ ≤ T) ≤ exp(-c·(b-a))

3. Prove the hitting-time lower bound: `E[τ] ≥ exp(c·(b-a)) - 1`. The proof is:
   - E[τ] = Σ_{N=0}^∞ P(τ > N) ≥ Σ_{N=0}^{T-1} P(τ > N) for any T
   - P(τ > N) ≥ 1 - P(τ ≤ N) ≥ 1 - exp(-c·(b-a))
   - Choose T = ⌈exp(c·(b-a))⌉:
     E[τ] ≥ T · (1 - exp(-c·(b-a))) ≥ exp(c·(b-a)) · (1 - exp(-c·(b-a))) = exp(c·(b-a)) - 1

INSTRUCTIONS:
- Do NOT modify the existing supermartingale proof (lines 99-328). It is correct and complete.
- Add the new results as additional themmas or extend the existing theorem.
- The file must compile with 0 errors and 0 sorry/admit.
- Only standard axioms [propext, Classical.choice, Quot.sound] allowed.
- Use existing helper lemmas in the file (exp_secant_bound, cosh_sub_r_sinh_le_one, etc.).
- Use mathlib's probability theory: MeasureTheory.integral_indicator, ProbabilityTheory.condExp, etc.
- Mark the completed proof region with `-- PROVIDED SOLUTION` immediately above.

FALLBACK: If the full hitting-time lower bound cannot be formalized, at minimum prove the tail bound P(τ ≤ T) ≤ exp(-c·(b-a)) as a separate theorem. Do NOT weaken the existing supermartingale bound.

CONSTRAINTS:
- Output must be axiom-clean: no sorry, admit, sorryAx, exact?, axiom, or @[implemented_by].
- The file already compiles. Do not break any existing lemma.
- Use the existing variable declarations (Ω, m0, F, X, τ, a, b, ε, c_step, etc.) from lines 17-97.
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
            f"--task-id {task.agent_task_id} --node DriftTheorems --wait"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
