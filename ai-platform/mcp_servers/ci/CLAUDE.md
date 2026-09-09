# mcp_servers/ci — conventions (Phase E — review mode)

- Deterministic-check results over a PR — `run_static_analysis`, `run_security_scan`,
  `get_test_coverage`, `run_tests`, `run_eval`. All **read-only**; in-process,
  fixture-backed (`store.py`).
- The **model interprets** these results and prioritises; it never decides pass/fail on
  the deterministic ones (agent-plan Phase 12). In this slice `agent_core/review.py`
  applies fixed rules over them (security HIGH → BLOCKER, any failing test → BLOCKER,
  coverage ≤ −1% → MINOR).
- `run_eval` is fixture-backed here; live it costs real model calls and is
  `workflow_dispatch`-only (paused for C+, `docs/backlog.md`).
