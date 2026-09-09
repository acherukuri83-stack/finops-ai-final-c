"""wire-server (Phase B — Wires, optional module) — reads over a simulated outgoing-wire
book plus four approval-gated writes. In-process, fixture-backed. No `release_wire`."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_servers.wire.tools import (
    add_standing_instruction,
    get_approval_queue,
    get_available_balance,
    get_cutoff,
    get_standing_instructions,
    get_wire,
    get_wire_audit_trail,
    get_wire_screening,
    list_wires,
    open_compliance_referral,
    reschedule_value_date,
    route_to_reviewer,
)

mcp = FastMCP("wire")

for _fn in (
    get_wire,
    list_wires,
    get_wire_audit_trail,
    get_standing_instructions,
    get_approval_queue,
    get_cutoff,
    get_wire_screening,
    get_available_balance,
    route_to_reviewer,
    add_standing_instruction,
    reschedule_value_date,
    open_compliance_referral,
):
    mcp.tool()(_fn)
