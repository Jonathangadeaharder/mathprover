# What Aristotle's run logs teach MathProver

Pulled live via the Aristotle CLI (`aristotle list`, `aristotle show <project> --limit 100` — events
capped at 100/page) on the faithful-LBT reduction run `9baa8a33…` (and siblings). The event feed is
the operational ground truth of how Aristotle actually works.

## Event-type distribution (100-event window, faithful run)
```
82  PROVING          per-subgoal proof-search narration / dispatch
 8  THINKING         orchestration decisions
 6  RUNNING_COMMAND  shell: lake env lean, grep -n, sed -i
 3  EDITING_FILE     scaffold / fill / cleanup edits
 1  REVIEWING        final gate
```
**Read:** Aristotle is ~82% raw proof search, sparse orchestration. Its edge is mostly *compute*
(huge bounded search per subgoal) wrapped in a thin, disciplined orchestration loop. We cannot match
the compute on one local box — so we copy the **structure** that makes compute effective, not the
volume.

## The transferable behaviors (what the logs show, verbatim patterns)
1. **Per-lemma subagents with retry.** Named subgoals (`faithful_maintenance`,
   `faithful_maintenance_numeric`, `faithful_drift_int`) each get an independent bounded proof
   search; `Proving X: failed` → repair → re-dispatch.
2. **Hypothesis-repair on fail.** When `faithful_maintenance{,_numeric}` wouldn't close, Aristotle
   *added the missing hypotheses* (`δ ≤ 1`, `z_star ≤ 1` via `h_z1`) and recompiled — rather than
   grinding the unprovable form.
3. **Self-audit + prune.** It detected a **dangling, incorrectly-stated** helper
   (`faithful_active_deficit`) and `sed -i '428,472d'`-deleted it, leaving one honest `sorry`. It
   does not leave wrong scaffolding behind.
4. **Continuous counterexample probing.** Throughout the search it tests concrete instances
   (`m=2, λ=100, γ₀=1, δ=1 → exp(-25) < 1/256`; "considering potential counterexamples") to decide
   whether a subgoal is even true before/while proving it.
5. **Whole-file iterate.** It works `attempt.lean` in place (`lake env lean attempt.lean` → `grep -n
   sorry` → `sed` edit → recompile), not isolated leaf files.
6. **Honest budget-exhaustion.** On running out, it cleans up, leaves exactly one documented `sorry`,
   and reports the precise remaining obligation — never a fake close.

## Gap analysis vs. our pipeline (and what we adopted)
| Aristotle behavior | MathProver before | Change made |
|---|---|---|
| per-lemma subagent + retry | helper-DAG + `prove_leaf` rounds | already have (kept) |
| **hypothesis-repair on fail** | none | REASSESS feeds Lean feedback into next PLAN; qwen can add hyps/restate (partial) |
| **self-audit: drop mis-stated helpers** | none | **NEW: refute-on-stuck** — a failed helper is refuted; a found counterexample marks it FALSE → REASSESS drops/restates it (`agent.py prove_phase`) |
| continuous counterexample probing | `truth_probe` (decide/norm_num), upfront `refute` on axiom-backed | extended: per-leaf refute on failure (the highest-leverage piece — catches the `faithful_active_deficit` class) |
| whole-file iterate | `edit_attempt` writes whole file + `final_verify` | already whole-file (kept) |
| honest budget-exhaustion | UNPROVED + gate | already have (kept) |

### The one structural addition (implemented)
**Refute-on-stuck per sub-lemma** (`agent.py`, `prove_phase`): when oprover fails a *model-invented*
helper, build `¬(∀…)` and spend a short (3-round) oprover budget trying to disprove it. If a
counterexample lands, the helper is **mis-stated** → feedback tells REASSESS to drop/restate it
instead of retrying. Sound (refute only succeeds by a gated proof of the negation; a true lemma is
never refuted) and cheap. This is exactly the move that let Aristotle delete its own false
`faithful_active_deficit` and not burn budget on it.

## What we deliberately do NOT try to copy
- **Raw search volume** (82 search steps/window, parallel subagent fleet): single local GPU, one
  resident model — infeasible. We compensate with gemma context-compression + premise selection so
  oprover's *fewer* attempts are better-aimed, and with the refute pre-filter so we don't search
  false goals.
- **Cloud-scale model**: Aristotle's prover ≫ oprover-8b. Hard research cores (`faithful_drift_int`)
  stay an Aristotle-cloud job; the local pipeline targets the tractable leaves + the refutations +
  the decomposition scaffolding.

## Net
MathProver now mirrors Aristotle's *loop shape*: decompose → prove-each → **refute the stuck ones** →
prune/restate → assemble → gate. The remaining difference is compute, which we narrow with
context-compression and aimed retrieval rather than brute force.
