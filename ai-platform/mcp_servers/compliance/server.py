"""compliance-server — read tools over the enterprise /restrictions and /screening endpoints."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_servers.compliance.tools import get_restrictions, get_screening_result

mcp = FastMCP("compliance")

for _fn in (get_restrictions, get_screening_result):
    mcp.tool()(_fn)
