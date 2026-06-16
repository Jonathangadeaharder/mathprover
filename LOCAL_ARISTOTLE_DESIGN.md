# Local-Aristotle: a tool-using prover agent (qwen MTPLX 27B + oprover-8B + gemma context)

Design for a fully-local proving **agent** that operates on real project files the way Aristotle
does — read/probe/compile/edit in a loop — instead of one-shot whole-proof generation. The guiding
constraint, learned the hard way (the A/B in `pipeline.py --prompt aristotle`): **the model that is
good at proving (oprover) is not trained to drive tools, and the models that can drive tools
(qwen/gemma) are not good at proving.** So we split the roles instead of asking one model to do both.

## 1. The three models and their jobs

| Model | Window | What it is | Role in the agent | Never does |
|---|---|---|---|---|
| **gemma-4-26b-a4b-qat** | 262k | huge-context MoE, cheap active params | **Context engine / librarian.** Ingests whole files, the project, `paper_source.md`, arxiv/search dumps; emits a **compact (<8k) self-contained goal spec** + curated premises + the exact in-scope definitions. Its job is *compression*: turn 200k tokens of project into the 8k oprover needs. | choose tactics; emit final Lean proofs |
| **Youssofal/Qwen3.6-27B-MTPLX-Optimized-Speed** | cap ~64k | fast local MTPLX instruction model, function-calling capable | **Orchestrator / planner.** The only model that *drives tools*. Runs the ReAct loop: decide next action, read tool results, build & update the helper-DAG, route work, decide done/escalate. Holds only compact loop state, never the whole project. | write Lean proofs itself; mark a node done without the gate |
| **oprover-8b** | 40k | SOTA Lean-trained whole-proof prover | **Prover tool.** Given a self-contained goal + retrieved proofs + compiler feedback, runs its trained refinement loop (existing `prove_leaf`) and returns proof-or-(failure+feedback). | navigate files; pick subgoals; decide strategy |
| *(nomic-embed)* | — | embeddings | premise retrieval index | — |

Rule of thumb: **gemma reads, qwen decides, oprover proves, the Lean compiler judges.**

## 2. Tools (the file-agent surface qwen can call)

