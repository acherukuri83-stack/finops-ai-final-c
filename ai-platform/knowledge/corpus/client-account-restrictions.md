---
doc: Client Account Restrictions
title: Client Account Restrictions Procedure
---

## §2.1 — Settlement holds

A `SETTLEMENT_HOLD` on an account is a compliance control. While it is active the account
cannot settle, regardless of instructions, position, or affirmation status. Operations
may not lift or work around a compliance hold, and must not propose a settlement action
for a trade that failed on `ACCOUNT_RESTRICTED`.

The correct step is to open a compliance referral for the account, quoting the trade id
and the restriction's reason and set-by fields, and to let compliance decide. No other
action is proposed.

## §5.1 — Restriction types

Accounts may carry several restriction types: `SETTLEMENT_HOLD` (blocks settlement),
`TRADING_SUSPENDED` (blocks new bookings), `WITHDRAWAL_HOLD` (blocks cash out), and
`REVIEW` (informational, does not block). Each restriction records who set it, when, and a
free-text reason. This section is a reference for the field values; it does not change the
handling in §2.1.
