"""The planner's structured output parses into a Plan."""

from __future__ import annotations

from agent_core.reasoning.model_client import FakeModelClient, ModelResponse, complete_structured
from agent_core.schemas.plan import Plan

_PLAN_JSON = """
{"assumptions": ["the failure is a live SSI mismatch"],
 "steps": [
   {"server": "trade", "tool": "get_trade",
    "args": {"trade_id": "T100245"}, "why": "the trade"},
   {"server": "trade", "tool": "get_settlement_status",
    "args": {"trade_id": "T100245"}, "why": "failure code"}
 ]}
"""


async def test_plan_parses() -> None:
    fake = FakeModelClient([ModelResponse(text=_PLAN_JSON)])
    plan = await complete_structured(
        fake, model="x", system="s", messages=[{"role": "user", "content": "go"}], schema=Plan
    )
    assert plan.assumptions == ["the failure is a live SSI mismatch"]
    assert [(s.server, s.tool) for s in plan.steps] == [
        ("trade", "get_trade"),
        ("trade", "get_settlement_status"),
    ]
    assert plan.steps[0].args == {"trade_id": "T100245"}


async def test_empty_plan_is_valid() -> None:
    fake = FakeModelClient([ModelResponse(text='{"assumptions": [], "steps": []}')])
    plan = await complete_structured(
        fake, model="x", system="s", messages=[{"role": "user", "content": "go"}], schema=Plan
    )
    assert plan.steps == []
