"""trade-server — read + write tools over the enterprise /trades endpoints."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_servers.trade.tools import (
    cancel_trade,
    find_trades,
    get_settlement_status,
    get_trade,
    resubmit_settlement,
)

mcp = FastMCP("trade")

for _fn in (get_trade, get_settlement_status, find_trades, resubmit_settlement, cancel_trade):
    mcp.tool()(_fn)
