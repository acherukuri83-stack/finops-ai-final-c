# mcp_servers/stockloan — conventions (Phase F)

- Wraps the **simulated securities-lending book**. `store.py` sits on
  `mcp_servers/_finance_store.py`: a **MEM** mode (dict fixtures, unit suite) and a **SQL**
  mode over seeded Postgres (`stock_loans` / `loan_recalls` / `loan_rerates` /
  `lending_availability`, seeded by `simulator` on `make seed`). Mode is `CASES_INMEMORY`;
  `tests/conftest.py` forces MEM. No `client.py`, no `_enterprise`, no `@guard`. Tools
  return plain dicts / lists or a `NOT_FOUND` envelope; never raise.
- `store.py` is facts only — loans, recalls, rerates, lending availability, and a
  deterministic `TODAY`. Nothing says a recall is late or a rate is wrong.
- Reads: `get_loan`, `list_loans`, `get_recall`, `get_rerate_history`,
  `get_lending_availability`.
- Writes (approval-gated via `_common.check_approval`): `initiate_recall`, `rerate_loan`,
  `book_buy_in` — proposals only, no override of a risk decision.
- **Recall vs buy-in is code, not prompt**: `agent_core/stockloan.py::_enforce_recall_window`
  converts `initiate_recall` → `book_buy_in` (and back) against
  `store.RECALL_NOTICE_DAYS` before `loan.return_needed_by`. Calendar days for the slice;
  a fuller version uses the settlement calendar.
- `store.reset()` — MEM: reload the seed snapshot + drop the action log. SQL: drop the
  action log only (the simulator owns the seeded rows). Tests call it in an autouse fixture.
- Keep the `Table` defs in sync with `simulator/simulator/finance_tables.py` by hand.
