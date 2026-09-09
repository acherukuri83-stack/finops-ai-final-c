"""Event-driven investigations (Phase D): a bus, an in-process consumer, and dedup."""

from __future__ import annotations

from platform_api.events.bus import SETTLEMENT_TOPIC, WIRE_TOPIC, Event, EventBus
from platform_api.events.consumer import drain_once, handle_event, run_poller
from platform_api.settings import settings

__all__ = [
    "Event",
    "EventBus",
    "SETTLEMENT_TOPIC",
    "WIRE_TOPIC",
    "get_bus",
    "handle_event",
    "drain_once",
    "run_poller",
]


def get_bus() -> EventBus:
    """The configured bus. `outbox` (default) needs only Postgres; `kafka` needs a broker."""
    if settings.event_bus == "kafka":
        from platform_api.events.kafka import KafkaEventBus

        return KafkaEventBus()
    from platform_api.events.outbox import PostgresOutboxBus

    return PostgresOutboxBus()
