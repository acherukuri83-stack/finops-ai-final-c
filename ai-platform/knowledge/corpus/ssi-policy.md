---
doc: SSI Policy
title: Standing Settlement Instruction Policy
---

## §3.2 — Change control

A change to an account's standing settlement instruction is a controlled action. A change
request must name the source of the new instruction (a client authorisation, a custodian
notice, or an onboarding record), be entered by a settlements user, and be approved by a
second settlements user before it takes effect. The prior version is closed out with an
effective end date of the day before the new version's effective date, so the history
stays contiguous. Change control governs *who* may change an SSI and *how* it is
recorded; it does not decide *whether* a given trade's failure calls for a change.

## §3.5 — Effective dating

A new SSI version carries an effective start date. Settlement for a trade uses the
version whose effective range covers that trade's settlement date. A version entered with
a future start date does not affect trades settling before it.
