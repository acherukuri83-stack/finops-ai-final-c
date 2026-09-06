# Backlog

Ideas that are out of the current phase's scope. Append; don't build.

- `docs/tool-contracts.md`'s `Account` shape lists `risk_flags[]`, and `Client`/`Counterparty`
  mention `restrictions[]`/`contacts[]` — the Phase A schema (`V2__phase_a_schema.sql`) has no
  risk-flag or counterparty-contact tables, and restrictions are only modeled at the account
  level. PR2's enterprise endpoints return `risk_flags: []` and `contacts: []` always (no data
  source), and `GET /clients/{id}` aggregates restrictions across the client's accounts rather
  than having its own restrictions table. Revisit if a scenario ever needs real values here.
- `PUT /accounts/{id}/ssi` (enterprise write endpoint) always creates a new SSI version and
  closes out the prior one; it has no concept of validating the caller's intent beyond that —
  by design, since `update_ssi`'s approval/rationale checks are the MCP tool's job in W3, not
  this tier's. 
