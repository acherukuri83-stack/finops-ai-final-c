"""OpenTelemetry bootstrap. One trace id flows React → FastAPI → httpx → Spring Boot.

Span attribute names follow docs/standards/observability.md.
"""

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from platform_api.settings import settings


def init_tracing() -> None:
    provider = TracerProvider(resource=Resource.create({"service.name": settings.service_name}))
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(endpoint=f"{settings.otel_exporter_otlp_endpoint}/v1/traces")
        )
    )
    trace.set_tracer_provider(provider)
    HTTPXClientInstrumentor().instrument()


def tracer() -> trace.Tracer:
    return trace.get_tracer("finops")
