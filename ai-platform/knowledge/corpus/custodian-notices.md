---
doc: Custodian Notices
title: Handling Custodian Notices
---

## §1 — Acting on a custodian notice

A custodian notice is a dated statement from a custodian about where an account settles —
for example, that an account has moved to a different DTC participant with effect from a
given date. A notice is a valid source for an SSI change under SSI Policy §3.2.

When a settlement failure is a `COUNTERPARTY_SSI_MISMATCH` and a custodian notice shows
our account moved to the participant the counterparty is affirming against, on or before
the settlement date, our own SSI is the record that was not updated. Propose `update_ssi`
to the participant in the notice, then resubmit. Retrieve the notice by account and date.

## §2 — Filing

Custodian notices are held in the knowledge corpus and indexed by account and effective
date. A notice that has been superseded by a later notice for the same account is kept for
history but is not acted on.
