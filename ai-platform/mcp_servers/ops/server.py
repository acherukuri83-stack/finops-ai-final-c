"""ops-server — search_logs over the enterprise /logs endpoint, plus W2 stubs."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_servers.ops.tools import find_incidents, search_knowledge, search_logs

mcp = FastMCP("ops")

for _fn in (search_logs, search_knowledge, find_incidents):
    mcp.tool()(_fn)
