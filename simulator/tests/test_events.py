"""DB-backed: `emit_settlement_failed` / `emit_wire_held` write well-formed outbox rows.

Skipped if no database is reachable (mirrors `test_seed_integration.py`).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import Connection, select, text
from sqlalchemy.exc import OperationalError

from simulator import events
from simulator.db import connect


@pytest.fixture
def conn() -> Iterator[Connection]:
    try:
        with connect() as c:
            c.execute(text("select 1"))
            yield c
    except OperationalError:
        pytest.skip("no database reachable at DATABASE_URL")


def test_emit_settlement_failed_writes_an_outbox_row(conn: Connection) -> None:
    events.ensure_outbox(conn)
    conn.execute(text("delete from outbox_events where subject_id = 'T-SIM-1'"))

    key = events.emit_settlement_failed(
        conn, "T-SIM-1", failure_code="COUNTERPARTY_SSI_MISMATCH", deadline="2026-09-04T11:00:00"
    )
    assert key == "T-SIM-1:COUNTERPARTY_SSI_MISMATCH"

    row = (
        conn.execute(
            select(events.outbox_events).where(events.outbox_events.c.subject_id == "T-SIM-1")
        )
        .mappings()
        .one()
    )
    assert row["topic"] == "settlement.events"
    assert row["event_type"] == "FAILED"
    assert row["dedup_key"] == key
    assert row["payload"]["failure_code"] == "COUNTERPARTY_SSI_MISMATCH"
    assert row["payload"]["deadline"] == "2026-09-04T11:00:00"
    assert row["published_at"] is None


def test_emit_wire_held_writes_an_outbox_row(conn: Connection) -> None:
    events.ensure_outbox(conn)
    conn.execute(text("delete from outbox_events where subject_id = 'W-SIM-1'"))

    key = events.emit_wire_held(
        conn, "W-SIM-1", hold_reason="NEW_BENEFICIARY", deadline="2026-09-06T16:00:00"
    )
    assert key == "W-SIM-1:NEW_BENEFICIARY"

    row = (
        conn.execute(
            select(events.outbox_events).where(events.outbox_events.c.subject_id == "W-SIM-1")
        )
        .mappings()
        .one()
    )
    assert row["topic"] == "wire.events"
    assert row["event_type"] == "HELD"
    assert row["subject_type"] == "wire"
    assert row["dedup_key"] == key
    assert row["payload"]["hold_reason"] == "NEW_BENEFICIARY"
    assert row["payload"]["deadline"] == "2026-09-06T16:00:00"
    assert row["published_at"] is None
