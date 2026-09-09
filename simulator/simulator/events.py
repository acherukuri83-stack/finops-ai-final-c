"""Publish estate events onto the platform outbox (Phase D).

`outbox_events` is a *platform-tier* table (owned by
`ai-platform/platform_api/store.py`), not part of the enterprise Flyway schema — so it
lives here, separate from `simulator/tables.py`, with an idempotent `CREATE TABLE IF NOT
EXISTS` that must match `store.py`. The in-process consumer in `ai-platform` drains it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Column,
    Connection,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

_md = MetaData()

outbox_events = Table(
    "outbox_events",
    _md,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("topic", String, nullable=False),
    Column("event_type", String, nullable=False),
    Column("dedup_key", String, nullable=False),
    Column("subject_type", String, nullable=False),
    Column("subject_id", String, nullable=False),
    Column("payload", JSONB, nullable=False, server_default="{}"),
    Column("occurred_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("published_at", DateTime(timezone=True)),
    Column("attempts", Integer, nullable=False, server_default="0"),
)


def ensure_outbox(conn: Connection) -> None:
    _md.create_all(conn.engine, tables=[outbox_events])


def emit_settlement_failed(
    conn: Connection,
    trade_id: str,
    *,
    failure_code: str | None = None,
    deadline: str | None = None,
    occurred_at: datetime | None = None,
) -> str:
    """Insert a FAILED settlement event for `trade_id`. Returns its dedup key.

    `failure_code` defaults to the trade's own; `deadline` (ISO-8601) inside 60 min makes
    the consumer mark the case HIGH priority.
    """
    ensure_outbox(conn)
    if failure_code is None:
        row = conn.execute(
            text("select failure_code from trades where trade_id = :t"), {"t": trade_id}
        ).first()
        failure_code = (row[0] if row and row[0] else None) or "UNKNOWN"

    payload: dict[str, Any] = {"failure_code": failure_code}
    if deadline:
        payload["deadline"] = deadline
    dedup_key = f"{trade_id}:{failure_code}"
    conn.execute(
        outbox_events.insert().values(
            topic="settlement.events",
            event_type="FAILED",
            dedup_key=dedup_key,
            subject_type="trade",
            subject_id=trade_id,
            payload=payload,
            occurred_at=occurred_at or datetime.now(UTC),
        )
    )
    return dedup_key


def emit_wire_held(
    conn: Connection,
    wire_id: str,
    *,
    hold_reason: str | None = None,
    deadline: str | None = None,
    occurred_at: datetime | None = None,
) -> str:
    """Insert a HELD wire event for `wire_id` on `wire.events`. Returns its dedup key.

    `hold_reason` defaults to the wire's own; `deadline` (ISO-8601, typically the
    currency cutoff) inside 60 min makes the consumer mark the case HIGH priority. The
    in-process consumer runs the Wire specialist (`investigate_wire`).
    """
    ensure_outbox(conn)
    if hold_reason is None:
        row = conn.execute(
            text("select hold_reason from wires where wire_id = :w"), {"w": wire_id}
        ).first()
        hold_reason = (row[0] if row and row[0] else None) or "HELD"

    payload: dict[str, Any] = {"hold_reason": hold_reason}
    if deadline:
        payload["deadline"] = deadline
    dedup_key = f"{wire_id}:{hold_reason}"
    conn.execute(
        outbox_events.insert().values(
            topic="wire.events",
            event_type="HELD",
            dedup_key=dedup_key,
            subject_type="wire",
            subject_id=wire_id,
            payload=payload,
            occurred_at=occurred_at or datetime.now(UTC),
        )
    )
    return dedup_key
