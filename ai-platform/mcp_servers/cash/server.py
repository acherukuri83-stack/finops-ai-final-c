"""cash-server (Phase F) — reads over the simulated cash & funding book plus three
approval-gated writes. In-process, fixture-backed."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_servers.cash.tools import (
    arrange_funding,
    escalate_cash,
    get_cash_break,
    get_facility,
    get_funding_ladder,
    list_cash_breaks,
    move_cash,
)

mcp = FastMCP("cash")

for _fn in (
    get_cash_break,
    list_cash_breaks,
    get_funding_ladder,
    get_facility,
    arrange_funding,
    move_cash,
    escalate_cash,
):
    mcp.tool()(_fn)
