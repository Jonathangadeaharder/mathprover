## Context

Brownfield SvelteKit UI reading static `graph.json`; Python CLI dispatch working but invisible to UI.

## Goals / Non-Goals

**Goals:**
- Thin API layer over existing filesystem artifacts
- Live SSE log stream during Goedel runs
- Router preview before dispatch confirm

**Non-Goals:**
- Separate FastAPI server
- Rewriting proof indexer decorators

## Decisions

1. **SvelteKit +server.ts** — keep API in mathprover-ui, spawn Python subprocess
2. **Run sidecar JSON** — `.mathprover/runs/<id>.json` bridges CLI and UI
3. **bootstrap_graph.py** — fallback when Lean lacks @paper-id decorators

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Long Goedel runs appear stuck | Streaming + heartbeats (implemented) |
| graph.json wiped by build_graph | bootstrap_graph.py + reindex uses bootstrap |
