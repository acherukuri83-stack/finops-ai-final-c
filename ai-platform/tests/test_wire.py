"""Phase B — the Wire specialist (optional module).

FakeModelClient + the in-process `wire` fixture store. Covers the four hard rules
(screening freeze, insufficient balance, cutoff, new beneficiary), the allowlist, that
`release_wire` is not a tool anywhere, and the approval gate on the writes.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest

from agent_core import policy
from agent_core.agents import WIRE, spec_for
from agent_core.reasoning.model_client import FakeModelClient, ModelResponse
from agent_core.wire import investigate_wire
from mcp_servers._fake_enterprise import FakeEnterpriseClient
from mcp_servers.hub import SERVERS
from mcp_servers.wire import store as wire_store
from mcp_servers.wire.tools import route_to_reviewer
from platform_api import cases


@pytest.fixture(autouse=True)
def _reset_wire() -> Iterator[None]:
    wire_store.reset()
    yield
    wire_store.reset()


def _plan(*steps: tuple[str, str, dict[str, str]]) -> str:
    return json.dumps(
        {
            "assumptions": [],
            "steps": [{"server": s, "tool": t, "args": a, "why": "x"} for s, t, a in steps],
        }
    )


def _wire_finding(*, wire_id: str, actions: list[dict[str, object]], root_cause: str | None) -> str:
    return json.dumps(
        {
            "subject": {"type": "wire", "id": wire_id},
            "outcome": "RESOLVED_CAUSE",
            "root_cause": root_cause,
            "evidence": [{"kind": "tool", "ref": "get_wire", "cited": True}],
            "proposed_actions": actions,
            "rejected_alternatives": [],
            "confidence_basis": "the wire, the standing instructions, and the cutoff",
        }
    )


# --- spec / allowlist / no release tool -------------------------------------


def test_wire_spec_and_allowlist() -> None:
    assert WIRE.allowlist_key == "wire"
    assert WIRE.tool_servers == frozenset({"wire", "ops"})
    assert WIRE.subject_type == "wire"
    assert spec_for("wire") is WIRE
    for act in (
        "route_to_reviewer",
        "add_standing_instruction",
        "reschedule_value_date",
        "open_compliance_referral",
    ):
        assert policy.allowed("wire", act) is True
    assert policy.allowed("wire", "update_ssi") is False
    assert policy.allowed("wire", "resubmit_settlement") is False


def test_release_wire_is_not_a_tool_anywhere() -> None:
    every_tool = {fn.__name__ for spec in SERVERS.values() for fn in spec.tools}
    assert "release_wire" not in every_tool
    assert "release" not in every_tool


# --- Sc. 13: new beneficiary, cutoff still open ----------------------------


async def test_new_beneficiary_routes_to_reviewer_with_a_cutoff_warning(
    fake_enterprise: FakeEnterpriseClient,
) -> None:
    fake = FakeModelClient(
        [
            ModelResponse(text=_plan(("wire", "get_wire", {"wire_id": "W300917"}))),
            ModelResponse(text=_plan()),
            ModelResponse(
                text=_wire_finding(
                    wire_id="W300917",
                    root_cause="NEW_BENEFICIARY_REVIEW",
                    actions=[
                        {
                            "action_type": "route_to_reviewer",
                            "params": {
                                "wire_id": "W300917",
                                "reason": "new beneficiary",
                                "packet": "x",
                            },
                            "rationale": "BEN-777 is not on file",
                            "impact": [],
                        },
                        {
                            "action_type": "add_standing_instruction",
                            "params": {"client_id": "HF-201", "beneficiary_account": "BEN-777"},
                            "rationale": "so future wires are not held",
                            "impact": [],
                        },
                    ],
                )
            ),
        ]
    )
    finding = await investigate_wire("W300917", request="why is W300917 stuck?", client=fake)

    kinds = [a.action_type for a in finding.proposed_actions]
    assert "route_to_reviewer" in kinds
    assert "add_standing_instruction" in kinds  # a *separate* action, not a substitute
    assert finding.root_cause == "NEW_BENEFICIARY_REVIEW"
    assert any("cutoff 16:00 is close" in q for q in finding.open_questions)


# --- Sc. 14: cutoff missed ------------------------------------------------


async def test_cutoff_missed_reschedules_and_never_routes_for_same_day(
    fake_enterprise: FakeEnterpriseClient,
) -> None:
    fake = FakeModelClient(
        [
            ModelResponse(text=_plan(("wire", "get_wire", {"wire_id": "W300918"}))),
            ModelResponse(text=_plan()),
            ModelResponse(
                text=_wire_finding(
                    wire_id="W300918",
                    root_cause=None,
                    actions=[
                        {
                            "action_type": "route_to_reviewer",
                            "params": {"wire_id": "W300918", "reason": "release", "packet": "x"},
                            "rationale": "ready to release",
                            "impact": [],
                        }
                    ],
                )
            ),
        ]
    )
    finding = await investigate_wire("W300918", client=fake)

    kinds = [a.action_type for a in finding.proposed_actions]
    assert kinds == ["reschedule_value_date"]
    assert "route_to_reviewer" not in kinds  # no same-day release attempt after cutoff
    assert finding.root_cause == "CUTOFF_MISSED"


# --- Sc. 15: screening hit ---------------------------------------------


async def test_screening_hit_freezes_to_a_referral_only(
    fake_enterprise: FakeEnterpriseClient,
) -> None:
    fake = FakeModelClient(
        [
            ModelResponse(text=_plan(("wire", "get_wire", {"wire_id": "W300920"}))),
            ModelResponse(text=_plan()),
            ModelResponse(
                text=_wire_finding(
                    wire_id="W300920",
                    root_cause=None,
                    actions=[
                        {
                            "action_type": "route_to_reviewer",
                            "params": {"wire_id": "W300920", "reason": "x", "packet": "y"},
                            "rationale": "looks routine",
                            "impact": [],
                        }
                    ],
                )
            ),
        ]
    )
    finding = await investigate_wire("W300920", client=fake)

    assert [a.action_type for a in finding.proposed_actions] == ["open_compliance_referral"]
    assert len(finding.proposed_actions) == 1
    assert finding.root_cause == "SCREENING_HIT"


# --- Sc. 16: insufficient balance ------------------------------------


async def test_insufficient_balance_proposes_no_wire_action(
    fake_enterprise: FakeEnterpriseClient,
) -> None:
    fake = FakeModelClient(
        [
            ModelResponse(text=_plan(("wire", "get_wire", {"wire_id": "W300921"}))),
            ModelResponse(text=_plan()),
            ModelResponse(
                text=_wire_finding(
                    wire_id="W300921",
                    root_cause=None,
                    actions=[
                        {
                            "action_type": "route_to_reviewer",
                            "params": {"wire_id": "W300921", "reason": "x", "packet": "y"},
                            "rationale": "release it",
                            "impact": [],
                        }
                    ],
                )
            ),
        ]
    )
    finding = await investigate_wire("W300921", client=fake)

    assert [a.action_type for a in finding.proposed_actions] == []
    assert finding.root_cause == "INSUFFICIENT_BALANCE"
    assert any("funding must be arranged" in q for q in finding.open_questions)


# --- Sc. 7: beneficiary mismatch -----------------------------------


async def test_beneficiary_mismatch_routes_to_reviewer(
    fake_enterprise: FakeEnterpriseClient,
) -> None:
    # the model tries to just whitelist BEN-999 — the code adds the reviewer routing
    # (a mismatch is a human decision, not a silent standing-instruction add).
    fake = FakeModelClient(
        [
            ModelResponse(text=_plan(("wire", "get_wire", {"wire_id": "W300915"}))),
            ModelResponse(text=_plan()),
            ModelResponse(
                text=_wire_finding(
                    wire_id="W300915",
                    root_cause=None,
                    actions=[
                        {
                            "action_type": "add_standing_instruction",
                            "params": {"client_id": "HF-201", "beneficiary_account": "BEN-999"},
                            "rationale": "whitelist it",
                            "impact": [],
                        }
                    ],
                )
            ),
        ]
    )
    finding = await investigate_wire("W300915", client=fake)

    assert any(a.action_type == "route_to_reviewer" for a in finding.proposed_actions)
    assert finding.root_cause == "NEW_BENEFICIARY_REVIEW"
    assert any("new beneficiary on W300915" in q for q in finding.open_questions)


# --- the approval gate ---------------------------------------------


async def test_route_write_refuses_a_forged_approval(fake_enterprise: FakeEnterpriseClient) -> None:
    result = await route_to_reviewer("W300917", "x", "packet", approval_id="ap_forged9")
    assert result["code"] == "ApprovalError"
    assert wire_store.actions() == []


async def test_approved_route_records_audits_and_queues(
    fake_enterprise: FakeEnterpriseClient,
) -> None:
    case = cases.create_case("wire", "W300917", "held wire")
    approval = cases.propose_action(
        case["case_id"],
        "route_to_reviewer",
        {"wire_id": "W300917"},
        "new beneficiary",
        [{"type": "wire", "id": "W300917"}],
        True,
    )
    cases.decide(approval["approval_id"], "APPROVED", "w.ops", "OPS_ANALYST")

    row = await route_to_reviewer(
        "W300917", "new beneficiary", "packet text", approval_id=approval["approval_id"]
    )
    assert row["kind"] == "route_to_reviewer" and row["wire_id"] == "W300917"
    assert len(wire_store.actions()) == 1
    assert [q["wire_id"] for q in wire_store.get_approval_queue()] == ["W300917"]
    audit = cases.get_case(case["case_id"])["audit"]
    assert any("routed" in e["event"] for e in audit)
