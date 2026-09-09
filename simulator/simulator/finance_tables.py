"""SQLAlchemy Core defs for the prime-finance tables (stockloan / margin / corpactions
/ cash).

These are **platform-tier** tables, not enterprise/Flyway ones: the AI platform owns them
(`ai-platform/mcp_servers/_finance_store.py` + the four `mcp_servers/<domain>/store.py`),
the same way `platform_api.store` owns `cases` / `outbox_events`. The simulator writes to
them directly and creates them if missing — keep this file in sync with the ai-platform
`Table` defs by hand, exactly as `tables.py` mirrors the Java Flyway schema.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Connection,
    Date,
    DateTime,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
)
from sqlalchemy.dialects.postgresql import JSONB

finance_metadata = MetaData()

# --- stockloan ---------------------------------------------------------------

stock_loans = Table(
    "stock_loans",
    finance_metadata,
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
    finance_metadata,
    Column("loan_id", String, primary_key=True),
    Column("status", String),
    Column("issued_at", DateTime),
    Column("due_date", Date),
    Column("satisfied", Boolean),
)

loan_rerates = Table(
    "loan_rerates",
    finance_metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("loan_id", String),
    Column("at", Date),
    Column("from_bps", Integer),
    Column("to_bps", Integer),
    Column("by", String),
)

lending_availability = Table(
    "lending_availability",
    finance_metadata,
    Column("security_id", String, primary_key=True),
    Column("lendable_qty", BigInteger),
    Column("on_loan_qty", BigInteger),
    Column("gc_rate_bps", Integer),
)

loan_actions = Table(
    "loan_actions",
    finance_metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("kind", String),
    Column("subject_id", String),
    Column("detail", JSONB),
    Column("status", String),
    Column("approval_id", String),
)

# --- margin ----------------------------------------------------------------

margin_calls = Table(
    "margin_calls",
    finance_metadata,
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
    finance_metadata,
    Column("account_id", String, primary_key=True),
    Column("requirement", BigInteger),
    Column("posted", BigInteger),
    Column("shortfall", BigInteger),
    Column("as_of", Date),
)

collateral = Table(
    "collateral",
    finance_metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("account_id", String),
    Column("security_id", String),
    Column("market_value", BigInteger),
    Column("haircut_pct", Integer),
    Column("eligible", Boolean),
)

collateral_eligibility = Table(
    "collateral_eligibility",
    finance_metadata,
    Column("security_id", String, primary_key=True),
    Column("eligible", Boolean),
    Column("haircut_pct", Integer),
    Column("rating", String),
)

margin_actions = Table(
    "margin_actions",
    finance_metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("kind", String),
    Column("subject_id", String),
    Column("detail", JSONB),
    Column("status", String),
    Column("approval_id", String),
)

# --- corpactions ---------------------------------------------------------

ca_events = Table(
    "ca_events",
    finance_metadata,
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
    finance_metadata,
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
    finance_metadata,
    Column("event_id", String, primary_key=True),
    Column("options", JSONB),
    Column("default", String),
    Column("submitted", String),
)

ca_actions = Table(
    "ca_actions",
    finance_metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("kind", String),
    Column("subject_id", String),
    Column("detail", JSONB),
    Column("status", String),
    Column("approval_id", String),
)

# --- cash --------------------------------------------------------------

cash_breaks = Table(
    "cash_breaks",
    finance_metadata,
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
    finance_metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("account_id", String),
    Column("currency", String),
    Column("time", DateTime),
    Column("flow", BigInteger),
    Column("kind", String),
)

credit_facilities = Table(
    "credit_facilities",
    finance_metadata,
    Column("account_id", String, primary_key=True),
    Column("currency", String, primary_key=True),
    Column("limit", BigInteger),
    Column("drawn", BigInteger),
    Column("headroom", BigInteger),
)

cash_actions = Table(
    "cash_actions",
    finance_metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("kind", String),
    Column("subject_id", String),
    Column("detail", JSONB),
    Column("status", String),
    Column("approval_id", String),
)

# child-to-parent-ish order; there are no FK constraints, so any order is TRUNCATE-safe.
FINANCE_TABLES = [
    loan_actions,
    loan_rerates,
    loan_recalls,
    stock_loans,
    lending_availability,
    margin_actions,
    collateral,
    collateral_eligibility,
    margin_status,
    margin_calls,
    ca_actions,
    ca_entitlements,
    ca_elections,
    ca_events,
    cash_actions,
    funding_ladders,
    credit_facilities,
    cash_breaks,
]


def ensure(conn: Connection) -> None:
    """CREATE TABLE IF NOT EXISTS for every finance table."""
    finance_metadata.create_all(conn, checkfirst=True)
