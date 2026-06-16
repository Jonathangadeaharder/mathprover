# Scaling MathProver to BIG problems (persistent recursive proof-DAG)

## The problem to solve
A "big" target (e.g. the faithful Corus LBT: ~600 lines, ~20 lemmas, one research core) is bigger
than any single model context, single `prove_leaf` call, or single session. Today those 28
`proofs/C2_M*` nodes exist only because **I (the human/planner) hand-decomposed them across many
sessions** and linked them in PLAN prose. To use the system *autonomously* on the next big problem,
the **system** must do what I did: decompose to depth, schedule the frontier, prove the tractable
leaves, refute the mis-stated ones, escalate the research cores, assemble up the tree, and keep a
sound, resumable account of the whole thing.

Three hard truths shape the design:
1. **No model sees the whole proof.** gemma compresses per-node; the global structure lives on disk,
   not in a context window.
2. **The work outlives a run.** Days, crashes, restarts → the DAG must persist and resume.
3. **The research cores stay LOCAL.** The long tail (e.g. `faithful_drift_int`) is NOT shipped to a
   cloud prover. We give the local fleet a genuine *deep-research* capability, adapted from
   Tongyi DeepResearch (IterResearch + Heavy mode), so hard nodes are attacked here, on our models.

## Core idea: a persistent proof-DAG with a frontier scheduler
Generalize the single-node `agent.py` into a DAG over proof nodes. Each node = one lemma/obligation;
edges = "uses". The orchestrator walks the DAG turn-based, batching by model to amortize residency
swaps across the **whole frontier**, not per node.

### 1. Data model — `dag.json` (on disk, the single source of truth)
```jsonc
{
  "goal": "level_based_theorem_faithful",          // root node id
  "nodes": {
    "<id>": {
      "statement": "<lean: imports+open+sig := by sorry>",  // self-contained
      "status": "open|context|planning|proving|researching|proved|refuted|blocked",
      "deps": ["<child id>", ...],                  // sub-lemmas it consumes
      "parent_proof": "by <tactics using deps>",    // null for leaves / direct
      "depth": 0,
      "premises": ["<gemma-selected sig>", ...],    // cached context
      "brief": "<gemma compact brief>",
      "report": ".mathprover/dag/<id>.report.md",   // IterResearch proof-state report (research nodes)
      "proof_path": ".mathprover/dag/<id>.lean",    // gate-clean artifact when proved
      "attempts": [{"ts","model","rounds","verdict","feedback_head"}],
      "axioms": ["propext","Classical.choice","Quot.sound"]  // #print axioms when proved
    }
  }
}
```
Mirrors the existing `proofs/<NODE>/{attempt.lean,paper_source.md,status.md}` layout — a node IS a
`proofs/` folder; `dag.json` adds the machine-readable graph (deps, status, depth) that today lives
only in PLAN prose.

### 2. The scheduler loop (turn-based, frontier-batched)
```
load dag.json (or seed root from a paper_source)
until root.proved or budget(--max-hours / --max-nodes) exhausted:
  frontier = ready open nodes (all deps proved)           # nothing blocked on unproven children
  # ---- batch by model across the WHOLE frontier (≤ swaps, not per-node) ----
  CONTEXT  (gemma)   for each frontier node missing brief/premises: gather_context   [1 residency load]
  PLAN     (qwen)    for each frontier node: decide direct|decompose; emit leaves+parent_proof
                     → write NEW child nodes into dag.json (recursion), scaffold sorries
  PROVE    (oprover) for every ready LEAF: prove_leaf; on stuck → refute-on-stuck (drop/restate)
  ASSEMBLE+GATE      for nodes whose deps just closed: build candidate, edit_attempt→final_verify,
                     mark proved + record #print axioms; propagate "ready" upward
  DEEP-RESEARCH      a leaf that is (a) not refuted, (b) failed normal prove rounds, (c) at max
                     decomposition depth → enter the LOCAL deep-research mode (§5): IterResearch loop,
                     and Heavy-mode Research-Synthesis for the root-critical cores. Only if THAT also
                     exhausts its budget → mark `blocked` and surface the exact obligation to the human.
  persist dag.json after every state change                # crash-safe, resumable
```
Why batched: residency swaps cost ~10-30s. Doing **all** gemma work, then **all** qwen, then **all**
oprover for the frontier turns N×(3 swaps) into 3 swaps per frontier sweep. This is the single
biggest local-throughput lever.

