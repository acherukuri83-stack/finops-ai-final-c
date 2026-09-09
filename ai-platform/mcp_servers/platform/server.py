"""platform-server (Phase E) — reads over the simulated platform tier plus three
approval-gated writes (change ticket, rerun, replay). In-process, fixture-backed."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_servers.platform.tools import (
    diff_config,
    get_deployments,
    get_incident,
    get_job_runs,
    get_platform_logs,
    get_service_health,
    get_source,
    get_topic_lag,
    open_change_ticket,
    replay_message,
    rerun_job,
)

mcp = FastMCP("platform")

for _fn in (
    get_service_health,
    get_job_runs,
    get_deployments,
    diff_config,
    get_topic_lag,
    get_platform_logs,
    get_source,
    get_incident,
    open_change_ticket,
    rerun_job,
    replay_message,
):
    mcp.tool()(_fn)
