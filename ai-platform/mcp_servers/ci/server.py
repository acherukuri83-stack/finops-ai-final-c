"""ci-server (Phase E — review mode) — deterministic checks over a PR. Read-only,
in-process, fixture-backed."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_servers.ci.tools import (
    get_test_coverage,
    run_eval,
    run_security_scan,
    run_static_analysis,
    run_tests,
)

mcp = FastMCP("ci")

for _fn in (run_static_analysis, run_security_scan, get_test_coverage, run_tests, run_eval):
    mcp.tool()(_fn)
