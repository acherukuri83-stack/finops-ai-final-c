"""In-process fixture store for the `stockloan` server (Phase F core slice).

Securities-lending is *simulated* the same way the enterprise and platform tiers are —
in-process, small, facts only. Loans, recalls, rerates, and lending availability. Nothing
here says whether a recall is late or a rate is wrong; the StockLoan Agent derives that
(hard rule §9). A fuller Phase F would move this to a seeded table + a `simulator`
planter, like the enterprise tier (`docs/backlog.md`).
"""

from __future__ import annotations

from datetime import date
from typing import Any

# Standard recall notice period: a recall must be *initiated* this many business days
# before the borrower's return is needed, or a buy-in is forced. Code rule, not prompt.
RECALL_NOTICE_DAYS = 3

_LOANS: dict[str, dict[str, Any]] = {
    "LN-5001": {
        "loan_id": "LN-5001",
        "account_id": "ACC-88213",
        "security_id": "NVDA",
        "counterparty": "CP-020",
        "qty": 30000,
        "rate_bps": 45,
        "trade_date": "2026-07-01",
        "open": True,
        # the account owes a 30k NVDA delivery on this date and is short without a recall
        "return_needed_by": "2026-09-10",
    },
    "LN-5002": {
        "loan_id": "LN-5002",
        "account_id": "ACC-88213",
        "security_id": "AMZN",
        "counterparty": "CP-020",
        "qty": 12000,
        "rate_bps": 30,
        "trade_date": "2026-06-15",
        "open": True,
        "return_needed_by": "2026-09-04",  # already inside/!past the notice window -> buy-in
    },
    "LN-5003": {
        "loan_id": "LN-5003",
        "account_id": "ACC-77120",
        "security_id": "AAPL",
        "counterparty": "CP-031",
        "qty": 5000,
        "rate_bps": 500,  # well above general-collateral — a rerate candidate
        "trade_date": "2026-08-20",
        "open": True,
        "return_needed_by": None,
    },
}

_RECALLS: dict[str, dict[str, Any]] = {
    # LN-5001 has no recall issued yet; LN-5002's was issued late.
    "LN-5002": {
        "loan_id": "LN-5002",
        "status": "ISSUED",
        "issued_at": "2026-09-03T14:00:00",
        "due_date": "2026-09-04",
        "satisfied": False,
    },
}

_RERATE_HISTORY: dict[str, list[dict[str, Any]]] = {
    "LN-5003": [
        {"at": "2026-08-20", "from_bps": 30, "to_bps": 500, "by": "desk.auto"},
    ],
}

_AVAILABILITY: dict[str, dict[str, Any]] = {
    "NVDA": {
        "security_id": "NVDA",
        "lendable_qty": 500000,
        "on_loan_qty": 180000,
        "gc_rate_bps": 25,
    },
    "AMZN": {
        "security_id": "AMZN",
        "lendable_qty": 200000,
        "on_loan_qty": 40000,
        "gc_rate_bps": 20,
    },
    "AAPL": {
        "security_id": "AAPL",
        "lendable_qty": 800000,
        "on_loan_qty": 120000,
        "gc_rate_bps": 15,
    },
}

# platform "today" for the recall-window rule (deterministic; matches the scenario dates)
TODAY = date(2026, 9, 6)

_ACTIONS: list[dict[str, Any]] = []
_SEQ = 0


def reset() -> None:
    global _SEQ
    _ACTIONS.clear()
    _SEQ = 0


def get_loan(loan_id: str) -> dict[str, Any] | None:
    row = _LOANS.get(loan_id)
    return dict(row) if row else None


def list_loans(security_id: str | None, account_id: str | None) -> list[dict[str, Any]]:
    return [
        dict(loan)
        for loan in _LOANS.values()
        if (security_id is None or loan["security_id"] == security_id)
        and (account_id is None or loan["account_id"] == account_id)
    ]


def get_recall(loan_id: str) -> dict[str, Any] | None:
    row = _RECALLS.get(loan_id)
    return dict(row) if row else None


def get_rerate_history(loan_id: str) -> list[dict[str, Any]]:
    return [dict(r) for r in _RERATE_HISTORY.get(loan_id, [])]


def get_lending_availability(security_id: str) -> dict[str, Any] | None:
    row = _AVAILABILITY.get(security_id)
    return dict(row) if row else None


def record_action(
    kind: str, loan_id: str, detail: dict[str, Any], approval_id: str
) -> dict[str, Any]:
    global _SEQ
    _SEQ += 1
    row = {
        "action_id": f"SL-{_SEQ:04d}",
        "kind": kind,  # recall | rerate | buy_in
        "loan_id": loan_id,
        "detail": detail,
        "status": "OPEN",
        "approval_id": approval_id,
    }
    _ACTIONS.append(row)
    return dict(row)


def actions() -> list[dict[str, Any]]:
    return [dict(a) for a in _ACTIONS]
