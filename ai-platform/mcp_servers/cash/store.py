"""In-process fixture store for the `cash` server (Phase F).

Cash & funding — balances, funding ladders, projected breaks, credit facilities. Facts
only; the Cash Agent derives whether a projected shortfall can still be funded before the
currency cutoff or must be escalated (hard rule §9).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

# platform "now" for the funding-cutoff rule (deterministic; matches the fixture times).
NOW = datetime(2026, 9, 6, 13, 30)

_BREAKS: dict[str, dict[str, Any]] = {
    "CB-8001": {
        "break_id": "CB-8001",
        "account_id": "ACC-88213",
        "currency": "USD",
        "projected_close": -6_500_000,  # a shortfall
        "min_buffer": 1_000_000,
        "funding_cutoff": "2026-09-06T16:00",  # still open at NOW
        "driver": "unexpected settlement outflow",
    },
    "CB-8002": {
        "break_id": "CB-8002",
        "account_id": "ACC-88213",
        "currency": "EUR",
        "projected_close": -2_100_000,
        "min_buffer": 500_000,
        "funding_cutoff": "2026-09-06T12:00",  # already passed at NOW
        "driver": "coupon payment",
    },
}

_LADDER: dict[str, list[dict[str, Any]]] = {
    "ACC-88213@USD": [
        {"time": "2026-09-06T10:00", "flow": 3_000_000, "kind": "receipt"},
        {"time": "2026-09-06T14:30", "flow": -9_500_000, "kind": "settlement"},
        {"time": "2026-09-06T15:00", "flow": 0, "kind": "expected"},
    ],
    "ACC-88213@EUR": [
        {"time": "2026-09-06T09:00", "flow": 400_000, "kind": "receipt"},
        {"time": "2026-09-06T11:30", "flow": -2_500_000, "kind": "coupon"},
    ],
}

_FACILITY: dict[str, dict[str, Any]] = {
    "ACC-88213@USD": {
        "account_id": "ACC-88213",
        "currency": "USD",
        "limit": 20_000_000,
        "drawn": 4_000_000,
        "headroom": 16_000_000,
    },
    "ACC-88213@EUR": {
        "account_id": "ACC-88213",
        "currency": "EUR",
        "limit": 5_000_000,
        "drawn": 0,
        "headroom": 5_000_000,
    },
}

_ACTIONS: list[dict[str, Any]] = []
_SEQ = 0


def reset() -> None:
    global _SEQ
    _ACTIONS.clear()
    _SEQ = 0


def get_cash_break(break_id: str) -> dict[str, Any] | None:
    row = _BREAKS.get(break_id)
    return dict(row) if row else None


def list_cash_breaks(account_id: str | None) -> list[dict[str, Any]]:
    return [
        dict(b) for b in _BREAKS.values() if account_id is None or b["account_id"] == account_id
    ]


def get_funding_ladder(account_id: str, currency: str) -> list[dict[str, Any]]:
    return [dict(x) for x in _LADDER.get(f"{account_id}@{currency}", [])]


def get_facility(account_id: str, currency: str) -> dict[str, Any] | None:
    row = _FACILITY.get(f"{account_id}@{currency}")
    return dict(row) if row else None


def record_action(
    kind: str, break_id: str, detail: dict[str, Any], approval_id: str
) -> dict[str, Any]:
    global _SEQ
    _SEQ += 1
    row = {
        "action_id": f"CS-{_SEQ:04d}",
        "kind": kind,  # arrange_funding | move_cash | escalate
        "break_id": break_id,
        "detail": detail,
        "status": "OPEN",
        "approval_id": approval_id,
    }
    _ACTIONS.append(row)
    return dict(row)


def actions() -> list[dict[str, Any]]:
    return [dict(a) for a in _ACTIONS]
