# mcp_servers/wire — conventions (Phase B — Wires, optional module)

- Wraps the **simulated outgoing-wire book**. `store.py` sits on
  `mcp_servers/_finance_store.py` (`FinanceStore` — generic, not finance-specific): a MEM
  mode (dict fixtures, unit suite) and a SQL mode over 6 seeded Postgres tables (`wires`,
  `wire_standing_instructions`, `wire_screening`, `wire_balances`, `wire_audit_events`,
  `wire_actions`), seeded by `simulator` on `make seed`. No `client.py`, no `_enterprise`,
  no `@guard`. Tools return plain dicts / lists or a `NOT_FOUND` envelope; never raise.
  Keep the `Table` defs in sync with `simulator/simulator/wire_tables.py` by hand.
- `store.py` is facts only — wires, holds, standing instructions, cutoffs (static config,
  not a table), one screening hit, available balances (cash-lite), and a deterministic
  `NOW` / `TODAY`. Nothing says a wire should be routed, rescheduled, or frozen. The
  reviewer queue is derived from the OPEN `route_to_reviewer` actions, not a table.
- Reads: `get_wire`, `list_wires`, `get_wire_audit_trail`, `get_standing_instructions`,
  `get_approval_queue`, `get_cutoff`, `get_wire_screening`, `get_available_balance`.
- Writes (approval-gated via `_common.check_approval`): `route_to_reviewer`,
  `add_standing_instruction`, `reschedule_value_date`, `open_compliance_referral`.
- **`release_wire` does not exist** — release is a human-only `WIRE_REVIEWER` action in
  the portal. `tests/test_wire.py` asserts it is absent from every discovered tool list.
- **Maker/checker, cutoff, screening are code, not prompt**
  (`agent_core/wire.py::_enforce_wire_controls`):
  - screening `HIT` → drop everything except `open_compliance_referral`; `root_cause =
    SCREENING_HIT`;
  - available balance < wire amount → drop wire actions, funding question in
    `open_questions`; `root_cause = INSUFFICIENT_BALANCE`;
  - same-day cutoff passed → `route_to_reviewer` → `reschedule_value_date`; `root_cause =
    CUTOFF_MISSED`;
  - beneficiary account not on the client's standing instructions → ensure
    `route_to_reviewer`; `root_cause = NEW_BENEFICIARY_REVIEW`.
- `store.reset()` — MEM: reload the seed snapshot + drop the action log. SQL: drop the
  action log only. Tests call it in an autouse fixture; `tests/conftest.py` forces MEM.
- Corpus: `knowledge/corpus/wire-processing-guide.md` + `sanctions-procedure.md` +
  `incidents/INC-2001…2005.md`; `planner/wire.md` / `synthesis/wire.md` cite the section.
- Deferred: the scored `make eval` run for Sc. 7 / 13–16 (YAMLs seeded and ready — with
  the C+ sweep); the portal `WIRE_REVIEWER` release flow.