### 3. Recursive decomposition (the part I did by hand)
A node is a **leaf** iff its self-contained prompt ≤ `INPUT_LIMIT` (8k, measured) AND oprover can
close it. Else qwen+gemma **decompose** it (`decompose.py` / `propose_split` + `verify_split`): emit
named sub-lemmas + a `parent_proof`, **compiler-check the split entails the parent** (no prose
bridge), write the sub-lemmas as new child nodes, recurse. Stop conditions per branch:
- proved → assemble; refuted → drop/restate (replan parent); 
- `depth ≥ MAX_DEPTH` and still hard → DEEP-RESEARCH (§5, local) or mark `blocked` with the obligation.
Easiest-first ordering + generic-helper extraction (the Aristotle patterns) seed reusable lemmas
early.

### 4. Assembly + the global soundness invariant
- A node is **proved** iff `final_verify` is clean on its artifact: compiles, no
  `sorry/admit/exact?/axiom`, statement byte-identical, `#print axioms ⊆ {propext, Classical.choice,
  Quot.sound}` (plus any *declared* quarantined axioms, tracked explicitly).
- The **root** is proved iff every node on its dep-closure is proved AND a final end-to-end build of
  the assembled file is gate-clean. The on-disk `axioms` per node roll up: if any node carries
  `sorryAx` the root is NOT closed. This is the firewall — no amount of orchestration can fake it.

### 5. Local deep-research mode (the research tail — NO cloud)
Hard nodes that survive normal prove + decomposition get a genuine research loop, adapted from
**Tongyi DeepResearch** (arXiv:2510.24701). Their insight transfers directly: long-horizon work dies
of **context bloat** in a mono-context ReAct log, and N-way exploration only fits in a window if each
thread is **compressed to a report**. We borrow both, on our local role-split models. (We do NOT have
their agentic-RL-trained 30B model — we approximate the *paradigm*, not the weights.)

