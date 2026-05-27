# MathProver

Project-agnostic Lean proof workbench: SvelteKit UI, agent dispatch (Goedel MLX / Aristotle),
graph indexing, and run registry. Works against any Lean project that provides
`lakefile.lean`, `mathprover.toml`, and `.mathprover/graph.json`.

## Quick start

```bash
# UI
cd mathprover-ui && pnpm install && pnpm dev

# Python agents (from repo root)
cd agents && uv sync
export MATHPROVER_HOME="$(pwd)/.."
export MATHPROVER_PROJECT_PATH="/path/to/your/lean-project"
uv run python dispatch.py --root "$MATHPROVER_PROJECT_PATH" --node <node-id>
```

Open `http://localhost:5173/workspace?project=/path/to/lean-project`.

## Layout

```
mathprover/                 # this repo (MATHPROVER_HOME)
├── mathprover-ui/          # SvelteKit workbench
├── agents/                 # dispatch router + prover backends
├── scripts/
│   ├── build_graph.py      # scan .lean decorators → graph.json
│   └── index_runs.py       # merge runs into graph metadata
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

## Related repos

- [lean-runtime-analysis](https://github.com/VidiomTM/lean-runtime-analysis) — Lean formalization (LBTCoupling)
- [PPSN_FOGA_GECCO](https://github.com/VidiomTM/PPSN_FOGA_GECCO) — paper portfolio and empirical scripts
