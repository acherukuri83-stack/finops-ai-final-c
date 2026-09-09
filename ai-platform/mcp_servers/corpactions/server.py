"""corpactions-server (Phase F) — reads over the simulated corporate-actions book plus
three approval-gated writes. In-process, fixture-backed."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_servers.corpactions.tools import (
    escalate_ca,
    get_ca_event,
    get_election,
    get_entitlement,
    list_ca_events,
    raise_claim,
    submit_election,
)

mcp = FastMCP("corpactions")

for _fn in (
    get_ca_event,
    list_ca_events,
    get_entitlement,
    get_election,
    submit_election,
    raise_claim,
    escalate_ca,
):
    mcp.tool()(_fn)