**(a) IterResearch loop (per hard node).** Maintain an evolving **proof-state report** (the "central
report") as the node's durable artifact — NOT the raw attempt log. Each round:
1. **THINK** (qwen): gap analysis over the report — what is still unproven, which reduction/lemma is
   the bottleneck.
2. **REPORT-UPDATE** (qwen, gemma-compress when it grows): fold the last evidence (compile error,
   proven fragment, dead-end, `#check` result) into the report; **discard the raw intermediate** —
   keep established facts, working sub-terms, ruled-out approaches.
3. **ACTION** (one targeted op): probe (`run_lean`/`check_decl`/`search_premises` — our mathlib/
   project analog of web-search+page-read), OR attempt a tactic block via **oprover**, OR spawn a
   child node (decompose). 
The round's **workspace is reconstructed** = `report (compressed) + last evidence only`, never the
full history. This is what lets a 40k/64k window sustain a long multi-step proof search instead of
degrading. (Our existing `prove_leaf` carries "last attempt + last feedback" — a degenerate one-step
version of this; deep-research generalizes it to a persistent, synthesized report.)

**(b) Heavy mode / Research-Synthesis (root-critical cores).** For the genuinely hard core
(`faithful_drift_int` class), run **N research threads on diverse attack angles** — e.g. for that
lemma: (A) direct ℝ≥0∞ integral; (B) prove the real-valued expectation then transfer; (C) split into
active-deficit + maintenance + numeric. Under turn-based residency the threads run **sequentially**
(one model resident), each persisting its **compressed report** (approach, proven fragments,
confidence, remaining gap — not the full trajectory). Then a single **synthesis pass (gemma**, big
window — holds all N compressed reports) consolidates: resolve contradictions, pick the convergent
winning angle, **graft the proven fragments**, and emit either an assembled candidate (→ GATE) or a
refined child sub-DAG (→ scheduler). Compression is the enabler: N full trajectories would never fit;
N reports do.

**Budget + soundness.** Deep-research is bounded (rounds, threads, wall-clock) and **changes nothing
about soundness** — every tactic attempt is still compiler-gated, every assembled candidate still
passes `final_verify` + `#print axioms`. A research thread cannot "talk its way" to proved; it can
only produce fragments the compiler accepts. If the whole deep-research budget is spent without a
gate-clean proof, the node is `blocked` with its report (the precise remaining obligation) surfaced
to the human planner — never a fake close.

### 6. Resume / long-run
`dag.json` persisted after every transition ⇒ a session is just "load DAG, run scheduler until this
session's `--max-hours`, persist, exit". Next session resumes the frontier. Proved nodes + their
artifacts are never recomputed (status cached). Crash mid-prove → node returns to `open`, retried.
This is what makes multi-day big problems possible.

### 7. Honest accounting + dashboard
Extend the progress dashboard to the DAG: `% nodes proved`, open frontier, `refuted` (mis-stated,
needs human/planner), `blocked` (research-exhausted), `researching` (in deep-research), and the **critical path** of
unproven nodes between the frontier and the root. At any moment the user sees exactly what is proven,
what is conjectured-open, and where the research cores are.

## Module plan (reuse heavily — bold = exists)
```
agents/
  dag.py        NEW  dag.json model: load/save, node states, frontier(), ready(), assemble-up,
                     axiom roll-up, critical-path. Crash-safe writes.
  orchestrator.py NEW  the frontier scheduler loop (§2); composes the phases below over the DAG.
  deep_research.py NEW  the §5 local research loop: IterResearch (proof-state report + workspace
                     reconstruction) and Heavy-mode Research-Synthesis (N sequential threads → gemma
                     synthesis). Composes existing tools; emits gate-able candidates or child nodes.
  decompose.py  **reuse/extend**  recursive split → child nodes (already budget-gated)
  agent.py      **reuse**  its phase fns (CONTEXT/PLAN/PROVE/ASSEMBLE) become per-frontier-batch ops
  tools.py      **reuse**  gather_context, prove, refute, architect, scaffold_helpers, edit_attempt, final_verify
  pipeline.py   **reuse**  prove_leaf, refute, verify_split, build_negation_goal, premise select, progress
  residency.py  **reuse**  single-model turn-based swaps (batch at phase boundaries)
  run_registry.py **reuse**  per-attempt logging
```
CLI: `python3 orchestrator.py --goal <root-node-or-paper> --max-hours H [--max-depth D]
[--research-threads N] [--research-rounds R]`. Fully local. Idempotent/resumable: re-running
continues the DAG. (The cloud `dispatch.py --prover aristotle` path still exists as a *separate*,
manually-invoked tool — it is NOT part of this autonomous loop.)

## What stays the same (the invariants that make it safe)
- **Turn-based single residency** — never two models hot (memory).
- **Compiler-in-the-loop at every structural step** — splits entailment-checked, leaves gate-verified.
- **Refute-on-stuck** — mis-stated helpers caught early (the Aristotle self-audit lesson).
- **Gate is the only path to proved** — global soundness via per-node `#print axioms` roll-up.
- **Honest status** — `refuted`/`blocked`/`researching` are first-class; no fake closes.

## Honest limits (and the human/planner's role)
- Local 8B/27B are weaker than a cloud research model. The deep-research mode (§5) is our bet that
  IterResearch context-management + Heavy-mode synthesis lets them punch above their weight on hard
  cores — but some (measure-theory drift, novel couplings) may still end `blocked`, surfaced to the
  human planner with the proof-state report = the exact remaining obligation. The system's job is to
  **shrink the human's work to only the genuine research nodes**, having mechanically discharged
  everything else and verified the scaffolding entails the goal.
- We are NOT replicating Tongyi's trained agentic model — only its inference-time paradigm
  (reconstructed workspace, compressed-report synthesis). Expect less than their benchmarks; the win
  is staying fully local with bounded, sound search instead of shipping cores to a cloud prover.
- Decomposition quality is the risk: a bad split wastes budget. Mitigations: `verify_split` (entails
  parent or rejected), refute-on-stuck (drops false children), easiest-first (cheap wins first),
  per-node attempt caps.

## Build order (incremental, each shippable)
1. `dag.py` + seed a DAG from the existing 28 `C2_*` nodes (manifest the graph we already have).
2. `orchestrator.py` frontier scheduler over `dag.py`, reusing `agent.py` phases per batch — run it
   on the existing DAG to assemble/verify what's already proved (no new proving) → validates the
   plumbing end-to-end.
3. Wire recursive decomposition (`decompose.py`) so the scheduler grows the DAG on hard nodes.
4. `deep_research.py`: IterResearch loop first (single-thread, proof-state report + workspace
   reconstruction), then Heavy-mode synthesis. Validate on one known-hard node.
5. Dashboard over the DAG + resume tests (kill mid-run, resume).
Then point it at a fresh big target via `paper_source` and let it run for days — fully local.
