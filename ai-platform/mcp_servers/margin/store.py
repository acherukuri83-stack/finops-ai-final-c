"""Data access for the `margin` server (Phase F).

Seeded Postgres (`simulator` planter) with an in-memory mode for the unit suite — the
split is in `mcp_servers._finance_store`. Facts only; the Margin Agent derives whether a
call is met, mis-priced, or past its window (hard rule §9). `TODAY` backs the
meet-vs-close-out rule in `agent_core/margin.py`.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import BigInteger, Boolean, Column, Date, Integer, String, Table
from sqlalchemy.dialects.postgresql import JSONB

from mcp_servers._finance_store import FinanceStore, metadata

# A margin call must be met by end of `due_by`; after that it escalates to a close-out.
TODAY = date(2026, 9, 6)

margin_calls = Table(
    "margin_calls",
    metadata,
    Column("call_id", String, primary_key=True),
    Column("account_id", String),
    Column("issued", Date),
    Column("due_by", Date),
    Column("amount", BigInteger),
    Column("reason", String),
    Column("status", String),
)

margin_status = Table(
    "margin_status",
    metadata,
    Column("account_id", String, primary_key=True),
    Column("requirement", BigInteger),
    Column("posted", BigInteger),
    Column("shortfall", BigInteger),
    Column("as_of", Date),
)

collateral = Table(
    "collateral",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("account_id", String),
    Column("security_id", String),
    Column("market_value", BigInteger),
    Column("haircut_pct", Integer),
    Column("eligible", Boolean),
)

collateral_eligibility = Table(
    "collateral_eligibility",
    metadata,
    Column("security_id", String, primary_key=True),
    Column("eligible", Boolean),
    Column("haircut_pct", Integer),
    Column("rating", String),
)

margin_actions = Table(
    "margin_actions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("kind", String),
    Column("subject_id", String),
    Column("detail", JSONB),
    Column("status", String),
    Column("approval_id", String),
)


def _seed() -> dict[str, list[dict[str, Any]]]:
    return {
        "margin_calls": [
            {
                "call_id": "MC-9001",
                "account_id": "ACC-88213",
                "issued": "2026-09-05",
                "due_by": "2026-09-06",  # still open on TODAY
                "amount": 4_200_000,
                "reason": "PRICE_MOVE",
                "status": "OPEN",
            },
            {
                "call_id": "MC-9002",
                "account_id": "ACC-88213",
                "issued": "2026-09-02",
                "due_by": "2026-09-03",  # past the window on TODAY -> close-out
                "amount": 1_100_000,
                "reason": "PRICE_MOVE",
                "status": "OPEN",
            },
        ],
        "margin_status": [
            {
                "account_id": "ACC-88213",
                "requirement": 18_400_000,
                "posted": 14_200_000,
                "shortfall": 4_200_000,
                "as_of": "2026-09-05",
            },
        ],
        "collateral": [
            {
                "account_id": "ACC-88213",
                "security_id": "AAPL",
                "market_value": 9_000_000,
                "haircut_pct": 5,
                "eligible": True,
            },
            {
                "account_id": "ACC-88213",
                "security_id": "NVDA",
                "market_value": 5_200_000,
                "haircut_pct": 8,
                "eligible": True,
            },
            {
                "account_id": "ACC-88213",
                "security_id": "XLOW",
                "market_value": 2_000_000,
                "haircut_pct": 100,
                "eligible": False,
            },
        ],
        "collateral_eligibility": [
            {"security_id": "AAPL", "eligible": True, "haircut_pct": 5, "rating": "A"},
            {"security_id": "NVDA", "eligible": True, "haircut_pct": 8, "rating": "A"},
            {"security_id": "XLOW", "eligible": False, "haircut_pct": 100, "rating": "CCC"},
        ],
    }


_S = FinanceStore(
    name="margin",
    read_tables=[margin_calls, margin_status, collateral, collateral_eligibility],
    action_table=margin_actions,
    action_prefix="MG",
    subject_key="call_id",
    seed=_seed,
)


def reset() -> None:
    _S.reset()


def ensure_schema() -> None:
    _S.ensure_schema()


def get_margin_call(call_id: str) -> dict[str, Any] | None:
    return _S.get("margin_calls", call_id=call_id)


def list_margin_calls(account_id: str | None) -> list[dict[str, Any]]:
    return _S.find("margin_calls", account_id=account_id)


def get_margin_status(account_id: str) -> dict[str, Any] | None:
    return _S.get("margin_status", account_id=account_id)


def get_collateral(account_id: str) -> list[dict[str, Any]]:
    rows = _S.find("collateral", account_id=account_id)
    for r in rows:
        r.pop("id", None)
    return rows


def get_eligibility(security_id: str) -> dict[str, Any] | None:
    return _S.get("collateral_eligibility", security_id=security_id)


def record_action(
    kind: str, call_id: str, detail: dict[str, Any], approval_id: str
) -> dict[str, Any]:
    return _S.record_action(kind, call_id, detail, approval_id)


def actions() -> list[dict[str, Any]]:
    return _S.actions()
