"""Phase F — the Margin specialist.

FakeModelClient + the in-process `margin` fixture store. Covers: a price-move shortfall
inside the window → `post_collateral`; a call past its `due_by` → `escalate_margin` (hard
rule in code); the allowlist; the write tools honour the approval gate.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest

from agent_core import policy
from agent_core.agents import MARGIN, spec_for
from agent_core.margin import investigate_margin_call
from agent_core.reasoning.model_client import FakeModelClient, ModelResponse
from agent_core.schemas.finding import Outcome
from mcp_servers._fake_enterprise import FakeEnterpriseClient
from mcp_servers.margin import store as mg_store
from mcp_servers.margin.tools import post_collateral
from platform_api import cases


@pytest.fixture(autouse=True)
def _reset_margin() -> Iterator[None]:
    mg_store.reset()
    yield
    mg_store.reset()


def _plan(*steps: tuple[str, str, dict[str, str]]) -> str:
    return json.dumps(
        {
            "assumptions": [],
            "steps": [{"server": s, "tool": t, "args": a, "why": "x"} for s, t, a in steps],
        }
    )


def _margin_finding(*, call_id: str, root_cause: str, action: str) -> str:
    return json.dumps(
        {
            "subject": {"type": "margin_call", "id": call_id},
            "outcome": "RESOLVED_CAUSE",
            "root_cause": root_cause,
            "evidence": [
                {"kind": "tool", "ref": "get_margin_call", "cited": True},
                {"kind": "tool", "ref": "get_margin_status", "cited": True},
            ],
            "proposed_actions": [
                {
                    "action_type": action,
                    "params": {"call_id": call_id, "security_id": "AAPL", "amount": "4200000"},
                    "rationale": "cover the shortfall",
                    "impact": [],
                }
            ],
            "rejected_alternatives": [
                {
                    "action_type": "escalate_margin",
                    "reason": "call can still be met",
                    "evidence": [],
                }
            ],
            "confidence_basis": "the call, the shortfall, and the collateral",
        }
    )


_STEPS = _plan(
    ("margin", "get_margin_call", {"call_id": "MC-9001"}),
    ("margin", "get_margin_status", {"account_id": "ACC-88213"}),
    ("margin", "get_collateral", {"account_id": "ACC-88213"}),
)


def test_margin_spec_and_allowlist() -> None:
    assert MARGIN.allowlist_key == "margin"
    assert {"margin", "market"} <= MARGIN.tool_servers
    assert MARGIN.subject_type == "margin_call"
    assert spec_for("margin") is MARGIN
    assert policy.allowed("margin", "post_collateral") is True
    assert policy.allowed("margin", "escalate_margin") is True
    assert policy.allowed("margin", "update_ssi") is False


async def test_open_window_proposes_post_collateral(fake_enterprise: FakeEnterpriseClient) -> None:
    fake = FakeModelClient(
        [
            ModelResponse(text=_STEPS),
            ModelResponse(text=_plan()),
            ModelResponse(
                text=_margin_finding(
                    call_id="MC-9001", root_cause="PRICE_MOVE_SHORTFALL", action="post_collateral"
                )
            ),
        ]
    )
    finding = await investigate_margin_call("MC-9001", request="what's the shortfall?", client=fake)

    assert finding.outcome is Outcome.RESOLVED_CAUSE
    assert finding.root_cause == "PRICE_MOVE_SHORTFALL"
    assert [a.action_type for a in finding.proposed_actions] == ["post_collateral"]
    assert finding.proposed_actions[0].proposed_by == "margin"


async def test_missed_window_converts_to_escalate_in_code(
    fake_enterprise: FakeEnterpriseClient,
) -> None:
    fake = FakeModelClient(
        [
            ModelResponse(text=_plan(("margin", "get_margin_call", {"call_id": "MC-9002"}))),
            ModelResponse(text=_plan()),
            ModelResponse(
                text=_margin_finding(
                    call_id="MC-9002", root_cause="PRICE_MOVE_SHORTFALL", action="post_collateral"
                )
            ),
        ]
    )
    finding = await investigate_margin_call("MC-9002", request="meet it?", client=fake)

    assert [a.action_type for a in finding.proposed_actions] == ["escalate_margin"]
    assert finding.root_cause == "CALL_WINDOW_MISSED"
    assert any("escalate_margin in code" in q for q in finding.open_questions)


async def test_post_collateral_refuses_a_forged_approval(
    fake_enterprise: FakeEnterpriseClient,
) -> None:
    result = await post_collateral("MC-9001", "AAPL", "4200000", approval_id="ap_forgedM")
    assert result["code"] == "ApprovalError"
    assert mg_store.actions() == []


async def test_approved_post_collateral_records_and_audits(
    fake_enterprise: FakeEnterpriseClient,
) -> None:
    case = cases.create_case("margin_call", "MC-9001", "margin call")
    approval = cases.propose_action(
        case["case_id"],
        "post_collateral",
        {"call_id": "MC-9001"},
        "cover",
        [{"type": "margin_call", "id": "MC-9001"}],
        True,
    )
    cases.decide(approval["approval_id"], "APPROVED", "m.desk", "OPS_ANALYST")
    row = await post_collateral("MC-9001", "AAPL", "4200000", approval_id=approval["approval_id"])
    assert row["kind"] == "post_collateral"
    assert len(mg_store.actions()) == 1
    audit = cases.get_case(case["case_id"])["audit"]
    assert any("posted 4200000 AAPL" in e["event"] for e in audit)
