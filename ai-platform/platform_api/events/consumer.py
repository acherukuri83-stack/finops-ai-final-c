"""The consumer: an event → a case → an investigation, with no user in the loop.

- **Routing** — a `trade` FAILED event runs `investigate`; a `wire` HELD event runs
  `investigate_wire` (Phase B). Client subjects and other event types are `OUT_OF_SCOPE`.
- **Dedup** — a repeat of the same problem for the same subject (`Event.dedup_key`, which
  keys on `failure_code` for a trade or `hold_reason` for a wire) is folded into the
  still-open case with an audit note; it does not start a second investigation.
- **Urgency** — a `deadline` in the payload inside the 60-minute window (a wire's currency
  cutoff, a settlement deadline) marks the case `HIGH` and records why.
- The trace root span is the `event`; the investigation nests under it.

`run_poller` is the loop the app lifespan starts; `drain_once` is the same body without
the loop, for tests.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from agent_core.loop import investigate
from agent_core.reasoning.model_client import ModelClient
from agent_core.spans import set_attrs, span
from agent_core.wire import investigate_wire
from platform_api import cases
from platform_api.events.bus import Event, EventBus
from platform_api.settings import settings

_URGENT_WINDOW = timedelta(minutes=60)


def _urgency(event: Event) -> tuple[str, str]:
    raw = event.payload.get("deadline")
    if not raw:
        return "NORMAL", ""
    try:
        deadline = datetime.fromisoformat(str(raw))
    except ValueError:
        return "NORMAL", ""
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=UTC)
    left = deadline - datetime.now(UTC)
    if left <= _URGENT_WINDOW:
        mins = max(0, int(left.total_seconds() // 60))
        return "HIGH", f"deadline {raw} (~{mins} min out) — prioritised HIGH"
    return "NORMAL", ""


async def handle_event(event: Event, *, client: ModelClient | None = None) -> str | None:
    """Process one event. Returns the case id, or None if nothing was opened."""
    existing = cases.find_open_by_dedup_key(event.dedup_key)
    if existing is not None:
        cases.update_case(
            existing["case_id"],
            f"repeat {event.type} event for {event.subject_id} at "
            f"{event.occurred_at:%Y-%m-%d %H:%M:%S} — folded into this case",
        )
        return str(existing["case_id"])

    priority, deadline_note = _urgency(event)
    with span(
        f"event:{event.type.lower()}",
        "event",
        **{
            "event.type": event.type,
            "event.topic": event.topic,
            "event.key": event.dedup_key,
            "event.subject": f"{event.subject_type}:{event.subject_id}",
            "event.deadline": event.payload.get("deadline"),
        },
    ) as root:
        if event.subject_type == "trade":
            finding = await investigate(event.subject_id, client=client)
        elif event.subject_type == "wire" and event.type == "HELD":
            # Phase B — a held outgoing wire runs the Wire specialist (maker only).
            finding = await investigate_wire(event.subject_id, client=client)
        else:
            # client subjects, and non-HELD wire events, have no module to run here.
            set_attrs(root, {"outcome": "OUT_OF_SCOPE"})
            return None
        set_attrs(
            root,
            {"outcome": finding.outcome, "case.id": finding.case_id, "priority": priority},
        )

    note = f"opened from a {event.type} event on {event.topic}"
    if deadline_note:
        note = f"{note}; {deadline_note}"

    if not finding.case_id:
        # the investigation proposed nothing, so the loop opened no case — open a tracking
        # case so the event is visible and a repeat dedups.
        case = cases.create_case(
            event.subject_type,
            event.subject_id,
            finding.root_cause or finding.outcome.value,
            trace_id=finding.trace_id,
            source="event",
            priority=priority,
            dedup_key=event.dedup_key,
        )
        cases.update_case(case["case_id"], note)
        return str(case["case_id"])

    cases.set_meta(finding.case_id, source="event", priority=priority, dedup_key=event.dedup_key)
    cases.update_case(finding.case_id, note)
    return finding.case_id


async def drain_once(
    bus: EventBus, *, batch: int | None = None, client: ModelClient | None = None
) -> int:
    """Poll one batch, handle each event, ack. Returns how many were handled."""
    events = await bus.poll(batch or settings.event_batch)
    handled: list[str] = []
    for event in events:
        try:
            await handle_event(event, client=client)
            handled.append(event.id)
        except Exception as exc:  # noqa: BLE001 — one bad event must not sink the batch
            print(f"[event-consumer] {event.type} {event.subject_id}: {type(exc).__name__}: {exc}")
            handled.append(event.id)  # ack anyway; the failure is logged, retry is manual
    await bus.ack(handled)
    return len(events)


async def run_poller(
    bus: EventBus,
    *,
    interval: float | None = None,
    batch: int | None = None,
    stop: asyncio.Event | None = None,
    client: ModelClient | None = None,
) -> None:
    """Drain the bus every `interval` seconds until `stop` is set or the task is cancelled."""
    wait = interval or settings.event_poll_seconds
    print(f"[event-consumer] polling {settings.event_bus} every {wait}s")
    while stop is None or not stop.is_set():
        try:
            await drain_once(bus, batch=batch, client=client)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            print(f"[event-consumer] poll error: {type(exc).__name__}: {exc}")
        if stop is None:
            await asyncio.sleep(wait)
        else:
            try:
                await asyncio.wait_for(stop.wait(), timeout=wait)
            except TimeoutError:
                pass
    await bus.close()
