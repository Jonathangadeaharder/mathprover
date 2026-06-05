# MathProver

Project-agnostic Lean proof workbench: SvelteKit UI, agent dispatch (Goedel MLX / Aristotle),
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
│   ├── router.py           # Goedel/Aristotle selection logic
│   ├── config.py           # mathprover.toml loader
│   ├── resource_guard.py   # exclusive Goedel lock + memory checks
│   ├── run_registry.py     # .mathprover/runs/ index
│   ├── lean_pipeline.py    # compile/extract helpers
│   ├── prompts.py          # prompt builders for Goedel/Aristotle
│   └── backends/
│       ├── goedel.py       # Goedel-Prover-V2-32B MLX backend
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
| `GOEDEL_PROVER_PATH` | Local Goedel runner script (see `mathprover.toml.example`) |
| `ARISTOTLE_API_KEY` | Required for Aristotle cloud dispatch (see `mathprover.toml.example`) |

**Note:** CodeQL is disabled on PRs while this repo is private without a GitHub Advanced Security license. Semgrep runs on every PR; enable CodeQL in `.github/workflows/pr-gate.yml` after GHAS or going public.

## Related repos

- [lean-runtime-analysis](https://github.com/VidiomTM/lean-runtime-analysis) — Lean formalization (LBTCoupling)
- [PPSN_FOGA_GECCO](https://github.com/VidiomTM/PPSN_FOGA_GECCO) — paper portfolio and empirical scripts
