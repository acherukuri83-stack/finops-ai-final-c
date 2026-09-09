"""Phase F — the CorpActions specialist.

FakeModelClient + the in-process `corpactions` fixture store. Covers: a cash dividend on a
lent-out slice → `raise_claim` (hard rule in code); an elective event past its deadline →
`escalate_ca` (hard rule); the allowlist; the write tools honour the approval gate.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest

from agent_core import policy
from agent_core.agents import CORPACTIONS, spec_for
from agent_core.corpactions import investigate_ca_event
from agent_core.reasoning.model_client import FakeModelClient, ModelResponse
from mcp_servers._fake_enterprise import FakeEnterpriseClient
from mcp_servers.corpactions import store as ca_store
from mcp_servers.corpactions.tools import submit_election
from platform_api import cases


@pytest.fixture(autouse=True)
def _reset_ca() -> Iterator[None]:
    ca_store.reset()
    yield
    ca_store.reset()


def _plan(*steps: tuple[str, str, dict[str, str]]) -> str:
    return json.dumps(
        {
            "assumptions": [],
            "steps": [{"server": s, "tool": t, "args": a, "why": "x"} for s, t, a in steps],
        }
    )


def _ca_finding(
    *, subject_id: str, root_cause: str | None, actions: list[dict[str, object]]
) -> str:
    return json.dumps(
        {
            "subject": {"type": "ca_event", "id": subject_id},
            "outcome": "RESOLVED_CAUSE",
            "root_cause": root_cause,
            "evidence": [{"kind": "tool", "ref": "get_entitlement", "cited": True}],
            "proposed_actions": actions,
            "rejected_alternatives": [],
            "confidence_basis": "the event and the entitlement",
        }
    )


def test_corpactions_spec_and_allowlist() -> None:
    assert CORPACTIONS.allowlist_key == "corpactions"
    assert {"corpactions", "stockloan"} <= CORPACTIONS.tool_servers
    assert CORPACTIONS.subject_type == "ca_event"
    assert spec_for("corpactions") is CORPACTIONS
    assert policy.allowed("corpactions", "raise_claim") is True
    assert policy.allowed("corpactions", "submit_election") is True
    assert policy.allowed("corpactions", "update_ssi") is False


async def test_dividend_on_a_lent_slice_forces_a_claim(
    fake_enterprise: FakeEnterpriseClient,
) -> None:
    # synthesis (wrongly) proposes nothing about the lent slice.
    fake = FakeModelClient(
        [
            ModelResponse(text=_plan(("corpactions", "get_ca_event", {"event_id": "CA-7001"}))),
            ModelResponse(text=_plan()),
            ModelResponse(
                text=_ca_finding(subject_id="CA-7001@ACC-88213", root_cause=None, actions=[])
            ),
        ]
    )
    finding = await investigate_ca_event(
        "CA-7001", "ACC-88213", request="entitlement?", client=fake
    )

    assert finding.root_cause == "MANUFACTURED_PAYMENT_DUE"
    claims = [a for a in finding.proposed_actions if a.action_type == "raise_claim"]
    assert claims and claims[0].params["qty"] == "30000"
    assert any("raise_claim added in code" in q for q in finding.open_questions)


async def test_missed_election_deadline_converts_to_escalate(
    fake_enterprise: FakeEnterpriseClient,
) -> None:
    fake = FakeModelClient(
        [
            ModelResponse(text=_plan(("corpactions", "get_ca_event", {"event_id": "CA-7002"}))),
            ModelResponse(text=_plan()),
            ModelResponse(
                text=_ca_finding(
                    subject_id="CA-7002@ACC-88213",
                    root_cause="ELECTION_DUE",
                    actions=[
                        {
                            "action_type": "submit_election",
                            "params": {
                                "event_id": "CA-7002",
                                "account_id": "ACC-88213",
                                "option": "TAKE_UP",
                            },
                            "rationale": "take up the rights",
                            "impact": [],
                        }
                    ],
                )
            ),
        ]
    )
    finding = await investigate_ca_event("CA-7002", "ACC-88213", request="elect?", client=fake)

    assert [a.action_type for a in finding.proposed_actions] == ["escalate_ca"]
    assert finding.root_cause == "ELECTION_DEADLINE_MISSED"
    assert any("escalate_ca in code" in q for q in finding.open_questions)


async def test_election_write_refuses_a_forged_approval(
    fake_enterprise: FakeEnterpriseClient,
) -> None:
    result = await submit_election("CA-7002", "ACC-88213", "TAKE_UP", approval_id="ap_forgedC")
    assert result["code"] == "ApprovalError"
    assert ca_store.actions() == []


async def test_approved_election_records_and_audits(fake_enterprise: FakeEnterpriseClient) -> None:
    case = cases.create_case("ca_event", "CA-7002", "corpaction")
    approval = cases.propose_action(
        case["case_id"],
        "submit_election",
        {"event_id": "CA-7002"},
        "elect",
        [{"type": "ca_event", "id": "CA-7002"}],
        True,
    )
    cases.decide(approval["approval_id"], "APPROVED", "c.desk", "OPS_ANALYST")
    row = await submit_election(
        "CA-7002", "ACC-88213", "TAKE_UP", approval_id=approval["approval_id"]
    )
    assert row["kind"] == "submit_election"
    assert len(ca_store.actions()) == 1
    audit = cases.get_case(case["case_id"])["audit"]
    assert any("submitted election TAKE_UP" in e["event"] for e in audit)
