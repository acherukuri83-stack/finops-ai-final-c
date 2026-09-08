"""The one path from MCP tools to the Java enterprise tier.

`httpx` with the W3C ``traceparent`` propagated (``HTTPXClientInstrumentor``, wired in
``platform_api.telemetry``). A 5xx or transport error gets exactly one retry inside the
call, then a *retryable* ``ErrorEnvelope``; a 4xx becomes a non-retryable envelope. Tools
never see an exception — ``@guard`` turns ``EnterpriseError`` into the envelope payload.

``FakeEnterpriseClient`` serves planted values in-process for the swap test and fast local
dev; select it with ``ENTERPRISE_FAKE=1``.
"""

from __future__ import annotations

import functools
import os
from collections.abc import Awaitable, Callable
from typing import Any, Protocol, cast

import httpx

from mcp_servers.errors import ErrorEnvelope, from_http, unavailable
from platform_api.settings import settings

_RETRYABLE_EXC = (httpx.TransportError,)


class EnterpriseError(Exception):
    """Internal control-flow: carries the ``ErrorEnvelope`` dict out to ``@guard``."""

    def __init__(self, envelope: dict[str, Any]) -> None:
        self.envelope = envelope
        super().__init__(str(envelope.get("message", "")))


class EnterpriseClient(Protocol):
    async def get_json(self, tool: str, path: str, params: dict[str, Any] | None = None) -> Any: ...
    async def post_json(self, tool: str, path: str, body: dict[str, Any] | None = None) -> Any: ...
    async def put_json(self, tool: str, path: str, body: dict[str, Any] | None = None) -> Any: ...


class HttpEnterpriseClient:
    """Shared async client. One instance per process (see ``get_enterprise_client``)."""

    def __init__(self, base_url: str, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        # 20s, not 10 — a cold 512 MB JVM behind Railway's private network can take
        # >10s on the first hit to a list endpoint. The loop already tolerates a slow
        # tool; this just stops spurious ReadTimeouts on a fresh deploy.
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"), timeout=20.0, transport=transport
        )

    async def get_json(self, tool: str, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self._request(tool, "GET", path, params=params)

    async def post_json(self, tool: str, path: str, body: dict[str, Any] | None = None) -> Any:
        return await self._request(tool, "POST", path, body=body)

    async def put_json(self, tool: str, path: str, body: dict[str, Any] | None = None) -> Any:
        return await self._request(tool, "PUT", path, body=body)

    async def _request(
        self,
        tool: str,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Any:
        clean = {k: v for k, v in (params or {}).items() if v is not None}
        last_exc: Exception | None = None
        for attempt in (0, 1):
            try:
                resp = await self._client.request(method, path, params=clean, json=body)
            except _RETRYABLE_EXC as exc:
                last_exc = exc
                continue
            if resp.status_code >= 500 and attempt == 0:
                continue
            if resp.status_code >= 400:
                raise EnterpriseError(from_http(tool, resp.status_code, _snippet(resp)))
            return resp.json() if resp.content else None
        raise EnterpriseError(
            unavailable(
                tool, f"{type(last_exc).__name__}: {last_exc}" if last_exc else "no response"
            )
        )

    async def aclose(self) -> None:
        await self._client.aclose()


def _snippet(resp: httpx.Response) -> str:
    try:
        return resp.text[:500]
    except Exception:  # noqa: BLE001 - body may be unreadable; the status is what matters
        return ""


# --- selection ---------------------------------------------------------------

_client: EnterpriseClient | None = None


def get_enterprise_client() -> EnterpriseClient:
    global _client
    if _client is None:
        if os.environ.get("ENTERPRISE_FAKE") == "1":
            from mcp_servers._fake_enterprise import FakeEnterpriseClient

            _client = FakeEnterpriseClient()
        else:
            _client = HttpEnterpriseClient(settings.enterprise_base_url)
    return _client


def set_enterprise_client(client: EnterpriseClient | None) -> None:
    """Tests only: install a stub/fake, or reset with ``None``."""
    global _client
    _client = client


# --- the tool guard --------------------------------------------------------------

type ToolFn = Callable[..., Awaitable[Any]]


def guard(fn: ToolFn) -> ToolFn:
    """Wrap a tool so it never raises into the loop: an ``EnterpriseError`` becomes its
    ``ErrorEnvelope`` payload, and anything else (a malformed upstream body, a schema
    mismatch) becomes a non-retryable ``TOOL_FAILED`` envelope.
    """

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await fn(*args, **kwargs)
        except EnterpriseError as exc:
            return exc.envelope
        except Exception as exc:  # noqa: BLE001 - a tool must never raise into the loop
            return ErrorEnvelope(
                code="TOOL_FAILED",
                message=f"{type(exc).__name__}: {exc}"[:400],
                retryable=False,
                tool=getattr(fn, "__name__", "tool"),
            ).as_dict

    return cast("ToolFn", wrapper)
