# ADR-0003 — We write the orchestrator, not a framework

**Status:** accepted · **Phase:** A

## Decision
The agent loop — plan → tool loop (budget, re-plan on contradiction) → synthesize →
outcome rules → policy → open a case — is ~250 lines of our own code in
`agent_core/loop.py`. No LangGraph, LangChain, CrewAI, or similar.

## Why
The loop is small and every rule in it is a decision we want to see and test:
the tool budget, when a re-plan fires, that outcome classification
(`INSUFFICIENT_EVIDENCE`, `TOOL_DEGRADED`) is code and not a prompt, that policy runs
*after* synthesis and *before* a case opens. A framework would hide those seams behind
its own abstractions and add a dependency whose upgrade cadence we don't control, to
save code we can afford to own. Structured output, retries, and spans are thin helpers
(`agent_core/reasoning/`, `agent_core/spans.py`), not a runtime.

## Consequences
- The loop is a single readable file; a reviewer can trace one investigation top to
  bottom.
- We carry the maintenance of the loop itself (re-plan heuristics, budget tuning) —
  acceptable at this size.
- Multi-agent delegation (Phase C) is our protocol to design, not a framework's.
