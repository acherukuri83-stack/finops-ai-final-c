"""`KafkaEventBus` — the local-with-a-broker path (Redpanda in Compose). Same interface
as `PostgresOutboxBus`; `aiokafka` is imported lazily so it is not a hard dependency and
CI (which has no broker) never touches this file. Not exercised in the current dev/CI
environment — see `docs/backlog.md`.
"""

from __future__ import annotations

import json
from typing import Any

from platform_api.events.bus import Event
from platform_api.settings import settings


class KafkaEventBus:
    def __init__(self, topics: list[str] | None = None) -> None:
        self._topics = topics or ["settlement.events", "wire.events"]
        self._producer: Any = None
        self._consumer: Any = None

    async def _ensure(self) -> None:
        if self._producer is not None:
            return
        try:
            from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "event_bus=kafka needs `aiokafka` installed and a broker at KAFKA_BOOTSTRAP"
            ) from exc
        bootstrap = settings.kafka_bootstrap or "localhost:9092"
        self._producer = AIOKafkaProducer(bootstrap_servers=bootstrap)
        self._consumer = AIOKafkaConsumer(
            *self._topics,
            bootstrap_servers=bootstrap,
            group_id="finops-consumer",
            enable_auto_commit=False,
        )
        await self._producer.start()
        await self._consumer.start()

    async def publish(self, event: Event) -> str:
        await self._ensure()
        await self._producer.send_and_wait(
            event.topic, json.dumps(event.model_dump(mode="json")).encode()
        )
        return event.id or event.dedup_key

    async def poll(self, limit: int) -> list[Event]:
        await self._ensure()
        batch = await self._consumer.getmany(timeout_ms=500, max_records=limit)
        out: list[Event] = []
        for records in batch.values():
            for rec in records:
                out.append(Event.model_validate(json.loads(rec.value)))
        return out

    async def ack(self, event_ids: list[str]) -> None:
        if self._consumer is not None:
            await self._consumer.commit()

    async def close(self) -> None:
        if self._producer is not None:
            await self._producer.stop()
        if self._consumer is not None:
            await self._consumer.stop()
