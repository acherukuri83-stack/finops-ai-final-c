# mcp_servers/stockloan — conventions (Phase F core slice)

- Wraps the **simulated securities-lending book** — in-process, fixture-backed
  (`store.py`), like `case` and `platform`. No `client.py`, no `_enterprise`, no
  `@guard`. Tools return plain dicts / lists or a `NOT_FOUND` envelope; never raise.
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
- `store.reset()` clears the mutable action log — tests call it in an autouse fixture.
- Deferred: a seeded table + `simulator` planter (this is Python fixtures for now);
  Margin / CorpActions / Cash domains; mixed-client Scenario 30 (`docs/backlog.md`).
