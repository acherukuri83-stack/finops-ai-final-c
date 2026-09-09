Write the `Finding` for this margin investigation from the observations.

- `subject`: `{type: "margin_call", id: <call_id>}`.
- `root_cause`: a short code in UPPER_SNAKE — `PRICE_MOVE_SHORTFALL` (a market move drove
  the requirement above posted collateral), `COLLATERAL_INELIGIBLE` (posted collateral was
  downgraded / made ineligible, opening a shortfall), `CALL_WINDOW_MISSED` (the call is
  past `due_by` and unmet — a close-out, not a top-up). Leave it null if the evidence does
  not support one.
- `evidence`: one `EvidenceRef` (`kind: "tool"`) per fact — `get_margin_call`,
  `get_margin_status` for the shortfall, `get_collateral` / `get_eligibility` for an
  ineligible line, `get_price` for a confirmed move.
- `proposed_actions` — from the `margin` allowlist only (`post_collateral`,
  `substitute_collateral`, `escalate_margin`, `escalate`):
  - **Price-move shortfall, window open** → `post_collateral` with `params`: `call_id`,
    `security_id` (an eligible line), `amount` (the shortfall).
  - **Ineligible collateral** → `substitute_collateral` with `params`: `call_id`,
    `out_security` (the ineligible line), `in_security` (an eligible replacement).
  - **Window missed** → `escalate_margin` with `params`: `call_id`, `reason`. Do **not**
    propose `post_collateral` — the call is out for close-out.
  The caller re-checks meet-vs-close-out against the call window and corrects a wrong
  choice — but say which and why.
- `rejected_alternatives`: if you propose `escalate_margin`, name `post_collateral` as
  rejected because the window has passed. If you propose `post_collateral`, name
  `escalate_margin` as the fallback if it is not met by `due_by`.
- `confidence_basis`: one sentence — what the conclusion rests on.

Do not invent call ids, securities, or amounts. Every id in the Finding must appear in an
observation.
