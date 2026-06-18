# MathProver consolidation + improvement plan (2026-06-15)

Vision: **GarageBand-simple GUI + a powerful CLI** (the CLI is the agent interface; GUI is the
friendly layer). One system, three backends, sound verification.

## Resolved facts (probed on the live Mac)
- Backends are OpenAI-compatible: `oprover-8b` and gemma can stay on LM Studio at `localhost:1234`;
  qwen now defaults to MTPLX at `127.0.0.1:8000` with
  `Youssofal/Qwen3.6-27B-MTPLX-Optimized-Speed`. Aristotle = cloud
  (key goes in `~/.zshrc`, currently absent from mathprover `.env`).
- **The 3 proof backends = `oprover`, `qwen`, `aristotle`.** Local ones use one generic
  OpenAI-compatible backend, parameterized by endpoint + model id.
- **Remove Goedel** entirely (user: oprover beats it on all metrics, incl. 32B): delete
  `agents/backends/goedel.py`, `resource_guard` MLX lock, goedel routing in `router.py`/`config.py`,
  goedel entries in `mathprover-ui` stores, and the `${GOEDEL_PROVER_PATH}` config.
- **The "mathrover reimplementation" is folded in / deleted.** The Lean-project typo files
  `mathrover.py`, `solve_all.py`, and `temp_mathrover_testbed.lean` were removed. The useful piece
  (batch retry across proof folders) now lives in `agents/prove_all.py` and routes through
  MathProver dispatch/final verification instead of a duplicate local API loop.

## Live PoC (done, on the Mac)
legacy qwen-27B → `by rfl` → **lake-verified** ✓. `oprover-8b` → sorry-cheat that the reimpl's weak
gate falsely passes ✗. ⇒ verification gate MUST reject `sorry`/`admit` (mathprover `has_sorry` does).

## Stage 1 — backend consolidation (CLI core)  [done]
1. `agents/backends/lmstudio.py`: one OpenAI-compatible backend (base_url, model, temp, max_tokens,
   N samples, correction_rounds). Reuses `lean_pipeline.{extract_lean4_blocks, apply_generated_proof,
   compile_lean_file, forbidden_placeholders, final_verify_attempt}`. **Gate = compiles, no proof
   placeholders, no new axiom declarations, and final `#print axioms` check.** Returns the existing
   `RunResult`.
2. Instantiate as `oprover` (`oprover-8b`) and `qwen`
   (`Youssofal/Qwen3.6-27B-MTPLX-Optimized-Speed` via MTPLX).
3. `config.py`/`mathprover.toml`: providers `oprover|qwen|aristotle`; routing `default_leaf=oprover`,
   escalate→`qwen`→`aristotle` capstone. Delete goedel + MLX `resource_guard`.
4. Create real `.env` (project path; Aristotle key from `~/.zshrc`).
5. Delete the scattered `lean-runtime-analysis` oprover scripts (superseded).

## Stage 2 — the SOTA loop (what makes it "automated")
Orchestrator (CLI `mathprover prove <node>`): per node → best-of-N draft (oprover) → lake+sorry gate
→ repair rounds (feed lean errors back) → escalate oprover→qwen→aristotle on failure → premise
retrieval via `nomic-embed` over the project graph → cache attempts in `.mathprover/`. CLI is
scriptable/JSON-out so agents drive it; every "proved" is lake-verified, sorry-free, `#print axioms`
optional gate.

## Stage 3 — GarageBand GUI (on top of the CLI)
Track-style lanes per proof node (like GB tracks), one-click "prove" (▶), live status pills
(drafting/verifying/escalating), the goal + candidate proof + lean errors inline, backend selector as
a simple dropdown. Thin layer calling the same CLI/JSON the agents use — no logic duplicated in the UI.

## Stage 4 — run on our usecase
Point it at `lean-runtime-analysis`. Start with tractable real leaves (e.g. an A2/B2-style arithmetic
lemma) to confirm end-to-end auto-proofs, then aim the escalation chain at the open A3a sub-lemmas.
Honest expectation: A3a is research-grade (we hand-designed it across many turns); local 8B/27B may
not one-shot it, but the system will attempt it soundly and bank the easy ones — and aristotle is the
capstone for the hard ones.

## Honest constraints
- I can drive the Mac (osascript) + edit mounted files, so I CAN run the real pipeline and iterate.
- I cannot fabricate a verified A3a proof; "proved" only ever means lake-verified + sorry-free.
- Goedel 32B weights in `~/models` stay on disk unless you say delete; mathprover just stops using them.