All tools run in our Python harness and return **compact** text/JSON (never raw 100k dumps — that's
gemma's job to compress). Tool catalog, grouped:

**Navigate / read**
- `list_dir(path)` , `read_file(path, lines?)` — project files (read-only by default).
- `grep_project(pattern, glob?)` → matching `name @ file:line` (signatures, not bodies).
- `gather_context(goal_or_node)` → **gemma**: returns `{self_contained_goal (<8k), premises[], defs[], notes}`. The heavy-context step; everything downstream consumes its output.

**Probe (ground truth, cheap)**
- `run_lean(snippet)` → compile a scratch file; return errors/`#check` output (the `scratch-probe` already in `proof_architecture.py`).
- `check_decl(name)` → `#check @name` type; `open_private(names, module)` → test `Batteries.Tactic.OpenPrivate` access.
- `type_of(expr)` , `search_premises(goal, k)` → RAG (nomic) top-k.

**Prove**
- `prove(goal_spec, hints?, rounds|deadline)` → **oprover** refinement loop (`prove_leaf`); returns `{ok, proof|None, last_feedback}`.
- `refute(goal)` → build `¬(∀…)` and try to prove it (`pipeline.refute`); returns a counterexample or None. *Mandatory first call on any axiom-backed / quarantined statement.*

**Structure**
- `architect(goal)` → **qwen+gemma**: semantic spine + helper-DAG (`proof_architecture.build_architecture`), each helper a named `… := by sorry`.
- `scaffold_helpers(file, helpers[])` → write the helper sorries into a scratch file (scaffold-then-fill).

**Commit (gated, side-effectful)**
- `edit_attempt(node, new_text)` → write back **only after** `final_verify` passes.
- `final_verify(file, theorem)` → the gate (§4). The *only* path to "done".

**Escalate (optional)**
- `submit_aristotle(node)` → cloud Aristotle (separate, rate-limited tool, `aristotle_attach.py` to monitor). Used only when local budget is exhausted on a load-bearing node.

Tool protocol: strict JSON `{"tool": "...", "args": {...}}`; the harness parses, executes, and returns
`{"observation": ...}`. A malformed call is answered with a schema reminder (one retry), never crashes
the loop — same resilience principle as the `chat()` 400 handling.

## 3. Control loop (the orchestrator state machine)

> **IMPLEMENTED (turn-based, phase-batched) — supersedes the free-ReAct loop below.**
> One machine cannot co-reside the three models (JIT on but no auto-evict → OOM, observed live).
> So the loop is **phase-batched** to amortize model swaps (`residency.py`, single resident model):
> `CONTEXT(gemma: brief+premises) → [PLAN(qwen, free-tool probes) → PROVE(oprover burst: refute?+all
> leaves) → ASSEMBLE+GATE]*`. qwen never interleaves with oprover/gemma → ~2 swaps/iteration instead
> of one per step. Premise retrieval folded into gemma (nomic dropped from hot path). Gate
> (`final_verify`) is the only path to PROVED. Validated: residency single-model (no OOM, 0 HTTP
> 400/500), smoke node PROVED end-to-end (lake exit 0, axioms ⊆ standard). Code: `agent.py` (phase
> machine), `residency.py`, `tools.py` (`gather_context` does gemma premise-selection), `roles.py`.
> The free-ReAct description below is retained as the original rationale.

qwen runs a bounded ReAct loop; phases mirror how Aristotle actually operated in the logs:

```
ORIENT      read node attempt.lean + paper_source via gather_context (gemma)            [1 gemma call]
   ↓
REFUTE?     if node is axiom-backed/quarantined/"suspicious": refute() first            [diagnose-before-grind]
   ↓  (no counterexample)
PROBE       scratch-probe imports / #check needed lemmas / open_private discovery        [run_lean]
   ↓
ARCHITECT   build helper-DAG + semantic spine; scaffold helpers as sorry                 [qwen plan]
   ↓
PROVE-NODES for each helper, EASIEST FIRST:                                              [oprover]
              prove(); on fail → refine w/ compiler feedback (k rounds);
              still failing → architect() that helper one level deeper (recurse)
   ↓
ASSEMBLE    prove the parent using the now-proven helpers (prove() on the parent file)
   ↓
GATE        final_verify; if clean → edit_attempt + DONE; else feed errors back → PROVE-NODES
   ↓
ESCALATE    budget exhausted on a load-bearing leaf → submit_aristotle (optional) or report UNPROVED
```

Two always-on policies: **easy-helpers-first** (cheap wins unblock the DAG and seed the retrieval
memory) and **generic-helper extraction** (prefer a reusable Mathlib-shaped lemma — this is what
turned Aristotle's failed `cex_trunc_lower` monolith into `lintegral_singleton_le` + `cex_recursion`).

## 4. Soundness gate (non-negotiable, model-agnostic)

No matter which model produced text, a node is "done" **iff** `final_verify` returns clean:
1. `lake env lean <file>` exits 0 (no `error:`);
2. no forbidden placeholder in **active code** (`sorry`/`admit`/`exact?`/`sorryAx`/new `axiom`) — comment-aware (`strip_lean_comments`);
3. `#print axioms <thm>` ⊆ `{propext, Classical.choice, Quot.sound}`;
4. **statement preserved** — the target theorem's type is byte-identical (mod notation) to the node's original.
The orchestrator is structurally forbidden from emitting "PROVED" on any other basis. A tool-driving
model could otherwise weaken a statement or smuggle an axiom — the gate is the firewall.

## 5. Context / budget routing (who sees what)

The whole point of three models is to keep each one inside a sane window:

- **gemma** is the only model that ever sees large inputs (whole files, project greps, paper, arxiv).
  It outputs ≤8k compact specs. Invoked rarely (ORIENT, and when a node needs fresh context).
- **qwen** sees: the plan, the helper-DAG state, and the **last** few compact tool observations
  (not full history — compact-state, like oprover's training interface). Hard cap ~48k; summarize-and-drop
  older observations via gemma if it grows.
- **oprover** sees only a self-contained ≤8k goal + ≤6 retrieved proofs + last attempt + last Lean
  feedback (its trained interface; unchanged).

## 6. Resource policy (one machine, three big models)

gemma(262k) + qwen(27B) + oprover(8B) + nomic cannot all stay hot. Policy:
- Keep **oprover** resident for proof bursts; qwen is served by MTPLX and gemma loads on demand for
  `gather_context` (accept swap latency; it's called rarely). `residency.py` prevents accidental
  multi-model LM Studio loads.
- Batch same-model calls to avoid thrash (e.g., gather all context for a DAG level in one gemma call).
- Everything is wall-clock bounded (`--max-hours`) with the progress dashboard (already built) showing
  phase, current node, model in use, elapsed.

## 7. Failure & termination policy

- Per-node: `k` refinement rounds, then decompose one level (max depth `D`).
- Global: wall-clock deadline; on hit, return the partial DAG (proven helpers persist) + UNPROVED for the rest.
- Loop-guard: qwen action budget; repeated identical tool calls → force a phase transition.
- Suspicion trigger → `refute` (auto on axiom-backed nodes; also if the model's plan stalls, to check truth).
- Hard leaf after local exhaustion → optional `submit_aristotle` (separate, rate-limited).

## 8. Module plan (what to build; reuse in **bold**)

```
agents/
  agent.py        NEW  orchestrator: qwen ReAct loop, phase machine, DAG state, progress
  tools.py        NEW  tool catalog + JSON schema + dispatch to existing fns; compact-result discipline
  roles.py        NEW  model-role bindings (gemma=context, qwen=planner, oprover=prover) + residency policy
  pipeline.py     **reuse** prove_leaf (prover tool), refute, retrieve_premises, definitions_for_goal,
                          pattern_hints, progress (init_progress/prog), aristotle_user_prompt
  proof_architecture.py **reuse** build_architecture (architect), write_scratch_probe (probe)
  lean_pipeline.py **reuse** compile_lean_file, final_verify_attempt, forbidden_placeholders,
                          strip_lean_comments
  backends/aristotle.py, aristotle_attach.py **reuse** escalation tool
```

CLI: `python3 agent.py --node <NODE> --max-hours H [--allow-cloud-escalation]`. The dashboard
(`progress.html`) gains a "phase" + "model" field.

## 9. Why this is the right shape (and the honest risks)

It mirrors Aristotle structurally — a **tool-using policy** (qwen) orchestrating a **specialist prover**
(oprover) with the **compiler as judge**, and a **big-context reader** (gemma) feeding compact specs —
without pretending the 8B prover is something it isn't.

Risks, with mitigations:
- **qwen tool-call reliability** (4-bit 27B is not GPT-class at function-calling): strict JSON schema,
  one-retry on malformed calls, a small fixed action vocabulary rather than open-ended tool use.
- **qwen planning quality < Aristotle**: lean on `architect-proof` templates + pattern memory so the
  plan is scaffolded, not invented from scratch.
- **context creep in qwen**: gemma-summarize older observations; compact-state discipline.
- **model thrash / OOM**: residency policy + on-demand gemma; MTPLX-served qwen is treated as externally resident.
- **soundness**: the gate (§4) is model-agnostic and mandatory — the firewall against any tool-driving
  model weakening a statement or adding an axiom.
- **non-termination**: per-node + global budgets, loop-guard, progress visibility.

Net: oprover stays the proving core in its trained loop; qwen becomes the file-agent that gives it the
project access Aristotle has; gemma keeps everyone inside their context windows; the compiler keeps it
sound. Start by implementing `tools.py` + a thin `agent.py` that runs the §3 loop with qwen, reusing the
existing prover/refute/architect/gate functions as tools.
```
