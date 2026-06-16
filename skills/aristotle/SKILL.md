---
name: aristotle
description: >
  Use Harmonic's Aristotle — a cloud verified-reasoning prover for Lean 4 — to fill `sorry`s in a
  Lean project or prove research-grade goals that the fully-local mathprover pipeline cannot close.
  Aristotle is a SEPARATE, optional tool: the local pipeline (oprover + qwen + gemma, compiler-in-the-
  loop) is the always-available system; reach for Aristotle deliberately for hard goals, mindful of
  its rate limits. Trigger: "use aristotle", "submit to aristotle", "cloud prover", "this leaf is too
  hard for the local models".
---

# Aristotle (separate cloud tool — NOT wired into the local pipeline)

**Relationship to mathprover.** The local pipeline is self-sufficient and always available. Aristotle
is an *independent* tool you invoke by hand for hard goals, and as a registered mathprover backend
(`dispatch.py --prover aristotle`). The local recursion never auto-calls it — if Aristotle is
rate-limited or down, the local system still works.

## Prerequisites (one-time)
- **Lean/Mathlib pinned to v4.28.0** (Aristotle's supported version): `lean-toolchain` =
  `leanprover/lean4:v4.28.0`; lakefile `mathlib` rev `v4.28.0`. Our project is already pinned.
- **CLI + lib**: `uv tool install aristotlelib` (CLI), and ensure the *Python module* is importable by
  the interpreter mathprover uses: `python3 -m pip install aristotlelib --break-system-packages`
  (the mathprover backend `import`s `aristotlelib`; missing it gives `No module named 'aristotlelib'`).
- **API key** in `~/.zshrc`: `export ARISTOTLE_API_KEY=...` (get it at
  aristotle.harmonic.fun/dashboard/settings; rotate if ever exposed). `source ~/.zshrc` before use.
- **Project builds**: `lake exe cache get && lake build` must pass — Aristotle submits the project.

## Rate limits (personal account) — respect them
- **60 requests/minute, 1000 requests/day.** mathprover enforces this via `agents/rate_limit.py`
  (`check_and_record` before every submit; `remaining()` to query budget). Do not bypass it.
- Each submit is one request; a hard goal is a single long-running *task*, not many requests.

## Two ways to use it
1. **Through mathprover (preferred for our nodes):**
   ```
   source ~/.zshrc                       # ARISTOTLE_API_KEY
   export MATHPROVER_PROJECT_PATH=~/projects/lean-runtime-analysis
   cd ~/projects/mathprover/agents
   python3 dispatch.py --node <FOLDER> --prover aristotle --skip-verify
   ```
   Submits `proofs/<FOLDER>/attempt.lean` (which must compile *with* its `sorry`), polls the cloud
   task (~10 min to hours for research goals), writes the filled proof back to `attempt.lean`.
2. **Aristotle CLI / Python API directly:**
   - CLI: `aristotle submit "Prove ..." --project-dir . --wait` (prompt mode), or submit a project to
     fill its `sorry`s.
   - Python: `from aristotlelib import Project; p = await Project.create(prompt=...);
     tasks,_ = await p.get_tasks(limit=1); await tasks[0].wait_for_completion();
     await p.get_files(destination="out.tar.gz")`.

## Modes
- **Fill sorries** (use this for our results): submit the project file with a `sorry`; Aristotle returns
  a verified fill. Keeps the proof against *our* statement → integrable.
- **Prove from prompt** / **formalize a paper** / **find counterexample**: natural-language modes;
  the result is Aristotle's *own* formalization — verify it matches our intended statement before use.

## Monitoring a run
Backgrounded run logs show: `Task: <uuid>`, `Project: <uuid>`, and a progress bar
(`[██░░] 25% (started 53m ago)`). The job is detached; re-`tail` the log to check progress.

## ALWAYS verify the result yourself (do not trust the cloud's word)
After Aristotle returns a proof, independently confirm — same bar as everything else in this project:
```
lake env lean proofs/<FOLDER>/attempt.lean        # exit 0, no `error:`, no `sorry` warning
# and, in a copy, append:  #print axioms <thm>     # must be [propext, Classical.choice, Quot.sound]
```
Only then is it "proved": **lake-verified, sorry-free, axiom-clean, and the statement is OUR statement.**
A returned proof that adds an axiom, leaves a `sorry`, or proves a weaker/different statement does not count.

MathProver's shared final gate is:
```
python3 ~/projects/mathprover/agents/proof_architecture.py final-verify \
  --project-root ~/projects/lean-runtime-analysis \
  --file proofs/<FOLDER>/attempt.lean
```

For hard goals, copy Aristotle's successful pattern before submission or local retry:
```
python3 ~/projects/mathprover/agents/proof_architecture.py architect-proof \
  --project-root ~/projects/lean-runtime-analysis \
  --goal-file proofs/<FOLDER>/attempt.lean

python3 ~/projects/mathprover/agents/proof_architecture.py scratch-probe \
  --project-root ~/projects/lean-runtime-analysis \
  --goal-file proofs/<FOLDER>/attempt.lean \
  --open-private-from <ModuleName> \
  --check <helper1> <helper2>
```
This creates a helper-DAG/semantic-spine artifact and a disposable Lean probe for `#check`,
imports, and `Batteries.Tactic.OpenPrivate` experiments.

## When to reach for Aristotle vs stay local
- **Stay local** (default): anything the oprover+qwen+gemma pipeline closes within budget; when you're
  rate-limited; for fast iteration.
- **Use Aristotle**: a genuinely hard leaf the local pipeline cannot close after decomposition, or a
  capstone you want a strong cloud attempt on — and you have daily budget to spare.

## ALWAYS refute-first on a quarantined / axiom-backed statement
Before submitting any axiom-backed or long-quarantined statement, run the **local refutation
probe** — it is cheap and catches false statements before you spend cloud budget:
```
python3 ~/projects/mathprover/agents/dispatch.py --node <FOLDER> --prover aristotle --refute-first 4
# local-only: python3 ~/projects/mathprover/agents/pipeline.py --refute \
#   --goal-file proofs/<FOLDER>/attempt.lean --project-root ~/projects/lean-runtime-analysis
```
It builds `¬ (∀ binders, conclusion)` and runs the OProver loop on it. If a counterexample is
found, dispatch reports `RESULT: FALSE` (exit 3) and does **not** submit. This is exactly how the
quarantined `level_based_theorem` was found false (missing `z_j ≤ 1`) — Aristotle disproved it
rather than proving it. Fix the statement, then submit the corrected form. See `PROOF_PATTERNS.md`
(P1–P3).
