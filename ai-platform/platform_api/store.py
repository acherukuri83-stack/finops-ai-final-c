"""Case / approval / audit persistence for the platform tier.

Idempotent `CREATE TABLE IF NOT EXISTS` in the same Postgres the rest of the stack uses —
the pattern `knowledge/store.py` set, so it works against a bare `docker compose up
postgres` with no Flyway. The Java tier stays out of this entirely.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import (
    Boolean,
    Column,
    Connection,
    DateTime,
    Engine,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from platform_api.settings import settings

_metadata = MetaData()

cases = Table(
    "cases",
    _metadata,
    Column("case_id", String, primary_key=True),
    Column("subject_type", String, nullable=False),
    Column("subject_id", String, nullable=False),
    Column("summary", String, nullable=False),
    Column("status", String, nullable=False, server_default="OPEN"),
    Column("trace_id", String, server_default=""),  # the investigation trace that opened it
    Column("source", String, nullable=False, server_default="user"),  # user | event (Phase D)
    Column("priority", String, nullable=False, server_default="NORMAL"),  # NORMAL | HIGH
    Column("dedup_key", String),  # {subject}:{failure_code} — a repeat event reuses the case
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)

# Phase D: the outbox the simulator writes FAILED / HELD events to and the in-process
# consumer drains. `published_at IS NULL` = not yet handled.
outbox_events = Table(
    "outbox_events",
    _metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("topic", String, nullable=False),  # settlement.events | wire.events
    Column("event_type", String, nullable=False),  # FAILED | HELD
    Column("dedup_key", String, nullable=False),
    Column("subject_type", String, nullable=False),
    Column("subject_id", String, nullable=False),
    Column("payload", JSONB, nullable=False, server_default="{}"),
    Column("occurred_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("published_at", DateTime(timezone=True)),  # set when the consumer acks
    Column("attempts", Integer, nullable=False, server_default="0"),
)

approvals = Table(
    "approvals",
    _metadata,
    Column("approval_id", String, primary_key=True),
    Column("case_id", String, nullable=False),
    Column("action_type", String, nullable=False),
    Column("params", JSONB, nullable=False, server_default="{}"),
    Column("rationale", String, nullable=False, server_default=""),
    Column("impact", JSONB, nullable=False, server_default="[]"),
    Column("reversible", Boolean, nullable=False, server_default="true"),
    Column("status", String, nullable=False, server_default="PENDING"),
    Column("decided_by", String),
    Column("role", String),
    Column("decided_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)

audit_events = Table(
    "audit_events",
    _metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("case_id", String, nullable=False),
    Column("event", String, nullable=False),
    Column("at", DateTime(timezone=True), server_default=func.now()),
)

_engine: Engine | None = None


def engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(settings.database_url, future=True)
    return _engine


@contextmanager
def connect() -> Iterator[Connection]:
    with engine().begin() as conn:
        yield conn


def ensure_schema() -> None:
    with engine().begin() as conn:
        conn.execute(text("create sequence if not exists case_seq"))
        _metadata.create_all(conn.engine, tables=[cases, approvals, audit_events, outbox_events])
        # additive columns for a `cases` table created before W4 / Phase D
        for ddl in (
            "alter table cases add column if not exists trace_id varchar default ''",
            "alter table cases add column if not exists source varchar not null default 'user'",
            "alter table cases add column if not exists priority varchar not null default 'NORMAL'",
            "alter table cases add column if not exists dedup_key varchar",
        ):
            conn.execute(text(ddl))
    from mcp_servers import _finance_store

    _finance_store.ensure_all_schemas()  # stockloan / margin / corpactions / cash tables

    from platform_api import trace_store

    trace_store.ensure_schema()
