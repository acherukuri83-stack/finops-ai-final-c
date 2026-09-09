"""margin-server (Phase F) — reads over the simulated margin book plus three
approval-gated writes. In-process, fixture-backed."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_servers.margin.tools import (
    escalate_margin,
    get_collateral,
    get_eligibility,
    get_margin_call,
    get_margin_status,
    list_margin_calls,
    post_collateral,
    substitute_collateral,
)

mcp = FastMCP("margin")

for _fn in (
    get_margin_call,
    list_margin_calls,
    get_margin_status,
    get_collateral,
    get_eligibility,
    post_collateral,
    substitute_collateral,
    escalate_margin,
):
    mcp.tool()(_fn)
