---
doc: Incident Management
title: Operations Incident Management
---

## §1 — Raising an incident

Open an incident when a settlement failure cannot be explained from the trade, account,
counterparty, position, reference, and log data available to operations, or when the same
failure mode affects more than one trade. The incident records what was checked, the trade
ids involved, and the point at which the investigation stopped.

## §2 — Escalating to settlement engineering

A trade that shows a failure with no failure code, no attempt detail, and no corroborating
log line — nothing for operations to act on — is escalated to settlement engineering with
the full list of checks performed. Operations does not resubmit, cancel, or change
instructions in this case; the escalation carries the checked list so engineering can
begin from where operations finished.

## §3 — Closing the loop

When an incident is resolved, its cause and resolution are written back so that the next
similar failure retrieves it. Historical incidents are referenced as `INC-####`.
