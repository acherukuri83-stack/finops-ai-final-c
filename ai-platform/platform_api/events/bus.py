"""The event contract and the bus interface (Phase D).

One `Event` shape for every topic. Two implementations — `PostgresOutboxBus` (the real
one; works with no broker, local and hosted) and `KafkaEventBus` (lazy adapter) — behind
the `EventBus` protocol so the consumer code is identical.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import BaseModel, Field

SETTLEMENT_TOPIC = "settlement.events"
WIRE_TOPIC = "wire.events"


class Event(BaseModel):
    """A thing that happened in the estate. `id` is set by the bus on publish."""

    id: str = ""
    topic: str = SETTLEMENT_TOPIC
    type: str  # FAILED | HELD
    subject_type: str = "trade"
    subject_id: str
    payload: dict[str, Any] = Field(default_factory=dict)  # failure_code, deadline, …
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def dedup_key(self) -> str:
        """A repeat of the *same problem* for the same subject collapses onto one case."""
        marker = self.payload.get("failure_code") or self.payload.get("hold_reason") or self.type
        return f"{self.subject_id}:{marker}"


class EventBus(Protocol):
    async def publish(self, event: Event) -> str: ...
    async def poll(self, limit: int) -> list[Event]: ...
    async def ack(self, event_ids: list[str]) -> None: ...
    async def close(self) -> None: ...
