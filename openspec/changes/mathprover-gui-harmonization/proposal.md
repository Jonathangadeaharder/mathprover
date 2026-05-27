## Why

The MathProver UI was a polished shell disconnected from the real `agents/dispatch.py` pipeline. Users could click Run Agent but saw synthetic logs while Goedel ran in a terminal with no visibility.

## What Changes

- SvelteKit API routes for dispatch, SSE log streaming, project refresh
- Run registry (`.mathprover/runs/`) and graph enrichment
- Wire RunAgentButton → POST /api/dispatch
- Goedel streaming heartbeats for live token progress
- Frontier dispatch buttons, router preview in PremisePicker

## Capabilities

### New Capabilities
- `mathprover-workbench`: Full spec for UI + API contract
- `agent-dispatch`: Run records, routing, heartbeats

### Modified Capabilities
<!-- baseline specs created fresh -->

## Impact

- `mathprover-ui/src/routes/api/`
- `agents/run_registry.py`, `backends/goedel.py`
- `models/goedel-prover-v2-32b/run_pipeline.py` (streaming)

## Non-Goals

- Stub models (opus, gpt5) in UI
- Paper⇄Lean block indexing (still empty in graph)
