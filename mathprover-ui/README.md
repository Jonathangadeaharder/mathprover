# MathProver UI

SvelteKit workbench for Lean proof projects. Reads `<project>/.mathprover/graph.json`,
dispatches agents via `mathprover.toml`, and streams run logs.

## Run

```bash
pnpm install
export MATHPROVER_HOME="$(cd .. && pwd)"
export MATHPROVER_PROJECT_PATH="/path/to/lean-project"
pnpm dev
```

Open `http://localhost:5173/workspace?project=/path/to/lean-project`.

See the [repository README](../README.md) for the full layout and environment variables.
