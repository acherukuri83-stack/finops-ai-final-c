"""EventBus protocol. Phase A ships only the no-op implementation.

Later: KafkaEventBus (local) and OutboxEventBus (hosted demo), same consumer code.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol

Handler = Callable[[dict[str, Any]], Awaitable[None]]


class EventBus(Protocol):
    async def publish(self, topic: str, event: dict[str, Any]) -> None: ...
    def subscribe(self, topic: str, handler: Handler) -> None: ...


class NoopEventBus:
    async def publish(self, topic: str, event: dict[str, Any]) -> None:
        return None

    def subscribe(self, topic: str, handler: Handler) -> None:
        return None
