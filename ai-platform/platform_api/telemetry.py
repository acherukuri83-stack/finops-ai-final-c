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


_pg_processor_added = False


def init_tracing() -> TracerProvider:
    """Install the tracer provider. Idempotent: if one is already set (e.g. a test
    already called this), reuse it and just add our processors once."""
    global _pg_processor_added
    existing = trace.get_tracer_provider()
    if isinstance(existing, TracerProvider):
        provider = existing
    else:
        provider = TracerProvider(
            resource=Resource.create({"service.name": settings.service_name})
        )
        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(endpoint=f"{settings.otel_exporter_otlp_endpoint}/v1/traces")
            )
        )
        trace.set_tracer_provider(provider)
        HTTPXClientInstrumentor().instrument()
    if settings.traces_enabled and not _pg_processor_added:
        provider.add_span_processor(PostgresSpanProcessor())
        _pg_processor_added = True
    return provider


def tracer() -> trace.Tracer:
    return trace.get_tracer("finops")
