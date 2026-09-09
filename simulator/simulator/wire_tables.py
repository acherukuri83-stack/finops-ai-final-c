"""SQLAlchemy Core defs for the wire tables (Phase B — Wires, optional module).

Platform-tier tables owned by `ai-platform/mcp_servers/wire/store.py`, seeded by the
simulator. Keep in sync with that file by hand, as `tables.py` mirrors the Java Flyway
schema and `finance_tables.py` mirrors the prime-finance stores.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Column,
    Connection,
    Date,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
)
from sqlalchemy.dialects.postgresql import JSONB

wire_metadata = MetaData()

wires = Table(
    "wires",
    wire_metadata,
    Column("wire_id", String, primary_key=True),
    Column("client_id", String),
    Column("account_id", String),
    Column("direction", String),
    Column("currency", String),
    Column("amount", BigInteger),
    Column("beneficiary", String),
    Column("beneficiary_account", String),
    Column("value_date", Date),
    Column("status", String),
    Column("hold_reason", String),
)

wire_standing_instructions = Table(
    "wire_standing_instructions",
    wire_metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("client_id", String),
    Column("beneficiary", String),
    Column("beneficiary_account", String),
    Column("added_at", Date),
    Column("added_by", String),
)

wire_screening = Table(
    "wire_screening",
    wire_metadata,
    Column("client_id", String, primary_key=True),
    Column("status", String),
    Column("matched_list", String),
    Column("checked_at", DateTime),
)

wire_balances = Table(
    "wire_balances",
    wire_metadata,
    Column("account_id", String, primary_key=True),
    Column("currency", String, primary_key=True),
    Column("available", BigInteger),
)

wire_audit_events = Table(
    "wire_audit_events",
    wire_metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("wire_id", String),
    Column("at", DateTime),
    Column("actor", String),
    Column("event", String),
)

wire_actions = Table(
    "wire_actions",
    wire_metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("kind", String),
    Column("subject_id", String),
    Column("detail", JSONB),
    Column("status", String),
    Column("approval_id", String),
)

WIRE_TABLES = [
    wire_actions,
    wire_audit_events,
    wire_balances,
    wire_screening,
    wire_standing_instructions,
    wires,
]


def ensure(conn: Connection) -> None:
    """CREATE TABLE IF NOT EXISTS for every wire table."""
    wire_metadata.create_all(conn, checkfirst=True)
