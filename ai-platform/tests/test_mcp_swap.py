"""W1 PR3 swap test: the trade tools run identically against an in-memory fake
enterprise, proving the client is a seam and tool code never touches transport.
"""

from __future__ import annotations

from mcp_servers._fake_enterprise import FakeEnterpriseClient
from mcp_servers.hub import open_session


async def test_trade_tools_against_fake_backend(fake_enterprise: FakeEnterpriseClient) -> None:
    async with open_session() as tools:
        trade = await tools.call("trade", "get_trade", trade_id="T100245")
        assert trade["status"] == "FAILED"
        assert trade["cpty_id"] == "CP-017"
        assert set(trade) >= {"trade_id", "client_id", "account_id", "security_id", "qty", "side"}

        settlement = await tools.call("trade", "get_settlement_status", trade_id="T100245")
        assert settlement["failure_code"] == "COUNTERPARTY_SSI_MISMATCH"
        assert settlement["attempts"]

        related = await tools.call("trade", "find_trades", account_id="ACC-88213")
        assert [t["trade_id"] for t in related] == ["T100245"]

    # every hop went through the injected fake, not httpx
    assert any(path == "/trades/T100245" for path, _ in fake_enterprise.calls)
