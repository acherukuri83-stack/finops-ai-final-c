"""Data access for the `cash` server (Phase F).

Seeded Postgres (`simulator` planter) with an in-memory mode for the unit suite — the
split is in `mcp_servers._finance_store`. Facts only; the Cash Agent derives whether a
projected shortfall can still be funded before the currency cutoff or must be escalated
(hard rule §9). `NOW` backs the funding-cutoff rule in `agent_core/cash.py`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Table
from sqlalchemy.dialects.postgresql import JSONB

from mcp_servers._finance_store import FinanceStore, metadata

# platform "now" for the funding-cutoff rule (deterministic; matches the fixture times).
NOW = datetime(2026, 9, 6, 13, 30)

cash_breaks = Table(
    "cash_breaks",
    metadata,
    Column("break_id", String, primary_key=True),
    Column("account_id", String),
    Column("currency", String),
    Column("projected_close", BigInteger),
    Column("min_buffer", BigInteger),
    Column("funding_cutoff", DateTime),
    Column("driver", String),
)

funding_ladders = Table(
    "funding_ladders",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("account_id", String),
    Column("currency", String),
    Column("time", DateTime),
    Column("flow", BigInteger),
    Column("kind", String),
)

credit_facilities = Table(
    "credit_facilities",
    metadata,
    Column("account_id", String, primary_key=True),
    Column("currency", String, primary_key=True),
    Column("limit", BigInteger),
    Column("drawn", BigInteger),
    Column("headroom", BigInteger),
)

cash_actions = Table(
    "cash_actions",
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
        "cash_breaks": [
            {
                "break_id": "CB-8001",
                "account_id": "ACC-88213",
                "currency": "USD",
                "projected_close": -6_500_000,  # a shortfall
                "min_buffer": 1_000_000,
                "funding_cutoff": "2026-09-06T16:00",  # still open at NOW
                "driver": "unexpected settlement outflow",
            },
            {
                "break_id": "CB-8002",
                "account_id": "ACC-88213",
                "currency": "EUR",
                "projected_close": -2_100_000,
                "min_buffer": 500_000,
                "funding_cutoff": "2026-09-06T12:00",  # already passed at NOW
                "driver": "coupon payment",
            },
        ],
        "funding_ladders": [
            {
                "account_id": "ACC-88213",
                "currency": "USD",
                "time": "2026-09-06T10:00",
                "flow": 3_000_000,
                "kind": "receipt",
            },
            {
                "account_id": "ACC-88213",
                "currency": "USD",
                "time": "2026-09-06T14:30",
                "flow": -9_500_000,
                "kind": "settlement",
            },
            {
                "account_id": "ACC-88213",
                "currency": "USD",
                "time": "2026-09-06T15:00",
                "flow": 0,
                "kind": "expected",
            },
            {
                "account_id": "ACC-88213",
                "currency": "EUR",
                "time": "2026-09-06T09:00",
                "flow": 400_000,
                "kind": "receipt",
            },
            {
                "account_id": "ACC-88213",
                "currency": "EUR",
                "time": "2026-09-06T11:30",
                "flow": -2_500_000,
                "kind": "coupon",
            },
        ],
        "credit_facilities": [
            {
                "account_id": "ACC-88213",
                "currency": "USD",
                "limit": 20_000_000,
                "drawn": 4_000_000,
                "headroom": 16_000_000,
            },
            {
                "account_id": "ACC-88213",
                "currency": "EUR",
                "limit": 5_000_000,
                "drawn": 0,
                "headroom": 5_000_000,
            },
        ],
    }


_S = FinanceStore(
    name="cash",
    read_tables=[cash_breaks, funding_ladders, credit_facilities],
    action_table=cash_actions,
    action_prefix="CS",
    subject_key="break_id",
    seed=_seed,
)


def reset() -> None:
    _S.reset()


def ensure_schema() -> None:
    _S.ensure_schema()


def get_cash_break(break_id: str) -> dict[str, Any] | None:
    return _S.get("cash_breaks", break_id=break_id)


def list_cash_breaks(account_id: str | None) -> list[dict[str, Any]]:
    return _S.find("cash_breaks", account_id=account_id)


def get_funding_ladder(account_id: str, currency: str) -> list[dict[str, Any]]:
    rows = _S.find("funding_ladders", account_id=account_id, currency=currency)
    for r in rows:
        r.pop("id", None)
        r.pop("account_id", None)
        r.pop("currency", None)
    return rows


def get_facility(account_id: str, currency: str) -> dict[str, Any] | None:
    return _S.get("credit_facilities", account_id=account_id, currency=currency)


def record_action(
    kind: str, break_id: str, detail: dict[str, Any], approval_id: str
) -> dict[str, Any]:
    return _S.record_action(kind, break_id, detail, approval_id)


def actions() -> list[dict[str, Any]]:
    return _S.actions()
