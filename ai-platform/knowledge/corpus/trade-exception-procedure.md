---
doc: Trade Exception Procedure
title: Trade Exception Procedure
---

## §6.1 — Duplicate booking

A `DUPLICATE_SUSPECT` failure means the settlement engine matched the trade to another
booking for the same account, security, side, quantity, and price within a short window.
One booking of the pair usually settles; the other fails.

Confirm the pair with `find_trades` for the account, security, and trade date, and read
the booking-service log for both ids. When the later booking is a genuine duplicate,
propose `cancel_trade` on the later id, listing both trade ids in the action's impact,
and note in the rationale that the trader must confirm the cancellation before it is
approved. Do not resubmit the failed trade.

## §6.3 — Amended bookings

A booking that was amended rather than duplicated shows a single id with a changed
economic field and an amendment entry in the log. That is not a duplicate and is not
cancelled; it is re-affirmed and resubmitted.
