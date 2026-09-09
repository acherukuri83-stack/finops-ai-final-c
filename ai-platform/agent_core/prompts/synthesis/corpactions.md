Write the `Finding` for this corporate-actions investigation from the observations.

- `subject`: `{type: "ca_event", id: "<event_id>@<account_id>"}`.
- `root_cause`: a short code in UPPER_SNAKE — `MANUFACTURED_PAYMENT_DUE` (part of the
  position was out on loan over the record date, so that slice's income must be claimed
  from the borrower), `ELECTION_DUE` (an elective event with the deadline still open and
  no election submitted), `ELECTION_DEADLINE_MISSED` (elective, deadline passed, nothing
  submitted). Leave it null if the entitlement is clean and fully held.
- `evidence`: one `EvidenceRef` (`kind: "tool"`) per fact — `get_ca_event`,
  `get_entitlement` for the held/lent split, `get_election` for an elective event,
  `stockloan.get_recall` / `list_loans` for the loan that spanned the record date.
- `proposed_actions` — from the `corpactions` allowlist only (`submit_election`,
  `raise_claim`, `escalate_ca`, `escalate`):
  - **Lent slice on a cash dividend** → `raise_claim` with `params`: `event_id`,
    `account_id`, `qty` (the `lent_qty`). Do **not** propose booking it directly — there
    is no such action, and the income comes via the claim.
  - **Elective event, deadline open** → `submit_election` with `params`: `event_id`,
    `account_id`, `option` (name one from the event's `options`; `default` if nothing
    else is indicated).
  - **Elective event, deadline passed** → `escalate_ca` with `params`: `event_id`,
    `reason`. Do **not** propose `submit_election`.
  The caller re-checks claim-vs-book and election-vs-escalate against the record date and
  the deadline — but say which and why.
- `rejected_alternatives`: name the action you did not take and why (e.g. `submit_election`
  rejected because the deadline has passed).
- `confidence_basis`: one sentence — what the conclusion rests on.

Do not invent event ids, options, or quantities. Every id in the Finding must appear in
an observation.
