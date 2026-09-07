"""Walking skeleton — the whole pipeline, none of the reasoning.

Given a trade id it calls exactly one tool (`trade.get_trade`) over MCP and returns a
minimal `Finding`. It proves portal -> platform-api -> MCP -> enterprise -> back with one
trace id. W2 replaces it with the real planner + tool loop + synthesis.
"""

from __future__ import annotations

from opentelemetry import trace

from agent_core.schemas.finding import EvidenceRef, Finding, Outcome, SubjectRef
from mcp_servers.errors import is_error
from mcp_servers.hub import open_session


async def investigate(trade_id: str) -> Finding:
    span = trace.get_current_span()
    trace_id = format(span.get_span_context().trace_id, "032x") if span else ""

    subject = SubjectRef(type="trade", id=trade_id)
    async with open_session() as tools:
        result = await tools.call("trade", "get_trade", trade_id=trade_id)

    if is_error(result):
        return Finding(
            subject=subject,
            outcome=Outcome.TOOL_DEGRADED,
            degraded_tools=["trade.get_trade"],
            confidence_basis=f"trade.get_trade returned {result.get('code')}",
            trace_id=trace_id,
        )

    return Finding(
        subject=subject,
        outcome=Outcome.SKELETON,
        evidence=[EvidenceRef(kind="tool", ref="trade.get_trade")],
        confidence_basis="walking skeleton — one tool call, no reasoning",
        trace_id=trace_id,
    )
