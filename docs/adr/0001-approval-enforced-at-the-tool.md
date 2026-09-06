# ADR-0001 — Approval is enforced at the write tool

**Status:** accepted · **Phase:** A

## Decision
Every MCP write tool takes an `approval_id` and validates it against `case.get_approval` before any side effect. The UI, the agent, and the orchestrator are not trusted to gate writes.

## Why
An agent is a component that can be wrong. If the only thing between a wrong proposal and a mutated record is a prompt or a UI button, the system's safety depends on the least reliable parts. Putting the check in the tool means it holds under every caller — agent, test harness, curl.

## Consequences
- Write tools are slightly more coupled (they know about `case-server`).
- The eval harness can assert the guard directly (forged / PENDING / REJECTED ids).
- PR review has a mechanical rule: a write tool without the check is a BLOCKER (security §4.1).
