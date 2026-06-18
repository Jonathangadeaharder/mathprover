# MathProver pattern memory

Reusable proof/diagnosis patterns distilled from successful Aristotle runs and local pipeline
runs. The `architect-proof` and `refute` modes surface these so workers don't rediscover them.
Each entry: when it applies, the move, and the concrete instance it came from.

## P1 — Refute before you grind (truth-probe a suspicious statement)
**When:** a goal is hard, long-quarantined, or backed by a trusted axiom; or a hypothesis set
looks too weak for the conclusion.
**Move:** before proof search, build `¬ (∀ binders, conclusion)` and try to prove *that* (see
`pipeline.build_negation_goal` / `--refute` / `dispatch --refute-first N`). A machine-checked
negation proof = the statement is false; stop and report the missing hypothesis.
**Instance:** `Quarantine.LBT.level_based_theorem` was *false as stated* — it dropped the paper's
`z_j ∈ (0,1]`. With `z_j → ∞` the RHS `(8/δ²)·∑(λ·log(6δλ/(4+zδλ)) + 1/z) → −∞` while
`expected_generations` is a `.toReal ≥ 0`; G1/G2/G3 don't bound `z` above. Counterexample:
`X=Fin 2, m=2, λ=20`, Dirac-at-top kernel, `γ₀=1/10, δ=1/2, z_j=10⁶`. (`proofs/M7_level_based_theorem/`.)

## P2 — `.toReal ≥ 0` vs a negative RHS (a cheap falsifier for inequality goals)
**When:** the goal is `someExpectation.toReal ≤ RHS` (or any `ENNReal.toReal`/`NNReal` LHS).
**Move:** `ENNReal.toReal_nonneg` gives `0 ≤ LHS` for free. If RHS can be driven `< 0` under the
stated hypotheses, the inequality is false. Check the sign of RHS at extreme parameter values
first — it's a one-line refutation.
**Instance:** the LBT disproof closed with `linarith [key, ENNReal.toReal_nonneg, hRHS_neg]`.

## P3 — Numeric stress-test before committing to "true" (Float `#eval`)
**When:** you've corrected a statement and want confidence it's now actually provable (not just
not-the-old-counterexample).
**Move:** `#eval` the RHS/key quantity over worst-case parameters as `Float` to see whether the
inequality plausibly holds, before spending a long proof attempt.
**Instance:** with `z_j ≤ 1` (worst case `z=1`), the corrected LBT RHS terms stayed positive across
`δ, λ, m` sweeps → the corrected statement is the genuine (hard) theorem, not vacuous.

## P4 — Scratch-probe the API before editing the target (`scratch-probe`)
**When:** a goal needs project lemmas/defs whose exact names, namespaces, or privacy you're unsure
of.
**Move:** in a disposable file, `#check @candidate`, test `import`s, and if a needed helper is
file-private use `open private … from Module` (Batteries.Tactic.OpenPrivate) — confirm it resolves
*before* touching `attempt.lean`.

## P5 — Feed definitions, not just lemma signatures (avoid re-definition hallucination)
**When:** the goal mentions project `def`s (`coea_sel_measure`, `A_ge`, …).
**Move:** put the *source of those definitions* in the prover prompt (`definitions_for_goal`) and
tell it to `unfold`/`simp only [...]`, not redefine. Observed failure without this: oprover wrote
`def coea_sel_measure …` inside `:= by`, a parse error.

## P6 — Architect the proof as a helper DAG, simple nodes first
**When:** a research-grade goal (multi-page paper proof).
**Move:** build a semantic spine + helper-lemma DAG (`architect-proof`); prove the easy/boundary
helpers first, the analytic/combinatorial core as its own node, then assemble. Don't treat a hard
`sorry` as one tactic search.
**Instance (A3a):** max-principle survival value `u`, potential `W = 1 − q^N`, finite averaging
operator, harmonicity, strict subsolution via PGF/binomial bounds → final theorem.

## P8 — Expected-hitting-time bound ⇒ additive drift with a potential
**When:** the goal is `expected_generations D target ≤ B` or `expected_generations_ennreal … < ⊤`.
**Move:** apply `kernel_additive_drift` with a potential `fun P => if P ∈ target then 0 else <bound>`
(measurable, vanishing on target), supply a strictly-positive finite drift, and discharge the
one-step drift obligation; `ENNReal.toReal_nonneg` covers the trivial side.
**Instance:** `cex_finite` bounded the worst-case hitting time by `1/q` this way (LBT-corrected run).
*(Now injected as a prove-time hint, keyed on `expected_generations`/`drift`.)*

## P9 — When a monolith fails, extract a GENERIC helper and scaffold-then-fill
**When:** a single induction/recurrence lemma won't close in the refinement loop.
**Move:** split it into named sub-lemmas — make the reusable ones **fully generic** — scaffold them
all as `sorry` in one file, prove the easy/general ones first, then prove the parent from them.
**Instance:** `cex_trunc_lower` failed as a 13-min monolith; Aristotle split out the generic
`lintegral_singleton_le` (`f a · μ{a} ≤ ∫⁻ f`) and the one-step `cex_recursion`, proved those, then
reassembled. *(Now injected as an always-on prove-time nudge.)*

## P7 — Multi-stage closing contract (never trust a green build alone)
**Move:** every finished attempt must pass: `lake env lean` (no `error`), grep for
`sorry|admit|exact?|sorryAx|axiom`, `#print axioms <thm>` = `[propext, Classical.choice, Quot.sound]`,
and a statement-unchanged check. A green build can still hide an open `sorry` (warning, not error).
**Wired in:** `lean_pipeline.final_verify_attempt`, `pipeline._statement_preserved`.
