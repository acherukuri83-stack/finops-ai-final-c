"""Phase F — the Cash specialist.

FakeModelClient + the in-process `cash` fixture store. Covers: a shortfall with the
cutoff still open → `arrange_funding`; a shortfall past the currency funding cutoff →
`escalate_cash` (hard rule in code); the allowlist; the write tools honour the approval
gate.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest

from agent_core import policy
from agent_core.agents import CASH, spec_for
from agent_core.cash import investigate_cash_break
from agent_core.reasoning.model_client import FakeModelClient, ModelResponse
from agent_core.schemas.finding import Outcome
from mcp_servers._fake_enterprise import FakeEnterpriseClient
from mcp_servers.cash import store as cs_store
from mcp_servers.cash.tools import arrange_funding
from platform_api import cases


@pytest.fixture(autouse=True)
def _reset_cash() -> Iterator[None]:
    cs_store.reset()
    yield
    cs_store.reset()


def _plan(*steps: tuple[str, str, dict[str, str]]) -> str:
    return json.dumps(
        {
            "assumptions": [],
            "steps": [{"server": s, "tool": t, "args": a, "why": "x"} for s, t, a in steps],
        }
    )


def _cash_finding(*, break_id: str, root_cause: str, action: str) -> str:
    return json.dumps(
        {
            "subject": {"type": "cash_break", "id": break_id},
            "outcome": "RESOLVED_CAUSE",
            "root_cause": root_cause,
            "evidence": [
                {"kind": "tool", "ref": "get_cash_break", "cited": True},
                {"kind": "tool", "ref": "get_facility", "cited": True},
            ],
            "proposed_actions": [
                {
                    "action_type": action,
                    "params": {"break_id": break_id, "source": "facility", "amount": "7500000"},
                    "rationale": "cover the shortfall plus buffer",
                    "impact": [],
                }
            ],
            "rejected_alternatives": [],
            "confidence_basis": "the break, the ladder, and the facility headroom",
        }
    )


_STEPS = _plan(
    ("cash", "get_cash_break", {"break_id": "CB-8001"}),
    ("cash", "get_funding_ladder", {"account_id": "ACC-88213", "currency": "USD"}),
    ("cash", "get_facility", {"account_id": "ACC-88213", "currency": "USD"}),
)


def test_cash_spec_and_allowlist() -> None:
    assert CASH.allowlist_key == "cash"
    assert {"cash", "market"} <= CASH.tool_servers
    assert CASH.subject_type == "cash_break"
    assert spec_for("cash") is CASH
    assert policy.allowed("cash", "arrange_funding") is True
    assert policy.allowed("cash", "escalate_cash") is True
    assert policy.allowed("cash", "update_ssi") is False


async def test_open_cutoff_proposes_arrange_funding(fake_enterprise: FakeEnterpriseClient) -> None:
    fake = FakeModelClient(
        [
            ModelResponse(text=_STEPS),
            ModelResponse(text=_plan()),
            ModelResponse(
                text=_cash_finding(
                    break_id="CB-8001", root_cause="INTRADAY_SHORTFALL", action="arrange_funding"
                )
            ),
        ]
    )
    finding = await investigate_cash_break("CB-8001", request="fund it?", client=fake)

    assert finding.outcome is Outcome.RESOLVED_CAUSE
    assert finding.root_cause == "INTRADAY_SHORTFALL"
    assert [a.action_type for a in finding.proposed_actions] == ["arrange_funding"]
    assert finding.proposed_actions[0].proposed_by == "cash"


async def test_missed_cutoff_converts_to_escalate_in_code(
    fake_enterprise: FakeEnterpriseClient,
) -> None:
    fake = FakeModelClient(
        [
            ModelResponse(text=_plan(("cash", "get_cash_break", {"break_id": "CB-8002"}))),
            ModelResponse(text=_plan()),
            ModelResponse(
                text=_cash_finding(
                    break_id="CB-8002", root_cause="INTRADAY_SHORTFALL", action="arrange_funding"
                )
            ),
        ]
    )
    finding = await investigate_cash_break("CB-8002", request="fund it?", client=fake)

    assert [a.action_type for a in finding.proposed_actions] == ["escalate_cash"]
    assert finding.root_cause == "FUNDING_CUTOFF_MISSED"
    assert any("escalate_cash in code" in q for q in finding.open_questions)


async def test_funding_write_refuses_a_forged_approval(
    fake_enterprise: FakeEnterpriseClient,
) -> None:
    result = await arrange_funding("CB-8001", "facility", "7500000", approval_id="ap_forgedCS")
    assert result["code"] == "ApprovalError"
    assert cs_store.actions() == []


async def test_approved_funding_records_and_audits(fake_enterprise: FakeEnterpriseClient) -> None:
    case = cases.create_case("cash_break", "CB-8001", "cash break")
    approval = cases.propose_action(
        case["case_id"],
        "arrange_funding",
        {"break_id": "CB-8001"},
        "fund",
        [{"type": "cash_break", "id": "CB-8001"}],
        True,
    )
    cases.decide(approval["approval_id"], "APPROVED", "t.desk", "OPS_ANALYST")
    row = await arrange_funding(
        "CB-8001", "facility", "7500000", approval_id=approval["approval_id"]
    )
    assert row["kind"] == "arrange_funding"
    assert len(cs_store.actions()) == 1
    audit = cases.get_case(case["case_id"])["audit"]
    assert any("arranged 7500000 funding" in e["event"] for e in audit)
