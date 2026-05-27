## Purpose

Define the SvelteKit MathProver workbench: graph visualization, real agent dispatch, and live run monitoring.

## Requirements

### Requirement: Graph as source of truth
The MathProver UI SHALL read project state from `.mathprover/graph.json`, enriched at runtime with run history from `.mathprover/runs/`.

#### Scenario: Page load
- **WHEN** user opens `/workspace`
- **THEN** the DAG displays node status, proof_folder links, and active agent if running

### Requirement: Real dispatch wiring
Run Agent SHALL invoke `agents/dispatch.py` via `POST /api/dispatch`, not navigate to a mock tab.

#### Scenario: User dispatches L661
- **WHEN** user confirms dispatch with prover `auto`
- **THEN** router selects Goedel for frontier leaf
- **AND** a run record is created under `.mathprover/runs/`
- **AND** Agent runs tab streams the log via SSE

### Requirement: Live progress visibility
Active Goedel runs SHALL emit heartbeats (phase, token count, tok/s) to run records and the log at least every 15 seconds during generation.

#### Scenario: Long generation
- **WHEN** Goedel generates up to 28K tokens for sample 1
- **THEN** the UI shows `generating` phase with token stats before compile
- **AND** `tail -f` on the attempt log shows streaming output

### Requirement: Node identity mapping
Graph nodes SHALL include `proof_folder` linking UI node IDs (e.g. `L661_sel_prob`) to `proofs/L661_coea_sel_measure_prob/`.

#### Scenario: Dispatch resolution
- **WHEN** API receives nodeId `L661_sel_prob`
- **THEN** dispatch resolves to folder `L661_coea_sel_measure_prob`
