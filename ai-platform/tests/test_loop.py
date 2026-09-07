"""The Investigator loop: plan -> tool loop (budget, re-plan) -> synthesize -> Finding.

Uses FakeModelClient (queued Plan then Finding JSON) and the in-process fake enterprise —
no network, no DB. Plans only touch tools the fake serves (no ops.search_knowledge here).
"""

from __future__ import annotations

import json

from agent_core.loop import _BUDGET, investigate
from agent_core.reasoning.model_client import FakeModelClient, ModelResponse
from agent_core.schemas.finding import Outcome
from mcp_servers._fake_enterprise import FakeEnterpriseClient


def _plan(*steps: tuple[str, str, dict[str, str]], assumptions: list[str] | None = None) -> str:
    return json.dumps(
        {
            "assumptions": assumptions or [],
            "steps": [{"server": s, "tool": t, "args": a, "why": "x"} for s, t, a in steps],
        }
    )


_FINDING = json.dumps(
    {
        "subject": {"type": "trade", "id": "T100245"},
        "outcome": "RESOLVED_CAUSE",
        "root_cause": "COUNTERPARTY_INSTRUCTION_STALE",
        "evidence": [{"kind": "tool", "ref": "get_ssi_history", "cited": True}],
        "proposed_actions": [
            {"action_type": "resubmit_settlement", "rationale": "cpty re-affirms", "impact": []}
        ],
        "rejected_alternatives": [
            {"action_type": "update_ssi", "reason": "our SSI is current", "evidence": []}
        ],
        "confidence_basis": "SSI history plus the affirmation",
    }
)


async def test_loop_runs_steps_then_synthesizes(fake_enterprise: FakeEnterpriseClient) -> None:
    fake = FakeModelClient(
        [
            ModelResponse(
                text=_plan(
                    ("trade", "get_trade", {"trade_id": "T100245"}),
                    ("trade", "get_settlement_status", {"trade_id": "T100245"}),
                )
            ),
            ModelResponse(text=_plan()),  # nothing more to do
            ModelResponse(text=_FINDING),
        ]
    )
    finding = await investigate("T100245", client=fake)

    assert finding.outcome is Outcome.RESOLVED_CAUSE
    assert finding.root_cause == "COUNTERPARTY_INSTRUCTION_STALE"
    assert "update_ssi" in [r.action_type for r in finding.rejected_alternatives]
    assert finding.trace_id
    # turn 0 plan, turn 1 replan (saw observations), synthesize
    assert len(fake.calls) == 3
    assert "Observations so far" in fake.calls[1]["messages"][-1]["content"]


async def test_loop_stops_at_budget(fake_enterprise: FakeEnterpriseClient) -> None:
    over_budget = _plan(*[("trade", "get_trade", {"trade_id": "T100245"})] * (_BUDGET + 5))
    fake = FakeModelClient([ModelResponse(text=over_budget), ModelResponse(text=_FINDING)])
    finding = await investigate("T100245", client=fake)
    assert finding.trace_id
    # planned once, hit the budget, went straight to synthesis — no second plan
    assert len(fake.calls) == 2


async def test_loop_degrades_when_required_tool_errors(
    fake_enterprise: FakeEnterpriseClient,
) -> None:
    fake_enterprise.fail_with = 503
    fake = FakeModelClient(
        [
            ModelResponse(text=_plan(("trade", "get_settlement_status", {"trade_id": "T100245"}))),
            ModelResponse(text=_plan()),
            ModelResponse(text=_FINDING),
        ]
    )
    finding = await investigate("T100245", client=fake)
    assert finding.outcome is Outcome.TOOL_DEGRADED
    assert finding.degraded_tools == ["trade.get_settlement_status"]
