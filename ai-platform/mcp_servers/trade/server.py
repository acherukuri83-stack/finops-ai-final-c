"""trade-server — read tools over the enterprise /trades endpoints."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_servers.trade.tools import find_trades, get_settlement_status, get_trade

mcp = FastMCP("trade")

for _fn in (get_trade, get_settlement_status, find_trades):
    mcp.tool()(_fn)
