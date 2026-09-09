---
doc: Sanctions Procedure
title: Sanctions Screening Procedure
---

## §2.1 — Screening hits

A wire is screened against the sanctions lists before release. A result other than `CLEAR`
— a `HIT` — freezes the wire. While a wire is frozen no routing, reschedule, standing-
instruction, or release action is taken on it. The screening result names the list matched
and the time of the check.

## §2.4 — Referral and freeze

A screening hit is referred to compliance (`open_compliance_referral`) and no other action
is proposed. The referral carries the wire id and the matched list. The freeze is lifted
only by compliance; operations does not clear a hit or route the wire around it. A wire
that was routed to a reviewer before a hit was returned is recalled to the frozen state.

## §3 — Clear results

A `CLEAR` screening result places no constraint on the wire. The wire is then subject only
to the beneficiary, funding, and cutoff controls in the Wire Processing Guide.
