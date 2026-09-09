# mcp_servers/platform — conventions (Phase E)

- This server wraps the **simulated platform tier** — job scheduler, deploy pipeline,
  config service, message bus. It is *in-process and fixture-backed* (`store.py`), like
  `case`, not an HTTP wrapper: **no `client.py`, no `_enterprise`, no `@guard`**. Tools
  return plain dicts / lists or a `NOT_FOUND` envelope; they never raise.
- `store.py` holds planted **facts only** — a job failed, a deploy changed a key, a topic
  has lag. Nothing states *why*. The Developer Agent derives the cause (hard rule §9).
- Reads: `get_service_health`, `get_job_runs`, `get_deployments`, `diff_config`,
  `get_topic_lag`, `get_platform_logs`, `get_source`.
- Writes: `open_change_ticket`, `rerun_job`, `replay_message` — each validates an APPROVED
  `approval_id` via `_common.check_approval` (ADR-0001) before touching the one mutable
  table (`change_tickets`). **There is deliberately no deploy / merge / approve /
  config-write tool** (`tests/test_developer.py` asserts the whole tool surface is
  disjoint from that set).
- `store.reset()` clears the mutable table — tests call it in an autouse fixture.
- `fix_strategy` (revert vs fix_forward) is decided in `agent_core/developer.py` from the
  deployment's `release_note`, not in the synthesis prompt.
