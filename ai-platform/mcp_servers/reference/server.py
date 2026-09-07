"""reference-server — read tools over the enterprise /securities and /calendar endpoints."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_servers.reference.tools import get_market_calendar, get_security

mcp = FastMCP("reference")

for _fn in (get_security, get_market_calendar):
    mcp.tool()(_fn)
