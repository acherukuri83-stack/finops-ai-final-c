# mcp_servers/cash — conventions (Phase F)

- Simulated cash & funding book. `store.py` sits on `mcp_servers/_finance_store.py` — MEM
  mode (dict fixtures, unit suite) + SQL mode over seeded Postgres (`cash_breaks` /
  `funding_ladders` / `credit_facilities`, seeded by `simulator`). No `client.py`, no
  `_enterprise`. Tools return dicts / lists or a `NOT_FOUND` envelope; never raise. Keep
  the `Table` defs in sync with `simulator/simulator/finance_tables.py`.
- Reads: `get_cash_break`, `list_cash_breaks`, `get_funding_ladder`, `get_facility`.
- Writes (approval-gated via `check_approval`): `arrange_funding`, `move_cash`,
  `escalate_cash` — proposals only.
- **Fund vs escalate is code, not prompt**:
  `agent_core/cash.py::_enforce_funding_cutoff` converts `arrange_funding` / `move_cash` →
  `escalate_cash` once `store.NOW` is past the break's `funding_cutoff`, and sets
  `root_cause = FUNDING_CUTOFF_MISSED`.
- `store.reset()` clears the mutable action log — tests call it in an autouse fixture.
