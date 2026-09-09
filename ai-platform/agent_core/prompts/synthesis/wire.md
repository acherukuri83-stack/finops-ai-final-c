Write the `Finding` for this wire investigation from the observations.

- `subject`: `{type: "wire", id: <wire_id>}`.
- `root_cause`: a short code in UPPER_SNAKE — `NEW_BENEFICIARY_REVIEW` (beneficiary not on
  the client's standing instructions), `CUTOFF_MISSED` (past the same-day cutoff),
  `SCREENING_HIT` (sanctions screening returned a hit), `INSUFFICIENT_BALANCE` (available
  balance below the wire amount), `BENEFICIARY_MISMATCH` (beneficiary account differs from
  the standing instruction for that beneficiary). Leave it null if the evidence does not
  support one — the caller finalises it against the wire's facts.
- `evidence`: one `EvidenceRef` (`kind: "tool"`) per fact — `get_wire`,
  `get_standing_instructions`, `get_wire_screening`, `get_cutoff`, `get_available_balance` —
  and one `EvidenceRef` (`kind: "knowledge"`) for the governing section you relied on:
  `Wire Processing Guide §5.2` (new beneficiary), `§9.1` (cutoff), `§7.4` (funds), or
  `Sanctions Procedure §2.1` / `§2.4` (screening hit). Cite it as `"<doc> §<section>"`.
- `proposed_actions` — from the `wire` allowlist only (`route_to_reviewer`,
  `add_standing_instruction`, `reschedule_value_date`, `open_compliance_referral`,
  `escalate`). **You are the maker; never propose releasing a wire.**
  - **Screening hit** → `open_compliance_referral` with `params`: `wire_id`, `reason`.
    Propose **nothing else** — the referral is the whole answer.
  - **New beneficiary, cutoff still open** → `route_to_reviewer` with `params`: `wire_id`,
    `reason`, `packet` (a short review packet: the hold reason, the beneficiary check, the
    cutoff time). If a standing instruction should exist for this beneficiary going
    forward, add `add_standing_instruction` as a **separate** action — it is not a
    substitute for the review.
  - **Cutoff passed** → `reschedule_value_date` with `params`: `wire_id`,
    `new_value_date`, `reason`. Do **not** propose `route_to_reviewer` for a same-day
    release.
  - **Insufficient balance** → propose **no wire action**; put the funding shortfall in
    `open_questions` (the caller does this too).
- `rejected_alternatives`: when you propose `reschedule_value_date`, name a same-day
  `route_to_reviewer` as rejected because the cutoff has passed. When you propose
  `open_compliance_referral`, name `route_to_reviewer` as rejected because a screening hit
  freezes remediation.
- `confidence_basis`: one sentence — what the conclusion rests on.

Do not invent wire ids, beneficiary accounts, amounts, or cutoff times. Every id in the
Finding must appear in an observation.
