"""Data access for the `stockloan` server (Phase F).

Seeded Postgres (`simulator` planter, `make seed`) with an in-memory mode for the unit
suite — the split lives in `mcp_servers._finance_store`. The row shapes below are exactly
what the fixtures held before seeding, so the specialist and its prompts don't change.

Nothing here says whether a recall is late or a rate is wrong; the StockLoan Agent
derives that (hard rule §9). `RECALL_NOTICE_DAYS` / `TODAY` back the recall-window rule
in `agent_core/stockloan.py`.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Integer,
    String,
    Table,
)
from sqlalchemy.dialects.postgresql import JSONB

from mcp_servers._finance_store import FinanceStore, metadata

# Standard recall notice period: a recall must be *initiated* this many business days
# before the borrower's return is needed, or a buy-in is forced. Code rule, not prompt.
RECALL_NOTICE_DAYS = 3

# platform "today" for the recall-window rule (deterministic; matches the scenario dates)
TODAY = date(2026, 9, 6)

# --- tables (mirrored by simulator/simulator/finance_tables.py) -----------------

stock_loans = Table(
    "stock_loans",
    metadata,
    Column("loan_id", String, primary_key=True),
    Column("account_id", String),
    Column("security_id", String),
    Column("counterparty", String),
    Column("qty", BigInteger),
    Column("rate_bps", Integer),
    Column("trade_date", Date),
    Column("open", Boolean),
    Column("return_needed_by", Date),
)

loan_recalls = Table(
    "loan_recalls",
    metadata,
    Column("loan_id", String, primary_key=True),
    Column("status", String),
    Column("issued_at", DateTime),
    Column("due_date", Date),
    Column("satisfied", Boolean),
)

loan_rerates = Table(
    "loan_rerates",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("loan_id", String),
    Column("at", Date),
    Column("from_bps", Integer),
    Column("to_bps", Integer),
    Column("by", String),
)

lending_availability = Table(
    "lending_availability",
    metadata,
    Column("security_id", String, primary_key=True),
    Column("lendable_qty", BigInteger),
    Column("on_loan_qty", BigInteger),
    Column("gc_rate_bps", Integer),
)

loan_actions = Table(
    "loan_actions",
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
        "stock_loans": [
            {
                "loan_id": "LN-5001",
                "account_id": "ACC-88213",
                "security_id": "NVDA",
                "counterparty": "CP-020",
                "qty": 30000,
                "rate_bps": 45,
                "trade_date": "2026-07-01",
                "open": True,
                # owes a 30k NVDA delivery on this date; short without a recall
                "return_needed_by": "2026-09-10",
            },
            {
                "loan_id": "LN-5002",
                "account_id": "ACC-88213",
                "security_id": "AMZN",
                "counterparty": "CP-020",
                "qty": 12000,
                "rate_bps": 30,
                "trade_date": "2026-06-15",
                "open": True,
                "return_needed_by": "2026-09-04",  # past the notice window -> buy-in
            },
            {
                "loan_id": "LN-5003",
                "account_id": "ACC-77120",
                "security_id": "AAPL",
                "counterparty": "CP-031",
                "qty": 5000,
                "rate_bps": 500,  # well above general-collateral -> a rerate candidate
                "trade_date": "2026-08-20",
                "open": True,
                "return_needed_by": None,
            },
        ],
        "loan_recalls": [
            {
                "loan_id": "LN-5002",
                "status": "ISSUED",
                "issued_at": "2026-09-03T14:00",
                "due_date": "2026-09-04",
                "satisfied": False,
            },
        ],
        "loan_rerates": [
            {
                "loan_id": "LN-5003",
                "at": "2026-08-20",
                "from_bps": 30,
                "to_bps": 500,
                "by": "desk.auto",
            },
        ],
        "lending_availability": [
            {
                "security_id": "NVDA",
                "lendable_qty": 500000,
                "on_loan_qty": 180000,
                "gc_rate_bps": 25,
            },
            {
                "security_id": "AMZN",
                "lendable_qty": 200000,
                "on_loan_qty": 40000,
                "gc_rate_bps": 20,
            },
            {
                "security_id": "AAPL",
                "lendable_qty": 800000,
                "on_loan_qty": 120000,
                "gc_rate_bps": 15,
            },
        ],
    }


_S = FinanceStore(
    name="stockloan",
    read_tables=[stock_loans, loan_recalls, loan_rerates, lending_availability],
    action_table=loan_actions,
    action_prefix="SL",
    subject_key="loan_id",
    seed=_seed,
)


def reset() -> None:
    _S.reset()


def ensure_schema() -> None:
    _S.ensure_schema()


def get_loan(loan_id: str) -> dict[str, Any] | None:
    return _S.get("stock_loans", loan_id=loan_id)


def list_loans(security_id: str | None, account_id: str | None) -> list[dict[str, Any]]:
    return _S.find("stock_loans", security_id=security_id, account_id=account_id)


def get_recall(loan_id: str) -> dict[str, Any] | None:
    return _S.get("loan_recalls", loan_id=loan_id)


def get_rerate_history(loan_id: str) -> list[dict[str, Any]]:
    rows = _S.find("loan_rerates", loan_id=loan_id)
    for r in rows:
        r.pop("id", None)
    return rows


def get_lending_availability(security_id: str) -> dict[str, Any] | None:
    return _S.get("lending_availability", security_id=security_id)


def record_action(
    kind: str, loan_id: str, detail: dict[str, Any], approval_id: str
) -> dict[str, Any]:
    return _S.record_action(kind, loan_id, detail, approval_id)


def actions() -> list[dict[str, Any]]:
    return _S.actions()
