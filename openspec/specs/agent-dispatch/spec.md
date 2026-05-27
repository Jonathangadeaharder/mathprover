## Purpose

Define Goedel and Aristotle prover routing, pipeline configuration, and run artifact conventions.

## Requirements

### Requirement: Prover routing
Dispatch SHALL route via `mathprover.toml` and `agents/router.py`.

#### Scenario: Frontier leaf
- **WHEN** folder has no subproofs and failure count < escalation threshold
- **THEN** `default_leaf` prover (Goedel) is selected

#### Scenario: Capstone
- **WHEN** folder is `L1012_r_local_G2` or in `routing.capstone`
- **THEN** `default_capstone` prover (Aristotle) is selected

#### Scenario: Escalation
- **WHEN** failure count ≥ `escalate_after_failures` (default 3)
- **THEN** Aristotle is selected regardless of leaf status

### Requirement: Goedel pipeline configuration
Goedel SHALL use pass@N with verifier-guided self-correction per official Goedel-Prover-V2 recommendations.

#### Scenario: Default run
- **WHEN** Goedel dispatches without override
- **THEN** config uses 4 samples, temp 1.0, 28K initial tokens, 2 correction rounds × 8K
- **AND** exclusive lock prevents parallel Goedel loads

### Requirement: Aristotle async pipeline
Aristotle SHALL submit via `aristotlelib`, poll to completion, download tarball, and reject proofs containing `sorry`.

#### Scenario: Capstone dispatch
- **WHEN** L1012 is dispatched to Aristotle
- **THEN** prompt includes `paper_source.md` and upstream lemma context in `attempt.lean`

### Requirement: Run artifacts
Every dispatch SHALL write `.mathprover/runs/<id>.json` and append to `proofs/<folder>/status.md`.

#### Scenario: Run completes
- **WHEN** dispatch exits
- **THEN** run record status is `ok` or `failed`
- **AND** `graph.json` attempts counter increments
- **AND** `activeAgent` is cleared
