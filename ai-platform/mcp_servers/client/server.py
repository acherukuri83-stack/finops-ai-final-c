"""client-server — read + write tools over the enterprise /clients and /accounts endpoints."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_servers.client.tools import (
    get_account,
    get_client,
    get_ssi,
    get_ssi_history,
    update_ssi,
)

mcp = FastMCP("client")

for _fn in (get_client, get_account, get_ssi, get_ssi_history, update_ssi):
    mcp.tool()(_fn)
