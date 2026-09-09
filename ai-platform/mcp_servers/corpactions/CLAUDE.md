# mcp_servers/corpactions — conventions (Phase F)

- Simulated corporate-actions book — in-process, fixture-backed (`store.py`), like
  `margin` / `stockloan`. No `client.py`, no `_enterprise`. Tools return dicts / lists or
  a `NOT_FOUND` envelope; never raise.
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
