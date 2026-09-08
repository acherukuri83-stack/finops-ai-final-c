"""Per-run metrics for the eval harness.

Two sources, because they observe different things:

- `CountingModelClient` wraps the real `ModelClient` and sums every call's token usage —
  including the structured-output retries whose `ModelResponse` never reaches a span.
- `span_sink()` installs an in-memory OTel exporter and counts `tool` / `retrieval`
  spans — the only place a tool call is observable from outside the loop. It exercises
  the same span path `docs/standards/observability.md` mandates.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from agent_core.reasoning.model_client import ModelClient, ModelResponse

_exporter = InMemorySpanExporter()
_installed = False


def install_span_sink() -> None:
    """Route the `finops` tracer into an in-memory exporter. Call once, before any run;
    a no-op if a provider is already set (the CLI owns tracing in this process).
    """
    global _installed
    if _installed:
        return
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(_exporter))
    trace.set_tracer_provider(provider)
    _installed = True


@dataclass
class RunMetrics:
    tool_calls: int = 0
    model_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cache_read: int = 0


class _Sink:
    def read(self, counter: CountingModelClient) -> RunMetrics:
        m = RunMetrics(
            model_calls=counter.calls,
            tokens_in=counter.tokens_in,
            tokens_out=counter.tokens_out,
            cache_read=counter.cache_read,
        )
        for s in _exporter.get_finished_spans():
            if (s.attributes or {}).get("finops.span.type") in ("tool", "retrieval"):
                m.tool_calls += 1
        return m


@contextmanager
def span_sink() -> Any:
    """Clear the exporter, yield a sink that reads span counts for the enclosed run."""
    _exporter.clear()
    yield _Sink()


class CountingModelClient:
    """Delegates to a real `ModelClient`, accumulating token usage across every call."""

    def __init__(self, inner: ModelClient) -> None:
        self._inner = inner
        self.calls = 0
        self.tokens_in = 0
        self.tokens_out = 0
        self.cache_read = 0

    def reset(self) -> None:
        self.calls = self.tokens_in = self.tokens_out = self.cache_read = 0

    async def complete(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 2048,
    ) -> ModelResponse:
        resp = await self._inner.complete(
            model=model, system=system, messages=messages, tools=tools, max_tokens=max_tokens
        )
        self.calls += 1
        self.tokens_in += resp.input_tokens
        self.tokens_out += resp.output_tokens
        self.cache_read += resp.cache_read_tokens
        return resp
