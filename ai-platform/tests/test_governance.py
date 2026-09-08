"""Governance: the approval gate lives in the write tool, and the policy engine drops
actions an agent may not take. Contract test: the full propose -> approve -> execute ->
audit round-trip against the live enterprise.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from agent_core import policy
from agent_core.schemas.finding import Finding, Outcome, ProposedAction, SubjectRef
from mcp_servers._fake_enterprise import FakeEnterpriseClient
from mcp_servers.trade.tools import cancel_trade, resubmit_settlement
from platform_api import cases


def _pending_approval(action_type: str, subject_id: str) -> str:
    case = cases.create_case("trade", subject_id, "test")
    approval = cases.propose_action(
        case["case_id"],
        action_type,
        {"trade_id": subject_id},
        "because",
        [{"type": "trade", "id": subject_id}],
        True,
    )
    return str(approval["approval_id"])


async def test_write_tool_refuses_a_forged_approval_id(
    fake_enterprise: FakeEnterpriseClient,
) -> None:
    result = await cancel_trade("T100291", "dup", approval_id="ap_forged1")
    assert result["code"] == "ApprovalError"
    assert fake_enterprise.writes == []


async def test_write_tool_refuses_a_pending_approval(fake_enterprise: FakeEnterpriseClient) -> None:
    approval_id = _pending_approval("cancel_trade", "T100291")
    result = await cancel_trade("T100291", "dup", approval_id=approval_id)
    assert result["code"] == "ApprovalError"
    assert "PENDING" in result["message"]
    assert fake_enterprise.writes == []


async def test_write_tool_refuses_a_rejected_approval(
    fake_enterprise: FakeEnterpriseClient,
) -> None:
    approval_id = _pending_approval("resubmit_settlement", "T100291")
    cases.decide(approval_id, "REJECTED", "a.patel", "OPS_ANALYST")
    result = await resubmit_settlement("T100291", approval_id=approval_id)
    assert result["code"] == "ApprovalError"
    assert fake_enterprise.writes == []


async def test_write_tool_refuses_an_approval_for_a_different_action(
    fake_enterprise: FakeEnterpriseClient,
) -> None:
    approval_id = _pending_approval("cancel_trade", "T100291")
    cases.decide(approval_id, "APPROVED", "a.patel", "OPS_ANALYST")
    result = await resubmit_settlement("T100291", approval_id=approval_id)  # approval is for cancel
    assert result["code"] == "ApprovalError"
    assert fake_enterprise.writes == []


async def test_approved_write_executes_and_audits(fake_enterprise: FakeEnterpriseClient) -> None:
    approval_id = _pending_approval("cancel_trade", "T100291")
    approval = cases.decide(approval_id, "APPROVED", "a.patel", "OPS_ANALYST")
    result = await cancel_trade("T100291", "duplicate", approval_id=approval_id)
    assert result.get("ok") is True
    assert fake_enterprise.writes and fake_enterprise.writes[0][1] == "/trades/T100291/cancel"
    audit = cases.get_case(approval["case_id"])["audit"]
    assert any("executed cancel_trade T100291" in e["event"] for e in audit)


def test_policy_drops_an_action_not_on_the_allowlist() -> None:
    finding = Finding(
        subject=SubjectRef(type="trade", id="T1"),
        outcome=Outcome.RESOLVED_CAUSE,
        root_cause="X",
        proposed_actions=[
            ProposedAction(action_type="resubmit_settlement", rationale="ok"),
            ProposedAction(action_type="release_wire", rationale="not in scope"),
        ],
    )
    out = policy.apply(finding, "investigator")
    kept = {a.action_type for a in out.proposed_actions}
    assert kept == {"resubmit_settlement"}
    assert any("release_wire" in q for q in out.open_questions)


def test_update_ssi_is_allowed_for_the_investigator_in_phase_a() -> None:
    # Phase A: the guard against a wrong SSI overwrite is ADR-0002 (reasoning), not policy.
    # The per-agent `update_ssi` restriction arrives with the Risk/Client agent in Phase C.
    assert policy.allowed("investigator", "update_ssi") is True


# --- contract: the real round-trip -----------------------------------------------

pytest_contract = pytest.mark.contract


@pytest.fixture
def _sql_cases() -> Iterator[None]:
    if not os.environ.get("ENTERPRISE_BASE_URL"):
        pytest.skip("needs the running stack")
    from mcp_servers import _enterprise
    from mcp_servers._enterprise import HttpEnterpriseClient
    from platform_api import store

    store.ensure_schema()
    cases.set_backend(cases.SqlBackend())
    _enterprise.set_enterprise_client(HttpEnterpriseClient(os.environ["ENTERPRISE_BASE_URL"]))
    try:
        yield
    finally:
        cases.set_backend(None)
        _enterprise.set_enterprise_client(None)


@pytest_contract
async def test_round_trip_against_the_live_enterprise(_sql_cases: None) -> None:
    case = cases.create_case("trade", "T100291", "duplicate booking")
    approval = cases.propose_action(
        case["case_id"],
        "cancel_trade",
        {"trade_id": "T100291"},
        "cancel the later duplicate",
        [{"type": "trade", "id": "T100290"}, {"type": "trade", "id": "T100291"}],
        False,
    )
    approval_id = approval["approval_id"]

    # PENDING -> refused
    refused = await cancel_trade("T100291", "dup", approval_id=approval_id)
    assert refused["code"] == "ApprovalError"

    cases.decide(approval_id, "APPROVED", "a.patel", "OPS_ANALYST")
    done = await cancel_trade("T100291", "dup", approval_id=approval_id)
    assert not (isinstance(done, dict) and done.get("code"))

    audit = cases.get_case(case["case_id"])["audit"]
    assert any("APPROVED by a.patel" in e["event"] for e in audit)
    assert any("executed cancel_trade T100291" in e["event"] for e in audit)
