"""Contract: the Postgres outbox round-trips against a real database (`-m contract`).

Skipped when no `DATABASE_URL` is set (local runs without the stack).
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

pytestmark = pytest.mark.contract


@pytest.fixture
def _pg() -> Iterator[None]:
    if not os.environ.get("DATABASE_URL") and not os.environ.get("ENTERPRISE_BASE_URL"):
        pytest.skip("needs Postgres at DATABASE_URL")
    from platform_api import store

    store.ensure_schema()  # idempotent — creates outbox_events if missing
    yield


async def test_outbox_publish_poll_ack_round_trip(_pg: None) -> None:
    from platform_api.events.bus import Event
    from platform_api.events.outbox import PostgresOutboxBus

    bus = PostgresOutboxBus()
    event = Event(type="FAILED", subject_id="T-CONTRACT-1", payload={"failure_code": "X"})

    event_id = await bus.publish(event)

    polled = await bus.poll(100)
    mine = next((e for e in polled if e.id == event_id), None)
    assert mine is not None
    assert mine.subject_id == "T-CONTRACT-1"
    assert mine.type == "FAILED"
    assert mine.dedup_key == "T-CONTRACT-1:X"

    await bus.ack([event_id])

    after = await bus.poll(100)
    assert all(e.id != event_id for e in after), "an acked row must not be polled again"
