Plan the next tool calls for this settlement-failure investigation.

You are given the request, the tools you may call (server + tool + description), and —
after the first turn — the observations so far. Produce a `Plan`:

- `assumptions`: the things your plan takes to be true and will re-check. Example:
  "the failure is a live SSI mismatch, not one already remediated".
- `steps`: 1–6 tool calls, each with `server`, `tool`, string `args`, and a one-line
  `why`. Do not set `k` on retrieval tools; the default is fine.

Ordering that works:

1. `trade.get_trade` — the trade, its account, counterparty, dates, status.
2. `trade.get_settlement_status` — the `failure_code` and attempt history. Everything
   after this depends on the code.
3. Depending on the code, gather the relevant records:
   - SSI mismatch → `counterparty.get_affirmation` and `client.get_ssi` **first**: if the
     latest affirmation's `cpty_dtc` already equals the current SSI's `dtc_participant`,
     the mismatch has been remediated and the trade just needs resubmitting — you can
     stop there. Otherwise also pull `client.get_ssi_history` and
     `counterparty.get_counterparty_ssi`.
   - reference-data → `reference.get_security`.
   - restricted → `client.get_account`, `compliance.get_restrictions`.
   - position → `position.get_position`, then `position.get_borrow_availability` only if
     short.
   - duplicate → `trade.find_trades` for the same account + security + date, then an
     `ops.search_knowledge` for the duplicate-booking / trade-exception procedure.
4. `ops.search_logs` with the `trade_id` for corroborating log lines.
5. **Only once the failure code is known**: `ops.search_knowledge` for the procedure that
   covers this code, and `ops.find_incidents` for similar past incidents.
6. For a **counterparty SSI mismatch**, whichever instruction looks current, run a second
   `ops.search_knowledge` whose query names the client id and "custodian notice" — a
   custodian move that was never reflected in our SSI is the difference between
   "counterparty is stale" and "our record is stale", and it only shows up on that query.

Re-plan (return a new `Plan`) when an observation contradicts an assumption — e.g. the
mismatch no longer exists (already remediated), or a required tool returned an error.
Stop planning when you have the cause and the evidence for it, or when the budget is
spent. Keep the whole investigation to about a dozen tool calls; do not call every tool
"just in case".
