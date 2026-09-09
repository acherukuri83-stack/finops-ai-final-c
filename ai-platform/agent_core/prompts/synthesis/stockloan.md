Write the `Finding` for this securities-lending investigation from the observations.

- `subject`: `{type: "loan", id: <loan_id>}`.
- `root_cause`: a short code in UPPER_SNAKE — `RECALL_REQUIRED` (the account is short the
  security to settle a delivery and the shares are out on this loan),
  `RECALL_WINDOW_MISSED` (the same, but the notice window has passed — a buy-in is now the
  only cover), `OFF_MARKET_RATE` (the loan's `rate_bps` is far from the security's
  `gc_rate_bps` with no borrow-specific reason). Leave it null if the evidence does not
  support one.
- `evidence`: one `EvidenceRef` (`kind: "tool"`) per fact — `get_loan` for the loan,
  `get_position` for the shortfall, `get_recall` for an existing recall,
  `get_lending_availability` for the GC rate, `get_rerate_history` for a rate move.
- `proposed_actions` — from the `stockloan` allowlist only (`initiate_recall`,
  `rerate_loan`, `book_buy_in`, `escalate`):
  - **Recall still possible** → `initiate_recall` with `params`: `loan_id`, `qty` (what
    the account is short), a one-line `reason`.
  - **Recall window missed** → `book_buy_in` with `params`: `loan_id`, `qty`, `reason`.
    Do **not** propose `initiate_recall` — it is too late to help this settlement.
  - **Off-market rate** → `rerate_loan` with `params`: `loan_id`, `new_rate_bps` (toward
    `gc_rate_bps` unless a recorded reason justifies the spread), `reason`.
  The caller re-checks recall-vs-buy-in against the notice window and will correct a
  wrong choice — but say which and why.
- `rejected_alternatives`: if you propose `book_buy_in`, name `initiate_recall` as
  rejected because the window has passed. If you propose `initiate_recall`, name
  `book_buy_in` as the fallback if the borrower does not return in time.
- `confidence_basis`: one sentence — what the conclusion rests on.

Do not invent loan ids, counterparties, or rates. Every id in the Finding must appear in
an observation.
