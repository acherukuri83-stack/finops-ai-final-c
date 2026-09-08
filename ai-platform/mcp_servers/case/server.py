"""case-server — cases, approvals, audit. Backed by platform_api.cases (same process)."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_servers.case.tools import (
    create_case,
    get_approval,
    log_audit,
    propose_action,
    update_case,
)

mcp = FastMCP("case")

for _fn in (create_case, update_case, propose_action, get_approval, log_audit):
    mcp.tool()(_fn)
