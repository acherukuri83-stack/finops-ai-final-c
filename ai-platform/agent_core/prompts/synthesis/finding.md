Write the `Finding` for this investigation from the observations.

- `subject`: `{type: "trade", id: <trade_id>}`.
- `root_cause`: a short code in UPPER_SNAKE, e.g. `COUNTERPARTY_INSTRUCTION_STALE`,
  `CLIENT_SSI_STALE`, `SECURITY_MASTER_INCONSISTENT`, `COMPLIANCE_RESTRICTION`,
  `DELIVERY_SHORTFALL`, `COUNTERPARTY_INSTRUCTION_EXPIRED`, `DUPLICATE_BOOKING`,
  `REMEDIATED_PENDING_RESUBMIT`. Leave it null if the evidence does not support one.
- `outcome`: `RESOLVED_CAUSE` when you have a cause and its evidence; otherwise leave it
  and let the caller's rules decide.
- `evidence`: one `EvidenceRef` per fact you rely on. `kind` is `tool`, `knowledge`,
  `incident`, or `log`. `ref` is the tool name (e.g. `get_ssi_history`); for a knowledge
  chunk, `"<doc> §<section>"` from its `doc` and `section` fields (e.g.
  `"Settlement Handbook §8.4"`), or just `<doc>` when it has no section; for an incident,
  its id (e.g. `INC-1001`). Set `cited: true` for the ones your conclusion actually rests
  on; `cited: false` for retrieved-but-unused chunks, and add a one-line note for each of
  those to `open_questions`.
- Every root-cause claim must cite at least one tool result **and**, when a relevant
  procedure or incident was retrieved, at least one `knowledge`/`incident` ref.
- `proposed_actions`: what a human should approve. Use the action names from the tool
  allowlist (`resubmit_settlement`, `cancel_trade`, `update_ssi`,
  `open_compliance_referral`, `escalate`). Give `rationale` and `impact`.
- `rejected_alternatives`: actions a reader might expect that you are **not** proposing,
  with the reason and the evidence. If you propose a write, name at least one.
  For an SSI mismatch where our instruction is current, `update_ssi` is a rejected
  alternative — cite the handbook paragraph that says so.
- `confidence_basis`: one sentence on what the confidence rests on — never a bare number.

Do not invent ids, tool names, or document sections. Every id and section in the Finding
must appear in an observation.
