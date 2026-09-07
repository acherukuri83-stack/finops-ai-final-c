"""Span helpers. Every agent step, tool call, and retrieval is a span with the typed
`finops.*` attributes from docs/standards/observability.md. Emitted from the first line
of the loop.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from opentelemetry.trace import Span

from platform_api.telemetry import tracer

_PRIMITIVE = (str, bool, int, float)


@contextmanager
def span(name: str, span_type: str, **attrs: Any) -> Iterator[Span]:
    """Open a span tagged `finops.span.type=<span_type>`; extra kwargs become
    `finops.<key>` attributes (nested dicts/lists are JSON-encoded, None is dropped).
    """
    with tracer().start_as_current_span(name) as current:
        set_attrs(current, {"span.type": span_type, **attrs})
        yield current


def set_attrs(current: Span, attrs: dict[str, Any]) -> None:
    for key, value in attrs.items():
        if value is None:
            continue
        current.set_attribute(
            f"finops.{key}", value if isinstance(value, _PRIMITIVE) else json.dumps(value)
        )
