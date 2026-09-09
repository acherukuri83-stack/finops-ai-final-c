"""In-process fixture store for the `margin` server (Phase F).

Margin & collateral — calls, eligibility, haircuts, shortfall. Facts only; the Margin
Agent derives whether a call is met, mis-priced, or past its window (hard rule §9). A
fuller Phase F moves this to a seeded table + a `simulator` planter (`docs/backlog.md`).
"""

from __future__ import annotations

from datetime import date
from typing import Any

# A margin call must be met by end of `due_by`; after that it escalates to a close-out.
# Code rule, not prompt.
TODAY = date(2026, 9, 6)

_CALLS: dict[str, dict[str, Any]] = {
    "MC-9001": {
        "call_id": "MC-9001",
        "account_id": "ACC-88213",
        "issued": "2026-09-05",
        "due_by": "2026-09-06",  # still open on TODAY
        "amount": 4_200_000,
        "reason": "PRICE_MOVE",
        "status": "OPEN",
    },
    "MC-9002": {
        "call_id": "MC-9002",
        "account_id": "ACC-88213",
        "issued": "2026-09-02",
        "due_by": "2026-09-03",  # past the window on TODAY -> close-out
        "amount": 1_100_000,
        "reason": "PRICE_MOVE",
        "status": "OPEN",
    },
}

_MARGIN_STATUS: dict[str, dict[str, Any]] = {
    "ACC-88213": {
        "account_id": "ACC-88213",
        "requirement": 18_400_000,
        "posted": 14_200_000,
        "shortfall": 4_200_000,
        "as_of": "2026-09-05",
    },
}

_COLLATERAL: dict[str, list[dict[str, Any]]] = {
    "ACC-88213": [
        {"security_id": "AAPL", "market_value": 9_000_000, "haircut_pct": 5, "eligible": True},
        {"security_id": "NVDA", "market_value": 5_200_000, "haircut_pct": 8, "eligible": True},
        {"security_id": "XLOW", "market_value": 2_000_000, "haircut_pct": 100, "eligible": False},
    ],
}

_ELIGIBILITY: dict[str, dict[str, Any]] = {
    "AAPL": {"security_id": "AAPL", "eligible": True, "haircut_pct": 5, "rating": "A"},
    "NVDA": {"security_id": "NVDA", "eligible": True, "haircut_pct": 8, "rating": "A"},
    "XLOW": {"security_id": "XLOW", "eligible": False, "haircut_pct": 100, "rating": "CCC"},
}

_ACTIONS: list[dict[str, Any]] = []
_SEQ = 0


def reset() -> None:
    global _SEQ
    _ACTIONS.clear()
    _SEQ = 0


def get_margin_call(call_id: str) -> dict[str, Any] | None:
    row = _CALLS.get(call_id)
    return dict(row) if row else None


def list_margin_calls(account_id: str | None) -> list[dict[str, Any]]:
    return [dict(c) for c in _CALLS.values() if account_id is None or c["account_id"] == account_id]


def get_margin_status(account_id: str) -> dict[str, Any] | None:
    row = _MARGIN_STATUS.get(account_id)
    return dict(row) if row else None


def get_collateral(account_id: str) -> list[dict[str, Any]]:
    return [dict(x) for x in _COLLATERAL.get(account_id, [])]


def get_eligibility(security_id: str) -> dict[str, Any] | None:
    row = _ELIGIBILITY.get(security_id)
    return dict(row) if row else None


def record_action(
    kind: str, call_id: str, detail: dict[str, Any], approval_id: str
) -> dict[str, Any]:
    global _SEQ
    _SEQ += 1
    row = {
        "action_id": f"MG-{_SEQ:04d}",
        "kind": kind,  # post_collateral | substitute_collateral | escalate
        "call_id": call_id,
        "detail": detail,
        "status": "OPEN",
        "approval_id": approval_id,
    }
    _ACTIONS.append(row)
    return dict(row)


def actions() -> list[dict[str, Any]]:
    return [dict(a) for a in _ACTIONS]
