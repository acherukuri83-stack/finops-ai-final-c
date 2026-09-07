---
doc: Delivery & Position Procedure
title: Delivery and Position Procedure
---

## §4.3 — Delivery shortfall and partial settlement

An `INSUFFICIENT_POSITION` failure means the account's available quantity for the security
is below the trade quantity at settlement time. Read the position: `available` is the
deliverable quantity, and `pending_deliver` is the quantity already committed to other
settlements, which is why the total held can exceed what is available.

Where a partial delivery is acceptable, resubmit the trade for the available quantity now
and let the balance settle when the pending deliveries clear. Check borrow availability
for the shortfall quantity only after the shortfall is confirmed; a borrow is arranged by
the securities lending desk, not by operations, and is proposed as a follow-up, not a
same-day fix.

## §4.5 — Pending receive

A pending receive that has not arrived can also leave an account short. Confirm the
expected receive against its own trade before assuming a lending shortfall.
