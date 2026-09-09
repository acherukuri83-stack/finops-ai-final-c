Write the `Finding` for this cash & funding investigation from the observations.

- `subject`: `{type: "cash_break", id: <break_id>}`.
- `root_cause`: a short code in UPPER_SNAKE — `INTRADAY_SHORTFALL` (a real projected
  shortfall the facility / a sweep can still cover before the cutoff),
  `FUNDING_CUTOFF_MISSED` (the shortfall stands and the currency's funding cutoff has
  passed — overdraft / next-day), `NO_BREAK` (the shortfall is inside `min_buffer` or a
  ladder inflow covers it). Leave it null if the evidence does not support one.
- `evidence`: one `EvidenceRef` (`kind: "tool"`) per fact — `get_cash_break`,
  `get_funding_ladder` for the covering inflow (or its absence), `get_facility` for the
  headroom, `get_price` for a sized swap.
- `proposed_actions` — from the `cash` allowlist only (`arrange_funding`, `move_cash`,
  `escalate_cash`, `escalate`):
  - **Shortfall, cutoff still open, facility headroom available** → `arrange_funding` with
    `params`: `break_id`, `source` (`facility` or `fx_swap`), `amount` (the shortfall plus
    the `min_buffer`).
  - **Shortfall, another of the client's accounts holds a surplus in the currency** →
    `move_cash` with `params`: `break_id`, `from_account`, `to_account`, `amount`.
  - **Cutoff passed** → `escalate_cash` with `params`: `break_id`, `reason`. Do **not**
    propose `arrange_funding` — the funding window is closed.
  The caller re-checks fund-vs-escalate against the funding cutoff and corrects a wrong
  choice — but say which and why.
- `rejected_alternatives`: name the action you did not take and why.
- `confidence_basis`: one sentence — what the conclusion rests on.

Do not invent break ids, amounts, or facility limits. Every id in the Finding must appear
in an observation.
