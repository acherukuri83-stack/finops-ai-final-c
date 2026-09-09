"""`PostgresOutboxBus` — the real bus. `publish` inserts a row into `outbox_events`;
`poll` returns the unhandled rows (oldest first, `FOR UPDATE SKIP LOCKED` so two pollers
don't double-handle); `ack` stamps `published_at`. No broker, no extra process.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update

from platform_api import store
from platform_api.events.bus import Event


class PostgresOutboxBus:
    async def publish(self, event: Event) -> str:
        with store.connect() as conn:
            new_id = conn.execute(
                store.outbox_events.insert()
                .values(
                    topic=event.topic,
                    event_type=event.type,
                    dedup_key=event.dedup_key,
                    subject_type=event.subject_type,
                    subject_id=event.subject_id,
                    payload=event.payload,
                    occurred_at=event.occurred_at,
                )
                .returning(store.outbox_events.c.id)
            ).scalar_one()
        return str(new_id)

    async def poll(self, limit: int) -> list[Event]:
        with store.connect() as conn:
            rows = (
                conn.execute(
                    select(store.outbox_events)
                    .where(store.outbox_events.c.published_at.is_(None))
                    .order_by(store.outbox_events.c.id)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
                .mappings()
                .all()
            )
            if rows:
                conn.execute(
                    update(store.outbox_events)
                    .where(store.outbox_events.c.id.in_([r["id"] for r in rows]))
                    .values(attempts=store.outbox_events.c.attempts + 1)
                )
        return [
            Event(
                id=str(r["id"]),
                topic=r["topic"],
                type=r["event_type"],
                subject_type=r["subject_type"],
                subject_id=r["subject_id"],
                payload=r["payload"] or {},
                occurred_at=r["occurred_at"],
            )
            for r in rows
        ]

    async def ack(self, event_ids: list[str]) -> None:
        if not event_ids:
            return
        with store.connect() as conn:
            conn.execute(
                update(store.outbox_events)
                .where(store.outbox_events.c.id.in_([int(i) for i in event_ids]))
                .values(published_at=datetime.now(UTC))
            )

    async def close(self) -> None:
        return None
