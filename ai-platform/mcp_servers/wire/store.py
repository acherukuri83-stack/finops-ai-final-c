"""In-process fixture store for the `wire` server (Phase B — Wires, optional module).

Outgoing wires, holds, standing instructions, the reviewer queue, Fedwire cutoffs, one
screening hit, and available balances (cash-lite, for Sc. 16). Facts only — nothing here
says a wire *should* be routed or rescheduled; the Wire specialist derives that, and the
maker/checker + cutoff + screening rules are code (`agent_core/wire.py`), not prompt.

`NOW` / `TODAY` are deterministic and back the cutoff computation. `NOW` is 15:38, so the
USD 16:00 cutoff is 22 minutes away (Sc. 13) and the EUR 15:00 cutoff has passed (Sc. 14).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

NOW = datetime(2026, 9, 6, 15, 38)
TODAY = date(2026, 9, 6)

_CUTOFFS: dict[str, dict[str, Any]] = {
    "USD": {"currency": "USD", "cutoff": "16:00", "tz": "America/New_York", "network": "Fedwire"},
    "EUR": {"currency": "EUR", "cutoff": "15:00", "tz": "Europe/London", "network": "TARGET2"},
}

_SCREENING: dict[str, dict[str, Any]] = {
    # everything is CLEAR unless listed here
    "HF-205": {
        "client_id": "HF-205",
        "status": "HIT",
        "matched_list": "OFAC SDN",
        "checked_at": "2026-09-06T14:55",
    },
}

_STANDING: dict[str, list[dict[str, Any]]] = {
    "HF-201": [
        {
            "beneficiary": "ACME Corp",
            "beneficiary_account": "BEN-100",
            "added_at": "2025-04-02",
            "added_by": "ops.klee",
        },
    ],
    "HF-203": [
        {
            "beneficiary": "Beta Logistics LLC",
            "beneficiary_account": "BEN-200",
            "added_at": "2025-08-19",
            "added_by": "ops.mchen",
        },
    ],
    "HF-205": [
        {
            "beneficiary": "Cedar Holdings",
            "beneficiary_account": "BEN-305",
            "added_at": "2025-01-10",
            "added_by": "ops.jsmith",
        },
    ],
    "HF-206": [
        {
            "beneficiary": "Delta Partners",
            "beneficiary_account": "BEN-410",
            "added_at": "2026-02-01",
            "added_by": "ops.rpatel",
        },
    ],
}

_BALANCES: dict[str, dict[str, Any]] = {
    "ACCT-201@USD": {"account_id": "ACCT-201", "currency": "USD", "available": 40_000_000},
    "ACCT-203@EUR": {"account_id": "ACCT-203", "currency": "EUR", "available": 12_000_000},
    "ACCT-205@USD": {"account_id": "ACCT-205", "currency": "USD", "available": 8_000_000},
    "ACCT-206@USD": {"account_id": "ACCT-206", "currency": "USD", "available": 1_200_000},
}

_WIRES: dict[str, dict[str, Any]] = {
    # Sc. 7 — beneficiary mismatch (account not on the client's standing instructions)
    "W300915": {
        "wire_id": "W300915",
        "client_id": "HF-201",
        "account_id": "ACCT-201",
        "direction": "OUT",
        "currency": "USD",
        "amount": 2_500_000,
        "beneficiary": "ACME Corp",
        "beneficiary_account": "BEN-999",  # not BEN-100
        "value_date": "2026-09-06",
        "status": "HELD",
        "hold_reason": "BENEFICIARY_MISMATCH",
    },
    # Sc. 13 — new beneficiary, USD cutoff 22 min away
    "W300917": {
        "wire_id": "W300917",
        "client_id": "HF-201",
        "account_id": "ACCT-201",
        "direction": "OUT",
        "currency": "USD",
        "amount": 3_100_000,
        "beneficiary": "Orion Freight Co",
        "beneficiary_account": "BEN-777",  # new
        "value_date": "2026-09-06",
        "status": "HELD",
        "hold_reason": "NEW_BENEFICIARY",
    },
    # Sc. 14 — cutoff missed (EUR 15:00, now 15:38); beneficiary is known
    "W300918": {
        "wire_id": "W300918",
        "client_id": "HF-203",
        "account_id": "ACCT-203",
        "direction": "OUT",
        "currency": "EUR",
        "amount": 900_000,
        "beneficiary": "Beta Logistics LLC",
        "beneficiary_account": "BEN-200",
        "value_date": "2026-09-06",
        "status": "HELD",
        "hold_reason": "AWAITING_RELEASE",
    },
    # Sc. 15 — screening hit on the client
    "W300920": {
        "wire_id": "W300920",
        "client_id": "HF-205",
        "account_id": "ACCT-205",
        "direction": "OUT",
        "currency": "USD",
        "amount": 1_750_000,
        "beneficiary": "Cedar Holdings",
        "beneficiary_account": "BEN-305",
        "value_date": "2026-09-06",
        "status": "HELD",
        "hold_reason": "SCREENING",
    },
    # Sc. 16 — insufficient available balance
    "W300921": {
        "wire_id": "W300921",
        "client_id": "HF-206",
        "account_id": "ACCT-206",
        "direction": "OUT",
        "currency": "USD",
        "amount": 5_000_000,
        "beneficiary": "Delta Partners",
        "beneficiary_account": "BEN-410",
        "value_date": "2026-09-06",
        "status": "HELD",
        "hold_reason": "FUNDING",
    },
}

_AUDIT: dict[str, list[dict[str, Any]]] = {
    "W300917": [
        {
            "at": "2026-09-06T15:20",
            "actor": "wire-gateway",
            "event": "received OUT 3,100,000 USD to BEN-777",
        },
        {
            "at": "2026-09-06T15:21",
            "actor": "wire-gateway",
            "event": "held: beneficiary not on standing instructions",
        },
    ],
    "W300918": [
        {
            "at": "2026-09-05T17:00",
            "actor": "wire-gateway",
            "event": "received OUT 900,000 EUR to BEN-200",
        },
        {
            "at": "2026-09-06T15:01",
            "actor": "cutoff-monitor",
            "event": "TARGET2 cutoff 15:00 passed, value date 2026-09-06",
        },
    ],
    "W300920": [
        {
            "at": "2026-09-06T14:55",
            "actor": "screening-gateway",
            "event": "screening returned HIT (OFAC SDN)",
        },
        {"at": "2026-09-06T14:55", "actor": "wire-gateway", "event": "held: screening"},
    ],
}

_QUEUE: list[dict[str, Any]] = []

_ACTIONS: list[dict[str, Any]] = []
_SEQ = 0


def reset() -> None:
    global _SEQ
    _ACTIONS.clear()
    _QUEUE.clear()
    _SEQ = 0


def get_wire(wire_id: str) -> dict[str, Any] | None:
    row = _WIRES.get(wire_id)
    return dict(row) if row else None


def get_wire_audit_trail(wire_id: str) -> list[dict[str, Any]]:
    return [dict(r) for r in _AUDIT.get(wire_id, [])]


def get_standing_instructions(client_id: str) -> list[dict[str, Any]]:
    return [dict(r) for r in _STANDING.get(client_id, [])]


def get_approval_queue() -> list[dict[str, Any]]:
    return [dict(r) for r in _QUEUE]


def get_cutoff(currency: str) -> dict[str, Any] | None:
    row = _CUTOFFS.get(currency)
    return dict(row) if row else None


def get_wire_screening(client_id: str) -> dict[str, Any]:
    row = _SCREENING.get(client_id)
    if row:
        return dict(row)
    return {
        "client_id": client_id,
        "status": "CLEAR",
        "matched_list": None,
        "checked_at": "2026-09-06T06:00",
    }


def get_available_balance(account_id: str, currency: str) -> dict[str, Any] | None:
    row = _BALANCES.get(f"{account_id}@{currency}")
    return dict(row) if row else None


def record_action(
    kind: str, wire_id: str, detail: dict[str, Any], approval_id: str
) -> dict[str, Any]:
    global _SEQ
    _SEQ += 1
    # kind: route_to_reviewer | add_standing_instruction | reschedule_value_date
    #       | compliance_referral
    row = {
        "action_id": f"WR-{_SEQ:04d}",
        "kind": kind,
        "wire_id": wire_id,
        "detail": detail,
        "status": "OPEN",
        "approval_id": approval_id,
    }
    _ACTIONS.append(row)
    if kind == "route_to_reviewer":
        _QUEUE.append(
            {
                "wire_id": wire_id,
                "routed_at": NOW.isoformat(timespec="minutes"),
                "reviewer": "WIRE_REVIEWER",
                "packet": detail.get("packet", ""),
            }
        )
    return dict(row)


def actions() -> list[dict[str, Any]]:
    return [dict(a) for a in _ACTIONS]
