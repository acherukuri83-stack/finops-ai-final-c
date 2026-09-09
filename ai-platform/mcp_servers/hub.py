"""The MCP registry: the eight read servers, plus the two ways to reach them.

- ``open_session()`` — an in-memory MCP client over one combined server holding every
  tool. Used by the Investigator loop and the contract tests. No socket.
- ``mount_all(app)`` — SSE-mounts each server at ``/mcp/<name>`` on the platform-api
  ASGI app (skipped when ``AI_PLATFORM_SPLIT=1``), for MCP Inspector / external clients.
- ``describe()`` — the payload behind ``GET /connections``.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import TextContent

from mcp_servers.case.server import mcp as case_mcp
from mcp_servers.case.tools import create_case, get_approval, log_audit, propose_action, update_case
from mcp_servers.cash.server import mcp as cash_mcp
from mcp_servers.cash.tools import (
    arrange_funding,
    escalate_cash,
    get_cash_break,
    get_facility,
    get_funding_ladder,
    list_cash_breaks,
    move_cash,
)
from mcp_servers.ci.server import mcp as ci_mcp
from mcp_servers.ci.tools import (
    get_test_coverage,
    run_eval,
    run_security_scan,
    run_static_analysis,
    run_tests,
)
from mcp_servers.client.server import mcp as client_mcp
from mcp_servers.client.tools import (
    get_account,
    get_client,
    get_ssi,
    get_ssi_history,
    update_ssi,
)
from mcp_servers.compliance.server import mcp as compliance_mcp
from mcp_servers.compliance.tools import get_restrictions, get_screening_result
from mcp_servers.corpactions.server import mcp as corpactions_mcp
from mcp_servers.corpactions.tools import (
    escalate_ca,
    get_ca_event,
    get_election,
    get_entitlement,
    list_ca_events,
    raise_claim,
    submit_election,
)
from mcp_servers.counterparty.server import mcp as counterparty_mcp
from mcp_servers.counterparty.tools import (
    get_affirmation,
    get_counterparty,
    get_counterparty_ssi,
)
from mcp_servers.errors import is_error
from mcp_servers.margin.server import mcp as margin_mcp
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
from mcp_servers.market.server import mcp as market_mcp
from mcp_servers.market.tools import get_price
from mcp_servers.ops.server import mcp as ops_mcp
from mcp_servers.ops.tools import find_incidents, search_knowledge, search_logs
from mcp_servers.platform.server import mcp as platform_mcp
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
from mcp_servers.position.server import mcp as position_mcp
from mcp_servers.position.tools import get_borrow_availability, get_position
from mcp_servers.reference.server import mcp as reference_mcp
from mcp_servers.reference.tools import get_market_calendar, get_security
from mcp_servers.repo.server import mcp as repo_mcp
from mcp_servers.repo.tools import (
    get_diff,
    get_pull_request,
    open_pull_request,
    post_review,
)
from mcp_servers.stockloan.server import mcp as stockloan_mcp
from mcp_servers.stockloan.tools import (
    book_buy_in,
    get_lending_availability,
    get_loan,
    get_recall,
    get_rerate_history,
    initiate_recall,
    list_loans,
    rerate_loan,
)
from mcp_servers.trade.server import mcp as trade_mcp
from mcp_servers.trade.tools import (
    cancel_trade,
    find_trades,
    get_settlement_status,
    get_trade,
    resubmit_settlement,
)
from mcp_servers.wire.server import mcp as wire_mcp
from mcp_servers.wire.tools import (
    add_standing_instruction,
    get_approval_queue,
    get_available_balance,
    get_cutoff,
    get_standing_instructions,
    get_wire,
    get_wire_audit_trail,
    get_wire_screening,
    open_compliance_referral,
    reschedule_value_date,
    route_to_reviewer,
)
from platform_api.settings import settings

_ToolFn = Callable[..., Awaitable[Any]]

# access tier per tool (docs/tool-contracts.md). `write` needs an APPROVED approval_id in
# the tool; `write*` is agent-allowed bookkeeping (the `case` server).
WRITE_TOOLS = frozenset(
    {
        "resubmit_settlement",
        "cancel_trade",
        "update_ssi",
        "open_change_ticket",
        "rerun_job",
        "replay_message",
        "initiate_recall",
        "rerate_loan",
        "book_buy_in",
        "post_collateral",
        "substitute_collateral",
        "escalate_margin",
        "submit_election",
        "raise_claim",
        "escalate_ca",
        "arrange_funding",
        "move_cash",
        "escalate_cash",
        "open_pull_request",
        "post_review",
        "route_to_reviewer",
        "add_standing_instruction",
        "reschedule_value_date",
        "open_compliance_referral",
    }
)
GOV_TOOLS = frozenset({"create_case", "update_case", "propose_action", "log_audit"})


def tool_access(name: str) -> str:
    if name in WRITE_TOOLS:
        return "write"
    if name in GOV_TOOLS:
        return "write*"
    return "read"


@dataclass(frozen=True)
class ServerSpec:
    name: str
    mcp: FastMCP
    tools: list[_ToolFn] = field(default_factory=list)
    access: str = "read"


SERVERS: dict[str, ServerSpec] = {
    s.name: s
    for s in (
        ServerSpec(
            "trade",
            trade_mcp,
            [get_trade, get_settlement_status, find_trades, resubmit_settlement, cancel_trade],
            "read+write",
        ),
        ServerSpec(
            "client",
            client_mcp,
            [get_client, get_account, get_ssi, get_ssi_history, update_ssi],
            "read+write",
        ),
        ServerSpec(
            "counterparty",
            counterparty_mcp,
            [get_counterparty, get_counterparty_ssi, get_affirmation],
        ),
        ServerSpec("position", position_mcp, [get_position, get_borrow_availability]),
        ServerSpec("reference", reference_mcp, [get_security, get_market_calendar]),
        ServerSpec("market", market_mcp, [get_price]),
        ServerSpec("compliance", compliance_mcp, [get_restrictions, get_screening_result]),
        ServerSpec("ops", ops_mcp, [search_logs, search_knowledge, find_incidents]),
        ServerSpec(
            "platform",
            platform_mcp,
            [
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
            ],
            "read+write",
        ),
        ServerSpec(
            "stockloan",
            stockloan_mcp,
            [
                get_loan,
                list_loans,
                get_recall,
                get_rerate_history,
                get_lending_availability,
                initiate_recall,
                rerate_loan,
                book_buy_in,
            ],
            "read+write",
        ),
        ServerSpec(
            "repo",
            repo_mcp,
            [get_pull_request, get_diff, open_pull_request, post_review],
            "read+write",
        ),
        ServerSpec(
            "ci",
            ci_mcp,
            [run_static_analysis, run_security_scan, get_test_coverage, run_tests, run_eval],
        ),
        ServerSpec(
            "margin",
            margin_mcp,
            [
                get_margin_call,
                list_margin_calls,
                get_margin_status,
                get_collateral,
                get_eligibility,
                post_collateral,
                substitute_collateral,
                escalate_margin,
            ],
            "read+write",
        ),
        ServerSpec(
            "corpactions",
            corpactions_mcp,
            [
                get_ca_event,
                list_ca_events,
                get_entitlement,
                get_election,
                submit_election,
                raise_claim,
                escalate_ca,
            ],
            "read+write",
        ),
        ServerSpec(
            "cash",
            cash_mcp,
            [
                get_cash_break,
                list_cash_breaks,
                get_funding_ladder,
                get_facility,
                arrange_funding,
                move_cash,
                escalate_cash,
            ],
            "read+write",
        ),
        ServerSpec(
            "wire",
            wire_mcp,
            [
                get_wire,
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
            ],
            "read+write",
        ),
        ServerSpec(
            "case",
            case_mcp,
            [create_case, update_case, propose_action, get_approval, log_audit],
            "write*",
        ),
    )
}

# tool name -> owning server, for grouping a flat tool list back by server
TOOL_SERVER: dict[str, str] = {
    fn.__name__: spec.name for spec in SERVERS.values() for fn in spec.tools
}

# tools whose success shape is an array (docs/tool-contracts.md) — the rest return one object
LIST_TOOLS = frozenset(
    {
        "find_trades",
        "get_ssi_history",
        "get_restrictions",
        "search_logs",
        "search_knowledge",
        "find_incidents",
        "get_job_runs",
        "get_deployments",
        "diff_config",
        "get_platform_logs",
        "get_incident",
        "run_static_analysis",
        "run_security_scan",
        "list_loans",
        "get_rerate_history",
        "list_margin_calls",
        "get_collateral",
        "list_ca_events",
        "list_cash_breaks",
        "get_funding_ladder",
        "get_wire_audit_trail",
        "get_standing_instructions",
        "get_approval_queue",
    }
)


def _combined() -> FastMCP:
    """One FastMCP holding every tool — the in-process path. Tool names are unique."""
    hub = FastMCP("hub")
    for spec in SERVERS.values():
        for fn in spec.tools:
            hub.tool()(fn)
    return hub


class Tools:
    """A thin facade over the in-memory MCP client session. `servers` scopes what
    `list()` returns (Phase C specialists) — every tool is still callable."""

    def __init__(self, session: Any, servers: set[str] | None = None) -> None:
        self._session = session
        self._servers = servers

    async def list(self) -> list[dict[str, Any]]:
        listed = await self._session.list_tools()
        rows = [
            {
                "server": TOOL_SERVER.get(tool.name, "?"),
                "tool": tool.name,
                "access": tool_access(tool.name),
                "description": tool.description or "",
                "params": sorted((tool.inputSchema or {}).get("properties", {})),
            }
            for tool in listed.tools
        ]
        if self._servers is not None:
            rows = [r for r in rows if r["server"] in self._servers]
        return rows

    async def call(self, server: str, tool: str, **arguments: Any) -> Any:
        del server  # tool names are globally unique; kept for a readable call site
        result = await self._session.call_tool(tool, arguments)
        payload = _payload(result)
        if tool in LIST_TOOLS and isinstance(payload, dict) and not is_error(payload):
            payload = [payload]  # a one-element array comes back as a single block
        return payload


def _payload(result: Any) -> Any:
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict) and "result" in structured:
        return structured["result"]

    texts = [c.text for c in result.content if isinstance(c, TextContent)]
    if getattr(result, "isError", False):
        return _tool_error(" ".join(texts))

    blocks: list[Any] = []
    for text in texts:
        try:
            blocks.append(json.loads(text))
        except json.JSONDecodeError:
            return _tool_error(text)  # a tool returned non-JSON — treat as a failure, don't crash
    if len(blocks) == 1:
        return blocks[0]
    return blocks  # 0 -> [], 2+ -> the array


def _tool_error(message: str) -> dict[str, Any]:
    return {"code": "TOOL_ERROR", "message": message[:400], "retryable": False, "tool": "?"}


@asynccontextmanager
async def open_session(*, servers: set[str] | None = None) -> AsyncIterator[Tools]:
    async with create_connected_server_and_client_session(_combined()) as session:
        yield Tools(session, servers)


def mount_all(app: Any) -> None:
    """SSE-mount every server on the platform-api app unless running split."""
    if settings.ai_platform_split:
        return
    for name, spec in SERVERS.items():
        app.mount(f"/mcp/{name}", spec.mcp.sse_app())


async def describe() -> dict[str, Any]:
    """`GET /connections`: enterprise health plus every server's tools and access tier."""
    healthy = await _enterprise_healthy()
    servers: list[dict[str, Any]] = []
    for name, spec in SERVERS.items():
        listed = await spec.mcp.list_tools()
        servers.append(
            {
                "name": name,
                "access": spec.access,
                "healthy": healthy,
                "tools": [
                    {
                        "name": t.name,
                        "access": tool_access(t.name),
                        "description": t.description or "",
                    }
                    for t in listed
                ],
            }
        )
    return {
        "enterprise_base_url": settings.enterprise_base_url,
        "healthy": healthy,
        "servers": servers,
    }


async def _enterprise_healthy() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.enterprise_base_url.rstrip('/')}/health")
            return resp.status_code == 200
    except httpx.HTTPError:
        return False
