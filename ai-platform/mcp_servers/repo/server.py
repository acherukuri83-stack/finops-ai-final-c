"""repo-server (Phase E — review mode) — reads over a simulated code host + draft-PR and
review writes. In-process, fixture-backed."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_servers.repo.tools import (
    get_diff,
    get_pull_request,
    open_pull_request,
    post_review,
)

mcp = FastMCP("repo")

for _fn in (get_pull_request, get_diff, open_pull_request, post_review):
    mcp.tool()(_fn)
