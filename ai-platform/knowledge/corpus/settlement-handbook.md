---
doc: Settlement Handbook
title: Settlement Failure Handbook
---

## §8.1 — SSI validation

Before every settlement run the platform validates that each account on the instruction
has exactly one current standing settlement instruction (SSI), that its effective range
covers the settlement date, and that the delivering and receiving agents are both
reachable. An account with no current SSI, or with overlapping effective ranges, is held
before submission and routed to the reference data team. This check is structural only;
it does not compare our instruction against the counterparty's.

## §8.4 — Counterparty SSI mismatch

A `COUNTERPARTY_SSI_MISMATCH` failure means the settlement engine received an instruction
from us and an affirmation from the counterparty that name different delivery agents.

¶1 Compare the instruction on the failed attempt with the counterparty affirmation. The
settlement engine log for the trade records both values.

¶2 Retrieve the SSI history for the account and confirm which instruction is current: the
version whose effective range covers the settlement date, with no later version.

¶3 Do NOT modify a valid client SSI merely to match a counterparty affirmation. Changing
a current instruction to resolve one trade misdirects every other delivery for that
account. `update_ssi` is appropriate only when independent evidence — a custodian notice,
a client instruction — shows our own record is out of date.

¶4 Where the client SSI is current, the counterparty is affirming against a superseded
instruction. Request re-affirmation against the current SSI and resubmit once the
counterparty confirms. Record the contact in the case notes.

## §8.6 — Expired counterparty instructions

A mismatch can also arise when our SSI and the counterparty's affirmation agree, but the
instruction the counterparty holds on file for us has passed its `valid_to` date. The
affirmation gateway logs `instruction valid_to <date> < settle_date` for the trade.

The client SSI is not at fault here and must not be changed. Request a refreshed
instruction from the counterparty for the current SSI, then resubmit. Escalate to the
counterparty onboarding desk if a refreshed instruction is not received the same day.
