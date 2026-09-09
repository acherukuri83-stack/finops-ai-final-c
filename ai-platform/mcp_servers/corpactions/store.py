"""In-process fixture store for the `corpactions` server (Phase F).

Corporate actions — events, entitlements, elections, and claims on positions that were
out on loan over the record date. Facts only; the CorpActions Agent derives whether the
entitlement is clean, needs a manufactured-payment claim from the borrower, or is past an
election deadline (hard rule §9).
"""

from __future__ import annotations

from datetime import date
from typing import Any

TODAY = date(2026, 9, 6)

_EVENTS: dict[str, dict[str, Any]] = {
    "CA-7001": {
        "event_id": "CA-7001",
        "security_id": "AAPL",
        "type": "CASH_DIVIDEND",
        "record_date": "2026-09-01",
        "pay_date": "2026-09-10",
        "gross_rate": 0.25,  # per share
        "elective": False,
        "election_deadline": None,
    },
    "CA-7002": {
        "event_id": "CA-7002",
        "security_id": "NVDA",
        "type": "RIGHTS_ISSUE",
        "record_date": "2026-09-02",
        "pay_date": "2026-09-20",
        "gross_rate": 0.0,
        "elective": True,
        "election_deadline": "2026-09-04",  # already past on TODAY
    },
}

# entitlement per (account, event): position on the record date, split held vs lent
_ENTITLEMENTS: dict[str, dict[str, Any]] = {
    "ACC-88213@CA-7001": {
        "account_id": "ACC-88213",
        "event_id": "CA-7001",
        "record_date_qty": 40000,
        "held_qty": 10000,  # in the box on record date
        "lent_qty": 30000,  # out on loan over the record date -> manufactured payment
        "gross_entitlement": 10000.0,  # 40000 * 0.25
    },
    "ACC-88213@CA-7002": {
        "account_id": "ACC-88213",
        "event_id": "CA-7002",
        "record_date_qty": 12000,
        "held_qty": 12000,
        "lent_qty": 0,
        "gross_entitlement": 0.0,
    },
}

_ELECTIONS: dict[str, dict[str, Any]] = {
    "CA-7002": {
        "event_id": "CA-7002",
        "options": ["TAKE_UP", "LAPSE", "SELL_RIGHTS"],
        "default": "LAPSE",
        "submitted": None,
    },
}

_ACTIONS: list[dict[str, Any]] = []
_SEQ = 0


def reset() -> None:
    global _SEQ
    _ACTIONS.clear()
    _SEQ = 0


def get_ca_event(event_id: str) -> dict[str, Any] | None:
    row = _EVENTS.get(event_id)
    return dict(row) if row else None


def list_ca_events(security_id: str | None) -> list[dict[str, Any]]:
    return [
        dict(e) for e in _EVENTS.values() if security_id is None or e["security_id"] == security_id
    ]


def get_entitlement(account_id: str, event_id: str) -> dict[str, Any] | None:
    row = _ENTITLEMENTS.get(f"{account_id}@{event_id}")
    return dict(row) if row else None


def get_election(event_id: str) -> dict[str, Any] | None:
    row = _ELECTIONS.get(event_id)
    return dict(row) if row else None


def record_action(
    kind: str, event_id: str, detail: dict[str, Any], approval_id: str
) -> dict[str, Any]:
    global _SEQ
    _SEQ += 1
    row = {
        "action_id": f"CA-A{_SEQ:04d}",
        "kind": kind,  # submit_election | raise_claim | escalate
        "event_id": event_id,
        "detail": detail,
        "status": "OPEN",
        "approval_id": approval_id,
    }
    _ACTIONS.append(row)
    return dict(row)


def actions() -> list[dict[str, Any]]:
    return [dict(a) for a in _ACTIONS]
