"""Phase E — the Developer Agent, incident mode.

FakeModelClient + the in-process `platform` fixture store + the fake enterprise. Covers:
`investigate_incident` reproduces a `revert` incident Finding; `fix_strategy` is corrected
in code from the deployment record (a release note forces `fix_forward`); the Developer
allowlist and the discovered tool set contain **no** deploy / merge / approve; the
change-ticket write tool honours the approval gate.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest

from agent_core import policy
from agent_core.agents import DEVELOPER, spec_for
from agent_core.developer import investigate_incident
from agent_core.reasoning.model_client import FakeModelClient, ModelResponse
from agent_core.schemas.finding import Outcome
from mcp_servers._fake_enterprise import FakeEnterpriseClient
from mcp_servers.hub import SERVERS
from mcp_servers.platform import store as platform_store
from mcp_servers.platform.tools import open_change_ticket
from platform_api import cases

_FORBIDDEN = {
    "deploy",
    "deploy_service",
    "merge_pr",
    "approve_pr",
    "approve_change",
    "write_config",
    "push_config",
    "merge",
}


@pytest.fixture(autouse=True)
def _reset_platform() -> Iterator[None]:
    platform_store.reset()
    yield
    platform_store.reset()


def _plan(*steps: tuple[str, str, dict[str, str]]) -> str:
    return json.dumps(
        {
            "assumptions": [],
            "steps": [{"server": s, "tool": t, "args": a, "why": "x"} for s, t, a in steps],
        }
    )


def _incident_finding(
    *, fix_strategy: str, target: str, root_cause: str = "CONFIG_REGRESSION"
) -> str:
    return json.dumps(
        {
            "subject": {"type": "job", "id": "job-4471"},
            "outcome": "RESOLVED_CAUSE",
            "root_cause": root_cause,
            "evidence": [
                {"kind": "tool", "ref": "get_deployments", "cited": True},
                {"kind": "tool", "ref": "diff_config", "cited": True},
                {"kind": "tool", "ref": "get_platform_logs", "cited": True},
            ],
            "blast_radius": [
                {"type": "trade", "id": "T100245"},
                {"type": "trade", "id": "T100251"},
            ],
            "fix_strategy": fix_strategy,
            "proposed_actions": [
                {
                    "action_type": "open_change_ticket",
                    "params": {
                        "kind": fix_strategy,
                        "target": target,
                        "summary": f"{fix_strategy} {target}",
                    },
                    "rationale": "the change that broke the batch",
                    "impact": [],
                },
                {
                    "action_type": "rerun_job",
                    "params": {"job_id": "job-4471"},
                    "rationale": "clear the 47-record backlog once applied",
                    "impact": [],
                },
            ],
            "rejected_alternatives": [
                {"action_type": "the other strategy", "reason": "see fix_strategy", "evidence": []}
            ],
            "confidence_basis": "the deployment, its config diff, and the abort line",
        }
    )


_PLAN_STEPS = _plan(
    ("platform", "get_service_health", {"service": "settlement-engine"}),
    ("platform", "get_job_runs", {"name": "settlement-batch"}),
    ("platform", "get_deployments", {"service": "settlement-engine"}),
    ("platform", "diff_config", {"deployment_id": "dep-88"}),
    ("platform", "get_platform_logs", {"job_id": "job-4471"}),
)


# --- spec / policy wiring ----------------------------------------------------


def test_developer_has_no_deploy_merge_or_approve_anywhere() -> None:
    all_tools = {fn.__name__ for spec in SERVERS.values() for fn in spec.tools}
    assert all_tools.isdisjoint(_FORBIDDEN), all_tools & _FORBIDDEN

    assert DEVELOPER.allowlist_key == "developer"
    for banned in (
        "deploy",
        "merge_pr",
        "approve_pr",
        "approve_change",
        "update_ssi",
        "resubmit_settlement",
    ):
        assert policy.allowed("developer", banned) is False
    assert policy.allowed("developer", "open_change_ticket") is True
    assert policy.allowed("developer", "rerun_job") is True
    assert spec_for("developer") is DEVELOPER
    assert "platform" in DEVELOPER.tool_servers and "client" not in DEVELOPER.tool_servers


# --- incident mode ---------------------------------------------------------


async def test_incident_run_reproduces_a_revert_finding(
    fake_enterprise: FakeEnterpriseClient,
) -> None:
    fake = FakeModelClient(
        [
            ModelResponse(text=_PLAN_STEPS),
            ModelResponse(text=_plan()),
            ModelResponse(text=_incident_finding(fix_strategy="revert", target="dep-88")),
        ]
    )
    finding = await investigate_incident(
        "job-4471", request="why did the settlement batch fail?", client=fake
    )

    assert finding.outcome is Outcome.RESOLVED_CAUSE
    assert finding.root_cause == "CONFIG_REGRESSION"
    assert finding.fix_strategy == "revert"
    assert {s.id for s in finding.blast_radius} == {"T100245", "T100251"}
    assert [a.action_type for a in finding.proposed_actions] == ["open_change_ticket", "rerun_job"]
    assert finding.proposed_actions[0].params["kind"] == "revert"
    assert finding.proposed_actions[0].proposed_by == "developer"
    assert finding.case_id  # a case was opened


async def test_release_note_forces_fix_forward_in_code(
    fake_enterprise: FakeEnterpriseClient,
) -> None:
    # synthesis says "revert" but the target deployment (dep-91) carries a release note.
    fake = FakeModelClient(
        [
            ModelResponse(text=_PLAN_STEPS),
            ModelResponse(text=_plan()),
            ModelResponse(text=_incident_finding(fix_strategy="revert", target="dep-91")),
        ]
    )
    finding = await investigate_incident("job-4471", request="diagnose", client=fake)

    assert finding.fix_strategy == "fix_forward"
    assert finding.proposed_actions[0].params["kind"] == "fix_forward"
    assert any("fix_strategy set to fix_forward" in q for q in finding.open_questions)


# --- governance ----------------------------------------------------------


async def test_change_ticket_refuses_a_forged_approval(
    fake_enterprise: FakeEnterpriseClient,
) -> None:
    result = await open_change_ticket("revert", "dep-88", "x", approval_id="ap_forged1")
    assert result["code"] == "ApprovalError"
    assert platform_store.change_tickets() == []


async def test_approved_change_ticket_opens_and_audits(
    fake_enterprise: FakeEnterpriseClient,
) -> None:
    case = cases.create_case("job", "job-4471", "incident")
    approval = cases.propose_action(
        case["case_id"],
        "open_change_ticket",
        {"kind": "revert", "target": "dep-88", "summary": "revert dep-88"},
        "unexplained config change",
        [{"type": "job", "id": "job-4471"}],
        True,
    )
    cases.decide(approval["approval_id"], "APPROVED", "d.patel", "CHANGE_APPROVER")

    ticket = await open_change_ticket(
        "revert", "dep-88", "revert dep-88", approval_id=approval["approval_id"]
    )

    assert ticket["kind"] == "revert" and ticket["target"] == "dep-88"
    assert len(platform_store.change_tickets()) == 1
    audit = cases.get_case(case["case_id"])["audit"]
    assert any("opened change ticket" in e["event"] for e in audit)
