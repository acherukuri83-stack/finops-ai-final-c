"""SQLAlchemy Core table definitions mirroring `enterprise`'s Flyway schema (V2).

The simulator writes directly to Postgres; it does not share JPA entities with the
Java tier (deliberately — two independent stacks per CLAUDE.md). Keep this in sync
with `enterprise/src/main/resources/db/migration/V2__phase_a_schema.sql` by hand.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    MetaData,
    Numeric,
    String,
    Table,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

clients = Table(
    "clients",
    metadata,
    Column("client_id", String, primary_key=True),
    Column("name", String),
    Column("type", String),
    Column("status", String),
)

accounts = Table(
    "accounts",
    metadata,
    Column("account_id", String, primary_key=True),
    Column("client_id", String),
    Column("custodian", String),
    Column("status", String),
)

ssi_versions = Table(
    "ssi_versions",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("account_id", String),
    Column("version", BigInteger),
    Column("dtc_participant", String),
    Column("agent_bic", String),
    Column("valid_from", Date),
    Column("valid_to", Date),
    Column("updated_at", DateTime),
    Column("updated_by", String),
)

securities = Table(
    "securities",
    metadata,
    Column("security_id", String, primary_key=True),
    Column("isin", String),
    Column("cusip", String),
    Column("description", String),
    Column("settle_cycle", String),
    Column("status", String),
)

market_calendar = Table(
    "market_calendar",
    metadata,
    Column("market", String, primary_key=True),
    Column("calendar_date", Date, primary_key=True),
    Column("is_business_day", Boolean),
    Column("holiday_name", String),
)

prices = Table(
    "prices",
    metadata,
    Column("security_id", String, primary_key=True),
    Column("price_date", Date, primary_key=True),
    Column("close_price", Numeric),
)

counterparties = Table(
    "counterparties",
    metadata,
    Column("cpty_id", String, primary_key=True),
    Column("name", String),
    Column("status", String),
)

counterparty_ssi = Table(
    "counterparty_ssi",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("cpty_id", String),
    Column("dtc_participant", String),
    Column("valid_to", Date),
)

trades = Table(
    "trades",
    metadata,
    Column("trade_id", String, primary_key=True),
    Column("client_id", String),
    Column("account_id", String),
    Column("security_id", String),
    Column("qty", BigInteger),
    Column("side", String),
    Column("price", Numeric),
    Column("trade_date", Date),
    Column("settle_date", Date),
    Column("status", String),
    Column("failure_code", String),
    Column("cpty_id", String),
    Column("booked_at", DateTime),
)

settlement_attempts = Table(
    "settlement_attempts",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("trade_id", String),
    Column("at", DateTime),
    Column("result", String),
    Column("detail", String),
)

affirmations = Table(
    "affirmations",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("trade_id", String),
    Column("cpty_id", String),
    Column("cpty_dtc", String),
    Column("affirmed", Boolean),
    Column("affirmed_at", DateTime),
)

positions = Table(
    "positions",
    metadata,
    Column("account_id", String, primary_key=True),
    Column("security_id", String, primary_key=True),
    Column("as_of", Date, primary_key=True),
    Column("qty", BigInteger),
    Column("available", BigInteger),
    Column("pending_deliver", BigInteger),
    Column("pending_receive", BigInteger),
)

borrow_availability = Table(
    "borrow_availability",
    metadata,
    Column("security_id", String, primary_key=True),
    Column("available_qty", BigInteger),
    Column("rate", Numeric),
    Column("recalls", JSONB),
)

restrictions = Table(
    "restrictions",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("account_id", String),
    Column("type", String),
    Column("reason", String),
    Column("set_by", String),
    Column("set_at", DateTime),
    Column("active", Boolean),
)

screening_results = Table(
    "screening_results",
    metadata,
    Column("client_id", String, primary_key=True),
    Column("status", String),
    Column("checked_at", DateTime),
)

app_logs = Table(
    "app_logs",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("ts", DateTime),
    Column("svc", String),
    Column("level", String),
    Column("msg", String),
    Column("trade_id", String),
)

incidents = Table(
    "incidents",
    metadata,
    Column("incident_id", String, primary_key=True),
    Column("occurred_at", DateTime),
    Column("status", String),
)

ALL_TABLES = [
    app_logs,
    incidents,
    restrictions,
    screening_results,
    borrow_availability,
    positions,
    affirmations,
    settlement_attempts,
    trades,
    counterparty_ssi,
    counterparties,
    prices,
    market_calendar,
    securities,
    ssi_versions,
    accounts,
    clients,
]
"""Child-to-parent order, safe for TRUNCATE ... CASCADE in any order, and for
per-table deletes that must run before their FK targets."""
