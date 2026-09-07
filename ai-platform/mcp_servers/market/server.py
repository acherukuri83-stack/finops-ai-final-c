"""market-server — read tools over the enterprise /prices endpoint."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_servers.market.tools import get_price

mcp = FastMCP("market")

mcp.tool()(get_price)
