# ADR-0002 — A counterparty SSI mismatch never resolves by overwriting the client SSI

**Status:** accepted · **Phase:** A

## Decision
When a settlement fails on `COUNTERPARTY_SSI_MISMATCH`, the agent determines which instruction is current from SSI history and the counterparty's affirmation. If the client SSI is current, the action is re-affirmation + resubmit. `update_ssi` is only proposed when independent evidence (e.g. a custodian notice) shows our record is stale — and it is approval-gated.

## Why
Overwriting a valid client SSI to match a counterparty's affirmation "fixes" one trade and breaks every other trade for that account. This is the mistake the obvious implementation makes, and it is the one Scenario 1 exists to catch. The agent must list `update_ssi` as a rejected alternative with the handbook citation.

## Consequences
- Scenario 1 and 2 form a pair: same failure code, opposite correct action, decided by evidence.
- The Risk/Client Agent (Phase C) owns the only path to `update_ssi`.
