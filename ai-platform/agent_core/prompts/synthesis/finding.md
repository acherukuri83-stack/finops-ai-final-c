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
- **Counterparty SSI mismatch — decide which side is stale from the evidence:**
  - Our SSI history shows a recent change to the participant *we* are on, no custodian
    notice says otherwise, and the counterparty is affirming the *older* participant →
    `COUNTERPARTY_INSTRUCTION_STALE`; action `resubmit_settlement` after re-affirmation;
    `update_ssi` is a rejected alternative (Settlement Handbook §8.4 ¶3).
  - A custodian notice (or *Custodian Notices §1*) shows our account moved to the
    participant the **counterparty is affirming**, on or before the settlement date, and
    our SSI was never updated to it → `CLIENT_SSI_STALE`; action `update_ssi` to that
    participant, then `resubmit_settlement`; the rejected alternative is resubmitting
    without correcting the SSI.
  - Our SSI and the affirmation name the same participant but the counterparty's
    instruction on file for us is past its `valid_to` → `COUNTERPARTY_INSTRUCTION_EXPIRED`;
    action `escalate` for a refreshed counterparty instruction, then `resubmit_settlement`.
  - The mismatch is gone — the current affirmation and our current SSI now name the same
    participant, and there has been no settlement attempt since — → `REMEDIATED_PENDING_RESUBMIT`;
    the only action is `resubmit_settlement` (no re-affirmation, no SSI change, no escalation).
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
