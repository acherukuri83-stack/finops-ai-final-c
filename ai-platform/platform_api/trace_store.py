"""Trace persistence for the Agent Trace screen.

Every OpenTelemetry span the agent emits is written here by `PostgresSpanProcessor`
(`platform_api/telemetry.py`); the loop calls `finalize_trace` when an investigation
completes to stamp the trace-level row (request, Finding, denormalised totals).

Same Postgres, same idempotent-DDL pattern as `platform_api/store.py`. Every write is
best-effort — a trace-DB failure must never fail an investigation — and the whole module
is a no-op when `settings.traces_enabled` is false (the eval harness scores Findings,
not traces).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from opentelemetry.sdk.trace import ReadableSpan
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    delete,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB, insert

from platform_api import store
from platform_api.settings import settings

_log = logging.getLogger("finops.trace_store")
_metadata = MetaData()

traces = Table(
    "traces",
    _metadata,
    Column("trace_id", String, primary_key=True),
    Column("subject_type", String, server_default=""),
    Column("subject_id", String, server_default=""),
    Column("request", String, server_default=""),
    Column("scenario_id", String, server_default=""),
    Column("case_id", String, server_default=""),
    Column("agent", String, server_default=""),
    Column("outcome", String, server_default=""),
    Column("root_cause", String, server_default=""),
    Column("status", String, nullable=False, server_default="RUNNING"),
    Column("started_at", DateTime(timezone=True)),
    Column("ended_at", DateTime(timezone=True)),
    Column("duration_ms", Integer, server_default="0"),
    Column("tool_calls", Integer, server_default="0"),
    Column("retrievals", Integer, server_default="0"),
    Column("model_calls", Integer, server_default="0"),
    Column("tokens_in", Integer, server_default="0"),
    Column("tokens_out", Integer, server_default="0"),
    Column("cost_usd", Float, server_default="0"),
    Column("finding", JSONB),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)

spans = Table(
    "spans",
    _metadata,
    Column("span_id", String, primary_key=True),
    Column("trace_id", String, nullable=False, index=True),
    Column("parent_span_id", String, server_default=""),
    Column("name", String, nullable=False),
    Column("span_type", String, server_default=""),
    Column("agent", String, server_default=""),
    Column("step", String, server_default=""),
    Column("started_at", DateTime(timezone=True)),
    Column("ended_at", DateTime(timezone=True)),
    Column("duration_ms", Integer, server_default="0"),
    Column("status", String, server_default=""),
    Column("attributes", JSONB, nullable=False, server_default="{}"),
)

span_payloads = Table(
    "span_payloads",
    _metadata,
    Column("span_id", String, primary_key=True),
    Column("payload_in", JSONB),
    Column("payload_out", JSONB),
)

# list price, USD per 1M tokens (input, output), keyed by a substring of the model id.
_PRICE = {"haiku": (0.80, 4.00), "sonnet": (3.00, 15.00), "opus": (15.00, 75.00)}


def _cost(model: str, tin: int, tout: int) -> float:
    pin, pout = next((p for k, p in _PRICE.items() if k in model.lower()), _PRICE["sonnet"])
    return round(tin / 1e6 * pin + tout / 1e6 * pout, 6)


def redact(obj: Any) -> Any:
    """Scrub PII before a payload is stored. Phase A data is fully fictional, so this is
    the identity — the single seam a real scrubber plugs into (see docs/backlog.md).
    """
    return obj


def ensure_schema() -> None:
    _metadata.create_all(store.engine(), tables=[traces, spans, span_payloads])


# --- writes (best-effort) -----------------------------------------------------


def _ns_to_dt(ns: int | None) -> datetime | None:
    return datetime.fromtimestamp(ns / 1e9, tz=UTC) if ns else None


def record_span(span: ReadableSpan) -> None:
    if not settings.traces_enabled or span.context is None:
        return
    try:
        attrs = dict(span.attributes or {})
        payload_in = _maybe_json(attrs.pop("finops.payload.in", None))
        payload_out = _maybe_json(attrs.pop("finops.payload.out", None))
        span_id = f"{span.context.span_id:016x}"
        started, ended = _ns_to_dt(span.start_time), _ns_to_dt(span.end_time)
        duration = (
            int((span.end_time - span.start_time) / 1e6) if span.end_time and span.start_time else 0
        )
        row = {
            "span_id": span_id,
            "trace_id": f"{span.context.trace_id:032x}",
            "parent_span_id": f"{span.parent.span_id:016x}" if span.parent else "",
            "name": span.name,
            "span_type": attrs.get("finops.span.type", ""),
            "agent": attrs.get("finops.agent", ""),
            "step": attrs.get("finops.step", ""),
            "started_at": started,
            "ended_at": ended,
            "duration_ms": duration,
            "status": span.status.status_code.name if span.status else "",
            "attributes": attrs,
        }
        with store.connect() as conn:
            conn.execute(_upsert(spans, row, "span_id"))
            if payload_in is not None or payload_out is not None:
                conn.execute(
                    _upsert(
                        span_payloads,
                        {
                            "span_id": span_id,
                            "payload_in": redact(payload_in),
                            "payload_out": redact(payload_out),
                        },
                        "span_id",
                    )
                )
    except Exception:  # noqa: BLE001 — tracing must never break the request
        _log.warning("record_span failed for %s", span.name, exc_info=True)


def finalize_trace(
    trace_id: str,
    *,
    request: str,
    subject_type: str,
    subject_id: str,
    scenario_id: str | None,
    case_id: str,
    agent: str,
    outcome: str,
    root_cause: str | None,
    status: str,
    finding: dict[str, Any] | None,
) -> None:
    if not settings.traces_enabled:
        return
    try:
        with store.connect() as conn:
            rows = list(
                conn.execute(
                    select(
                        spans.c.span_type,
                        spans.c.started_at,
                        spans.c.ended_at,
                        spans.c.attributes,
                    ).where(spans.c.trace_id == trace_id)
                ).mappings()
            )
            tool_calls = sum(r["span_type"] == "tool" for r in rows)
            retrievals = sum(r["span_type"] == "retrieval" for r in rows)
            model_rows = [r for r in rows if "finops.tokens.in" in (r["attributes"] or {})]
            tokens_in = sum(int(r["attributes"]["finops.tokens.in"]) for r in model_rows)
            tokens_out = sum(int(r["attributes"].get("finops.tokens.out", 0)) for r in model_rows)
            cost = sum(
                _cost(
                    str(r["attributes"].get("finops.model", "")),
                    int(r["attributes"]["finops.tokens.in"]),
                    int(r["attributes"].get("finops.tokens.out", 0)),
                )
                for r in model_rows
            )
            starts = [r["started_at"] for r in rows if r["started_at"]]
            ends = [r["ended_at"] for r in rows if r["ended_at"]]
            started_at = min(starts) if starts else None
            ended_at = max(ends) if ends else None
            duration_ms = (
                int((ended_at - started_at).total_seconds() * 1000)
                if started_at and ended_at
                else 0
            )
            conn.execute(
                _upsert(
                    traces,
                    {
                        "trace_id": trace_id,
                        "subject_type": subject_type,
                        "subject_id": subject_id,
                        "request": request,
                        "scenario_id": scenario_id or "",
                        "case_id": case_id,
                        "agent": agent,
                        "outcome": outcome,
                        "root_cause": root_cause or "",
                        "status": status,
                        "started_at": started_at,
                        "ended_at": ended_at,
                        "duration_ms": duration_ms,
                        "tool_calls": tool_calls,
                        "retrievals": retrievals,
                        "model_calls": len(model_rows),
                        "tokens_in": tokens_in,
                        "tokens_out": tokens_out,
                        "cost_usd": round(cost, 6),
                        "finding": finding,
                    },
                    "trace_id",
                )
            )
    except Exception:  # noqa: BLE001
        _log.warning("finalize_trace failed for %s", trace_id, exc_info=True)


# --- reads ------------------------------------------------------------------


def list_traces(
    *, case_id: str | None = None, scenario_id: str | None = None, limit: int = 50
) -> list[dict[str, Any]]:
    if not settings.traces_enabled:
        return []
    with store.connect() as conn:
        stmt = select(traces).order_by(traces.c.created_at.desc()).limit(limit)
        if case_id:
            stmt = stmt.where(traces.c.case_id == case_id)
        if scenario_id:
            stmt = stmt.where(traces.c.scenario_id == scenario_id)
        return [dict(r) for r in conn.execute(stmt).mappings()]


def get_trace(trace_id: str) -> dict[str, Any] | None:
    if not settings.traces_enabled:
        return None
    with store.connect() as conn:
        trace = conn.execute(select(traces).where(traces.c.trace_id == trace_id)).mappings().first()
        if trace is None:
            return None
        span_rows = (
            conn.execute(
                select(spans).where(spans.c.trace_id == trace_id).order_by(spans.c.started_at)
            )
            .mappings()
            .all()
        )
        payloads = {
            r["span_id"]: {"payload_in": r["payload_in"], "payload_out": r["payload_out"]}
            for r in conn.execute(
                select(span_payloads).where(
                    span_payloads.c.span_id.in_([s["span_id"] for s in span_rows] or [""])
                )
            ).mappings()
        }
    out_spans = [{**dict(s), **payloads.get(s["span_id"], {})} for s in span_rows]
    return {**dict(trace), "spans": out_spans}


def record_approval_span(
    trace_id: str, *, approval_id: str, status: str, by: str, role: str, elapsed_ms: int
) -> None:
    """A human approve/reject lands in a separate request; stitch it into the case's
    trace as an `approval` span so the timeline shows the whole story."""
    if not settings.traces_enabled or not trace_id:
        return
    try:
        with store.connect() as conn:
            root = conn.execute(
                select(spans.c.span_id)
                .where(spans.c.trace_id == trace_id, spans.c.parent_span_id == "")
                .limit(1)
            ).scalar()
            now = datetime.now(UTC)
            conn.execute(
                _upsert(
                    spans,
                    {
                        "span_id": f"approval-{approval_id}",
                        "trace_id": trace_id,
                        "parent_span_id": root or "",
                        "name": f"approval {approval_id}",
                        "span_type": "approval",
                        "agent": "",
                        "step": "",
                        "started_at": now,
                        "ended_at": now,
                        "duration_ms": 0,
                        "status": "OK",
                        "attributes": {
                            "finops.span.type": "approval",
                            "finops.approval.id": approval_id,
                            "finops.approval.status": status,
                            "finops.approval.by": by,
                            "finops.approval.role": role,
                            "finops.approval.elapsed_ms": elapsed_ms,
                        },
                    },
                    "span_id",
                )
            )
    except Exception:  # noqa: BLE001
        _log.warning("record_approval_span failed for %s", approval_id, exc_info=True)


def delete_trace(trace_id: str) -> None:
    with store.connect() as conn:
        ids = [
            r[0] for r in conn.execute(select(spans.c.span_id).where(spans.c.trace_id == trace_id))
        ]
        if ids:
            conn.execute(delete(span_payloads).where(span_payloads.c.span_id.in_(ids)))
        conn.execute(delete(spans).where(spans.c.trace_id == trace_id))
        conn.execute(delete(traces).where(traces.c.trace_id == trace_id))


# --- helpers ---------------------------------------------------------------


def _upsert(table: Table, row: dict[str, Any], pk: str) -> Any:
    stmt = insert(table).values(**row)
    return stmt.on_conflict_do_update(
        index_elements=[pk], set_={k: v for k, v in row.items() if k != pk}
    )


def _maybe_json(value: Any) -> Any:
    if value is None or not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value
