"""position-server — read tools over the enterprise /positions and /borrow endpoints."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_servers.position.tools import get_borrow_availability, get_position

mcp = FastMCP("position")

for _fn in (get_position, get_borrow_availability):
    mcp.tool()(_fn)
