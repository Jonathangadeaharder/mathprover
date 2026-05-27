## ADDED Requirements

### Requirement: Run progress heartbeats
Goedel pipeline SHALL update run records with phase, token count, and tok/s during generation.

#### Scenario: Heartbeat during sample 1
- **WHEN** Goedel generates tokens for 15+ seconds
- **THEN** log contains `[heartbeat]` line
- **AND** `.mathprover/runs/<id>.json` has updated `heartbeat_at`
