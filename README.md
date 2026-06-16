# MathProver

Project-agnostic Lean proof workbench: SvelteKit UI, agent dispatch (local OpenAI-compatible
oprover/qwen / Aristotle),
graph indexing, and run registry. Works against any Lean project that provides
`lakefile.lean`, `mathprover.toml`, and `.mathprover/graph.json`.

## Quick start

```bash
cp .env.example .env   # edit paths, then: source .env
make agents-sync
make reindex           # Lean project graph
make ui                # workbench
make dispatch NODE=L661_coea_sel_measure_prob
```

Open `http://localhost:5173/workspace?project=/path/to/lean-project`.

## Hard-proof workflow

MathProver treats research-grade Lean goals as small proof developments, not as one-shot tactic
holes. The local pipeline now writes a proof architecture artifact before proving:

```bash
python3 agents/proof_architecture.py architect-proof \
  --project-root ~/projects/lean-runtime-analysis \
  --goal-file ~/projects/lean-runtime-analysis/proofs/A3a_core/attempt.lean \
  --out ~/projects/lean-runtime-analysis/.mathprover/pipeline/A3a.architecture.md
```

For API discovery, use a disposable scratch probe before editing the target file:

```bash
python3 agents/proof_architecture.py scratch-probe \
  --project-root ~/projects/lean-runtime-analysis \
  --goal-file ~/projects/lean-runtime-analysis/proofs/A3a_core/attempt.lean \
  --open-private-from M10LevelCountCoupling \
  --check ideal_count_kernel_eval ideal_pop_count_step_expectation_eq_level_vector
```

Every non-`--skip-verify` dispatch now runs the final proof gate after `lake build`: compile the
attempt file, reject `sorry`/`admit`/`exact?`/`sorryAx`/new `axiom`, then append `#print axioms` in
a copy and reject unexpected custom axioms. You can run that gate directly:

```bash
python3 agents/proof_architecture.py final-verify \
  --project-root ~/projects/lean-runtime-analysis \
  --file ~/projects/lean-runtime-analysis/proofs/A3a_core/attempt.lean
```

Batch proof attempts live in MathProver too, not in Lean projects:

```bash
python3 agents/prove_all.py \
  --project-root ~/projects/lean-runtime-analysis \
  --node A3a_core \
  --node L661_coea_sel_measure_prob \
  --prover auto \
  --max-rounds 2
```

MTPLX qwen smoke test:

```bash
mtplx start --model Youssofal/Qwen3.6-27B-MTPLX-Optimized-Speed
python3 agents/mtplx_smoke.py --chat
```

## Refutation-first (diagnose before you grind)

A hard `sorry` may be unprovable because the **statement is false** (e.g. a hypothesis dropped in
formalization). Before spending prover or cloud budget, try to *disprove* it: MathProver builds
`¬ (∀ binders, conclusion)` from the goal and runs the same OProver agentic loop on it. A verified,
sorry-free negation proof is a machine-checked counterexample — the statement is false as stated.

```bash
# refutation only:
python3 agents/pipeline.py --refute \
  --goal-file ~/projects/lean-runtime-analysis/proofs/<node>/attempt.lean \
  --project-root ~/projects/lean-runtime-analysis

# probe N rounds before proving, and stop if disproved:
python3 agents/pipeline.py --refute-first 4 --goal-file … --project-root …

# at the node/dispatch level (skips the prover if a counterexample is found, exit code 3):
python3 agents/dispatch.py --node <node> --prover aristotle --refute-first 4
```

This caught a real defect: the quarantined `Quarantine.LBT.level_based_theorem` was **false as
stated** (it dropped the published `z_j ∈ (0,1]`); see `proofs/M7_level_based_theorem/` and
`PROOF_PATTERNS.md` (P1, P2). Reusable proof/diagnosis patterns from successful runs live in
[`PROOF_PATTERNS.md`](PROOF_PATTERNS.md).

## Lean project contract

Any Lean repo can use MathProver if it provides:

| File | Purpose |
|------|---------|
| `lakefile.lean` | Lake build (UI marker) |
| `mathprover.toml` | Prover routing (see `mathprover.toml.example`) |
| `scripts/bootstrap_graph.py` | Optional hand-maintained DAG (bypasses decorator scanning) |
| `scripts/reindex_graph.py` | Optional; delegates to MathProver (see [lean-runtime-analysis](https://github.com/VidiomTM/lean-runtime-analysis)) |
| `.mathprover/graph.json` | Generated DAG (gitignored in most projects) |
| `proofs/<folder>/` | Optional worker scaffolds for dispatch |

Reference implementation: [VidiomTM/lean-runtime-analysis](https://github.com/VidiomTM/lean-runtime-analysis).

## Layout

```
mathprover/                 # this repo (MATHPROVER_HOME)
├── mathprover-ui/          # SvelteKit workbench
├── agents/                 # dispatch router + prover backends
│   ├── dispatch.py         # CLI: dispatch a proof node
│   ├── preview.py          # CLI: print routing decision as JSON
│   ├── router.py           # oprover/qwen/Aristotle selection logic
│   ├── config.py           # mathprover.toml loader
│   ├── run_registry.py     # .mathprover/runs/ index
│   ├── lean_pipeline.py    # compile/extract helpers
│   ├── prompts.py          # prompt builders for Goedel/Aristotle
│   └── backends/
│       ├── lmstudio.py     # local OpenAI-compatible backend (LM Studio or MTPLX)
│       └── aristotle.py    # Aristotle cloud prover backend
├── scripts/
│   ├── build_graph.py      # scan .lean decorators → graph.json
│   ├── index_runs.py       # merge runs into graph metadata
│   └── reindex_project.py  # one-shot reindex for any Lean project
└── openspec/               # workbench + dispatch specs

your-lean-project/          # separate repo (e.g. lean-runtime-analysis)
├── lakefile.lean
├── mathprover.toml         # prover routing for this project
├── proofs/                 # worker scaffolds (optional)
└── .mathprover/
    ├── graph.json
    ├── runs/
    └── attempts/
```

## Environment

| Variable | Purpose |
|----------|---------|
| `MATHPROVER_HOME` | Path to this repo (auto-detected when UI runs from `mathprover-ui/`) |
| `MATHPROVER_PROJECT_PATH` | Default Lean project to open |
| `MATHPROVER_ALLOWED_ROOTS` | Colon-separated allowlist for project picker |
| `MATHPROVER_LOCAL_BASE_URL` | Default local OpenAI-compatible endpoint for oprover/gemma |
| `MATHPROVER_MTPLX_BASE_URL` | MTPLX OpenAI-compatible endpoint for qwen, default `http://127.0.0.1:8000/v1` |
| `MATHPROVER_QWEN_MODEL` | qwen role model, default `Youssofal/Qwen3.6-27B-MTPLX-Optimized-Speed` |
| `MATHPROVER_TELEMETRY` | Optional JSONL telemetry toggle, default enabled |
| `ARISTOTLE_API_KEY` | Required for Aristotle cloud dispatch (see `mathprover.toml.example`) |

**Note:** CodeQL is disabled on PRs while this repo is private without a GitHub Advanced Security license. Semgrep runs on every PR; enable CodeQL in `.github/workflows/pr-gate.yml` after GHAS or going public.

## Related repos

- [lean-runtime-analysis](https://github.com/VidiomTM/lean-runtime-analysis) — Lean formalization (LBTCoupling)
- [PPSN_FOGA_GECCO](https://github.com/VidiomTM/PPSN_FOGA_GECCO) — paper portfolio and empirical scripts
