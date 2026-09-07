---
doc: Reference Data Procedure
title: Security Reference Data Procedure
---

## §3.2 — Identifier inconsistency on a failed trade

A `SECURITY_ID_MISMATCH` failure means the identifiers on the trade record do not agree
with the security master: typically the CUSIP carried on the trade does not resolve to
the ISIN the master holds for that security. The reference-data service logs the
offending identifier for the trade.

Operations cannot correct a security master record. Confirm the inconsistency with
`get_security` and the service log, then escalate to the reference data team with the
trade id and both identifier values. Hold the trade — do not resubmit — until the master
is corrected, because a resubmission validates against the same record and fails again.

## §3.4 — Settlement cycle and calendar

Each security carries a settlement cycle in the master. A settlement date that is not a
business day for the relevant market, or that does not match the security's cycle, is a
reference-data question and is escalated the same way; it is not corrected by operations.
