"""trade-server read tools. Docstrings are the exposed descriptions (docs/tool-contracts.md)."""

from __future__ import annotations

from typing import Any

from mcp_servers._common import shape, shape_list
from mcp_servers.trade.client import get_enterprise_client, guard
from mcp_servers.trade.models import SettlementStatus, Trade


@guard
async def get_trade(trade_id: str) -> dict[str, Any]:
    """Full trade record: client, account, security, qty, side, dates, status, counterparty. Use first for any trade question."""
    data = await get_enterprise_client().get_json("get_trade", f"/trades/{trade_id}")
    return shape(Trade, data)


@guard
async def get_settlement_status(trade_id: str) -> dict[str, Any]:
    """Settlement state, failure_code, failure_detail, attempts[] with timestamps. Use to learn *why* a trade is not settled. Returns failure_code=null if never attempted."""
    data = await get_enterprise_client().get_json(
        "get_settlement_status", f"/trades/{trade_id}/settlement"
    )
    return shape(SettlementStatus, data)


@guard
async def find_trades(
    client_id: str | None = None,
    account_id: str | None = None,
    status: str | None = None,
    security_id: str | None = None,
    trade_date: str | None = None,
    settle_date: str | None = None,
) -> Any:
    """Search trades by filters. Use to find related trades (same client, same security, same day) e.g. for duplicates or blast radius. Do not use to fetch a known trade_id — use get_trade."""
    data = await get_enterprise_client().get_json(
        "find_trades",
        "/trades",
        {
            "client": client_id,
            "account": account_id,
            "status": status,
            "security": security_id,
            "tradeDate": trade_date,
            "settleDate": settle_date,
        },
    )
    return shape_list(Trade, data)
