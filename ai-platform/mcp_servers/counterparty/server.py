"""counterparty-server — read tools over the enterprise /counterparties endpoints."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_servers.counterparty.tools import get_affirmation, get_counterparty, get_counterparty_ssi

mcp = FastMCP("counterparty")

for _fn in (get_counterparty, get_counterparty_ssi, get_affirmation):
    mcp.tool()(_fn)
