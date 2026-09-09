---
doc: Wire Processing Guide
title: Outgoing Wire Processing Guide
---

## §3.1 — Hold reasons

An outgoing wire is held before release for one of: a beneficiary account not on the
client's standing instructions (`NEW_BENEFICIARY`), a beneficiary account that differs
from the standing instruction for a named beneficiary (`BENEFICIARY_MISMATCH`), a sanctions
screening result that is not clear (`SCREENING`), an available balance below the wire
amount (`FUNDING`), or a wire awaiting a reviewer decision (`AWAITING_RELEASE`). The hold
reason is recorded on the wire and in its audit trail. Operations establishes the facts
behind the hold and routes the wire; operations does not release it.

## §5.2 — New beneficiary control

A wire whose `beneficiary_account` is not on the client's standing wire instructions is
routed to a WIRE_REVIEWER before release. The review packet carries the wire detail, the
standing-instruction check, and the same-day cutoff for the currency. Adding the
beneficiary to the client's standing instructions is a separate action from routing the
wire in front of the reviewer; one does not substitute for the other. A beneficiary
account that conflicts with an existing standing instruction for the same beneficiary is
treated the same way — routed for review, not whitelisted.

## §7.4 — Available funds

Before a wire is released the available balance on the funding account in the wire currency
must cover the wire amount. Where it does not, the wire stays held and the funding
shortfall is raised with treasury; no routing or reschedule action is taken on the wire
until funding is confirmed.

## §9.1 — Same-day cutoffs

Each currency has a same-day value cutoff for its settlement network (Fedwire for USD,
TARGET2 for EUR). A wire that has not been released by the cutoff cannot settle same-day;
its value date is moved to the next business day (`reschedule_value_date`). After the
cutoff a wire is not routed for a same-day release. The cutoff time and network are read
from the currency's cutoff record.

## §11.2 — Value date reschedule

`reschedule_value_date` moves a held wire's value date forward when a same-day release is
no longer possible. It is proposed with the new value date and the reason. It does not
release the wire; the wire remains held for the reviewer at the new value date.
