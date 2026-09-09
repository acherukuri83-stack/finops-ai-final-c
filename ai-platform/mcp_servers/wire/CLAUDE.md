# mcp_servers/wire — conventions (Phase B — Wires, optional module)

- Wraps the **simulated outgoing-wire book** — in-process, fixture-backed (`store.py`),
  like `platform` / `repo` / `ci`. No `client.py`, no `_enterprise`, no `@guard`. Tools
  return plain dicts / lists or a `NOT_FOUND` envelope; never raise.
- `store.py` is facts only — wires, holds, standing instructions, the reviewer queue,
  cutoffs, one screening hit, available balances (cash-lite), and a deterministic
  `NOW` / `TODAY`. Nothing says a wire should be routed, rescheduled, or frozen.
- Reads: `get_wire`, `get_wire_audit_trail`, `get_standing_instructions`,
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
- `store.reset()` clears the action log + reviewer queue — tests call it in an autouse
  fixture.
- Deferred: seeded Postgres + a `simulator` planter (this is Python fixtures); a scored
  eval for Sc. 7 / 13 / 14 / 15 / 16 (documented in `docs/eval-scenarios.md`, unit-tested
  in `tests/test_wire.py`); a wire corpus (`Wire Processing Guide`, sanctions procedure).
