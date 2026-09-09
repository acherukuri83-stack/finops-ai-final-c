# mcp_servers/margin — conventions (Phase F)

- Simulated margin & collateral book. `store.py` sits on `mcp_servers/_finance_store.py`
  — MEM mode (dict fixtures, unit suite) + SQL mode over seeded Postgres (`margin_calls` /
  `margin_status` / `collateral` / `collateral_eligibility`, seeded by `simulator`). No
  `client.py`, no `_enterprise`. Tools return dicts / lists or a `NOT_FOUND` envelope;
  never raise. Keep the `Table` defs in sync with
  `simulator/simulator/finance_tables.py`.
- Reads: `get_margin_call`, `list_margin_calls`, `get_margin_status`, `get_collateral`,
  `get_eligibility`.
- Writes (approval-gated via `check_approval`): `post_collateral`, `substitute_collateral`,
  `escalate_margin` — proposals only.
- **Meet vs close-out is code, not prompt**:
  `agent_core/margin.py::_enforce_call_window` converts `post_collateral` /
  `substitute_collateral` → `escalate_margin` once `store.TODAY` is past the call's
  `due_by`, and sets `root_cause = CALL_WINDOW_MISSED`.
- `store.reset()` clears the mutable action log — tests call it in an autouse fixture.
