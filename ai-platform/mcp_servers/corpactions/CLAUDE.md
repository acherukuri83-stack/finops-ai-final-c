# mcp_servers/corpactions — conventions (Phase F)

- Simulated corporate-actions book. `store.py` sits on `mcp_servers/_finance_store.py` —
  MEM mode (dict fixtures, unit suite) + SQL mode over seeded Postgres (`ca_events` /
  `ca_entitlements` / `ca_elections`, seeded by `simulator`). No `client.py`, no
  `_enterprise`. Tools return dicts / lists or a `NOT_FOUND` envelope; never raise. Keep
  the `Table` defs in sync with `simulator/simulator/finance_tables.py`.
- Reads: `get_ca_event`, `list_ca_events`, `get_entitlement` (the held/lent split over the
  record date), `get_election`.
- Writes (approval-gated via `check_approval`): `submit_election`, `raise_claim`
  (manufactured-payment claim on the borrower for the lent slice), `escalate_ca`.
- **Record-date / election-deadline is code, not prompt**
  (`agent_core/corpactions.py::_enforce_record_date`):
  - a `CASH_DIVIDEND` on an entitlement with `lent_qty > 0` → the lent slice is a
    `raise_claim` on the borrower; any `submit_election` on it is dropped;
  - an elective event past `election_deadline` → `submit_election` → `escalate_ca`.
- `store.reset()` clears the mutable action log — tests call it in an autouse fixture.
