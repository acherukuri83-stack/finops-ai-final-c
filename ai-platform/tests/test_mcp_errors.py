"""Error mapping: 5xx retries once then a retryable envelope; 4xx does not retry.
Mirrors Scenario 12's TOOL_DEGRADED shape at the tool boundary.
"""

from __future__ import annotations

import httpx

from mcp_servers import _enterprise
from mcp_servers._enterprise import HttpEnterpriseClient
from mcp_servers.hub import open_session


def _counting_transport(status: int) -> tuple[httpx.MockTransport, list[int]]:
    hits: list[int] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        hits.append(1)
        return httpx.Response(status, text=f"boom {status}")

    return httpx.MockTransport(handler), hits


async def test_5xx_retries_once_then_retryable_envelope() -> None:
    transport, hits = _counting_transport(503)
    _enterprise.set_enterprise_client(
        HttpEnterpriseClient("http://enterprise.test", transport=transport)
    )
    try:
        async with open_session() as tools:
            result = await tools.call("trade", "get_trade", trade_id="T100245")
    finally:
        _enterprise.set_enterprise_client(None)

    assert sum(hits) == 2  # original + exactly one retry
    assert result["code"] == "UPSTREAM_503"
    assert result["retryable"] is True
    assert result["tool"] == "get_trade"


async def test_404_is_not_retryable_and_does_not_retry() -> None:
    transport, hits = _counting_transport(404)
    _enterprise.set_enterprise_client(
        HttpEnterpriseClient("http://enterprise.test", transport=transport)
    )
    try:
        async with open_session() as tools:
            result = await tools.call("client", "get_account", account_id="ACC-NOPE")
    finally:
        _enterprise.set_enterprise_client(None)

    assert sum(hits) == 1
    assert result["code"] == "NOT_FOUND"
    assert result["retryable"] is False


async def test_transport_error_retries_then_unavailable() -> None:
    hits: list[int] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        hits.append(1)
        raise httpx.ConnectError("refused")

    _enterprise.set_enterprise_client(
        HttpEnterpriseClient("http://enterprise.test", transport=httpx.MockTransport(handler))
    )
    try:
        async with open_session() as tools:
            result = await tools.call("ops", "search_logs", query="x")
    finally:
        _enterprise.set_enterprise_client(None)

    assert sum(hits) == 2
    assert result["code"] == "UPSTREAM_UNAVAILABLE"
    assert result["retryable"] is True


async def test_last_retries_reports_the_in_call_retry_count() -> None:
    calls: list[int] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(200 if len(calls) > 1 else 503, json={"ok": True})

    client = HttpEnterpriseClient("http://enterprise.test", transport=httpx.MockTransport(handler))
    await client.get_json("get_trade", "/trades/T1")
    assert _enterprise.last_retries() == 1  # one 503, one retry, then 200

    # a clean call resets it
    calls.clear()

    def ok(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    client2 = HttpEnterpriseClient("http://enterprise.test", transport=httpx.MockTransport(ok))
    await client2.get_json("get_trade", "/trades/T2")
    assert _enterprise.last_retries() == 0
