"""OpenTelemetry bootstrap. One trace id flows React → FastAPI → httpx → Spring Boot.

Spans go to two places: the OTLP exporter (Jaeger, for engineers) and — when
`TRACES_ENABLED` — a `PostgresSpanProcessor` that persists every span to the `traces` /
`spans` / `span_payloads` tables for the in-portal Agent Trace screen.

Span attribute names follow docs/standards/observability.md.
"""

from __future__ import annotations

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from platform_api.settings import settings


class PostgresSpanProcessor(SpanProcessor):
    """Write every finished span to Postgres via `platform_api.trace_store`."""

    def on_start(self, span: object, parent_context: object | None = None) -> None:
        return None

    def on_end(self, span: ReadableSpan) -> None:
        from platform_api import trace_store

        trace_store.record_span(span)

    def shutdown(self) -> None:
        return None

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return True


def init_tracing() -> None:
    provider = TracerProvider(resource=Resource.create({"service.name": settings.service_name}))
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(endpoint=f"{settings.otel_exporter_otlp_endpoint}/v1/traces")
        )
    )
    if settings.traces_enabled:
        provider.add_span_processor(PostgresSpanProcessor())
    trace.set_tracer_provider(provider)
    HTTPXClientInstrumentor().instrument()


def tracer() -> trace.Tracer:
    return trace.get_tracer("finops")
