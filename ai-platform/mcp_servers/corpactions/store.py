"""Data access for the `corpactions` server (Phase F).

Seeded Postgres (`simulator` planter) with an in-memory mode for the unit suite — the
split is in `mcp_servers._finance_store`. Facts only; the CorpActions Agent derives
whether the entitlement is clean, needs a manufactured-payment claim from the borrower,
or is past an election deadline (hard rule §9).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import BigInteger, Boolean, Column, Date, Integer, Numeric, String, Table
from sqlalchemy.dialects.postgresql import JSONB

from mcp_servers._finance_store import FinanceStore, metadata

TODAY = date(2026, 9, 6)

ca_events = Table(
    "ca_events",
    metadata,
    Column("event_id", String, primary_key=True),
    Column("security_id", String),
    Column("type", String),
    Column("record_date", Date),
    Column("pay_date", Date),
    Column("gross_rate", Numeric),
    Column("elective", Boolean),
    Column("election_deadline", Date),
)

ca_entitlements = Table(
    "ca_entitlements",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("account_id", String),
    Column("event_id", String),
    Column("record_date_qty", BigInteger),
    Column("held_qty", BigInteger),
    Column("lent_qty", BigInteger),
    Column("gross_entitlement", Numeric),
)

ca_elections = Table(
    "ca_elections",
    metadata,
    Column("event_id", String, primary_key=True),
    Column("options", JSONB),
    Column("default", String),
    Column("submitted", String),
)

ca_actions = Table(
    "ca_actions",
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
        "ca_events": [
            {
                "event_id": "CA-7001",
                "security_id": "AAPL",
                "type": "CASH_DIVIDEND",
                "record_date": "2026-09-01",
                "pay_date": "2026-09-10",
                "gross_rate": 0.25,  # per share
                "elective": False,
                "election_deadline": None,
            },
            {
                "event_id": "CA-7002",
                "security_id": "NVDA",
                "type": "RIGHTS_ISSUE",
                "record_date": "2026-09-02",
                "pay_date": "2026-09-20",
                "gross_rate": 0.0,
                "elective": True,
                "election_deadline": "2026-09-04",  # already past on TODAY
            },
        ],
        "ca_entitlements": [
            {
                "account_id": "ACC-88213",
                "event_id": "CA-7001",
                "record_date_qty": 40000,
                "held_qty": 10000,  # in the box on record date
                "lent_qty": 30000,  # out on loan over the record date -> manufactured payment
                "gross_entitlement": 10000.0,  # 40000 * 0.25
            },
            {
                "account_id": "ACC-88213",
                "event_id": "CA-7002",
                "record_date_qty": 12000,
                "held_qty": 12000,
                "lent_qty": 0,
                "gross_entitlement": 0.0,
            },
        ],
        "ca_elections": [
            {
                "event_id": "CA-7002",
                "options": ["TAKE_UP", "LAPSE", "SELL_RIGHTS"],
                "default": "LAPSE",
                "submitted": None,
            },
        ],
    }


_S = FinanceStore(
    name="corpactions",
    read_tables=[ca_events, ca_entitlements, ca_elections],
    action_table=ca_actions,
    action_prefix="CA-A",
    subject_key="event_id",
    seed=_seed,
)


def reset() -> None:
    _S.reset()


def ensure_schema() -> None:
    _S.ensure_schema()


def get_ca_event(event_id: str) -> dict[str, Any] | None:
    return _S.get("ca_events", event_id=event_id)


def list_ca_events(security_id: str | None) -> list[dict[str, Any]]:
    return _S.find("ca_events", security_id=security_id)


def get_entitlement(account_id: str, event_id: str) -> dict[str, Any] | None:
    row = _S.get("ca_entitlements", account_id=account_id, event_id=event_id)
    if row:
        row.pop("id", None)
    return row


def get_election(event_id: str) -> dict[str, Any] | None:
    return _S.get("ca_elections", event_id=event_id)


def record_action(
    kind: str, event_id: str, detail: dict[str, Any], approval_id: str
) -> dict[str, Any]:
    return _S.record_action(kind, event_id, detail, approval_id)


def actions() -> list[dict[str, Any]]:
    return _S.actions()
