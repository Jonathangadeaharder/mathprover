## ADDED Requirements

### Requirement: API dispatch endpoint
The MathProver UI SHALL expose `POST /api/dispatch` spawning `agents/dispatch.py`.

#### Scenario: Dispatch from UI
- **WHEN** user confirms Run Agent on a frontier node
- **THEN** a run record is created and SSE stream starts within 5 seconds

### Requirement: Graph bootstrap fallback
When Lean files lack `@paper-id` decorators, the project SHALL use `scripts/bootstrap_graph.py` to populate `graph.json`.

#### Scenario: Reindex without decorators
- **WHEN** user clicks Reindex in Topbar
- **THEN** bootstrap_graph runs before or instead of empty build_graph output
