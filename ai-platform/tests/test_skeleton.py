"""The walking skeleton: one MCP tool call in, a minimal Finding out."""

from __future__ import annotations

from agent_core.schemas.finding import Outcome
from agent_core.skeleton import investigate
from mcp_servers._fake_enterprise import FakeEnterpriseClient


async def test_skeleton_returns_minimal_finding(fake_enterprise: FakeEnterpriseClient) -> None:
    finding = await investigate("T100245")
    assert finding.outcome is Outcome.SKELETON
    assert finding.subject.type == "trade"
    assert finding.subject.id == "T100245"
    assert [e.ref for e in finding.evidence] == ["trade.get_trade"]
    assert isinstance(finding.trace_id, str)


async def test_skeleton_degrades_when_the_tool_fails(fake_enterprise: FakeEnterpriseClient) -> None:
    finding = await investigate("T999999")  # no route in the fake -> NOT_FOUND envelope
    assert finding.outcome is Outcome.TOOL_DEGRADED
    assert finding.degraded_tools == ["trade.get_trade"]
