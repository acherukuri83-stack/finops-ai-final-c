# platform_api/events — conventions (Phase D)

- **One `Event` shape** (`bus.py`) for every topic. `Event.dedup_key` = `{subject_id}:{failure_code|hold_reason|type}`.
- **`PostgresOutboxBus` is the real bus** — `publish` inserts into `outbox_events`, `poll`
  reads unhandled rows `FOR UPDATE SKIP LOCKED`, `ack` stamps `published_at`. No broker,
  works local and hosted. `KafkaEventBus` is a lazy-import adapter (Redpanda in Compose),
  not exercised in CI. `get_bus()` picks by `settings.event_bus`.
- **The consumer runs in-process** (`main.py` lifespan → `run_poller`), gated by
  `settings.events_enabled`. One process on the demo (ADR-0005) — no separate worker.
- **Routing is code, not an LLM classify.** A `trade` FAILED event → `investigate(trade_id)`;
  a `wire` HELD event → `investigate_wire(wire_id)` (Phase B). Urgency comes from a
  `deadline` field (a wire's currency cutoff, a settlement deadline), not a model call.
- **Dedup is a case lookup**, not an event lookup: `cases.find_open_by_dedup_key` — a
  repeat event for the same open problem appends an audit note, no second investigation.
- **Trace root is the `event` span**; the investigation nests under it
  (`docs/standards/observability.md`).
- The consumer stamps `source="event"`, `priority`, `dedup_key` on the case
  (`cases.set_meta`) *after* the investigation, or opens a tracking case itself if the
  investigation proposed nothing.
- Client event subjects, and non-HELD wire events, are `OUT_OF_SCOPE` here.
