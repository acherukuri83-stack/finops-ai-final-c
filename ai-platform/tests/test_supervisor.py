"""Phase C — the Supervisor fan-out.

FakeModelClient supplies the decompose plan and the client-level synthesis; the specialist
dispatch is stubbed so these tests exercise the Supervisor's own logic — correlation,
verbatim surfacing of sub-finding gaps, the known-actions registry, and the per-action
policy re-check against the *proposing* specialist's allowlist.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from agent_core import policy, supervisor
from agent_core.reasoning.model_client import FakeModelClient, ModelResponse
from agent_core.schemas.finding import (
    EvidenceRef,
    Finding,
    Outcome,
    ProposedAction,
    RejectedAlternative,
    SubjectRef,
)
from platform_api import cases


def _decompose(*subtasks: dict[str, Any]) -> str:
    return json.dumps({"subtasks": list(subtasks)})


def _client_finding(**kw: Any) -> str:
    body: dict[str, Any] = {
        "subject": {"type": "client", "id": "HEDGE_FUND_101"},
        "outcome": "RESOLVED_CAUSE",
        "proposed_actions": [],
        "open_questions": [],
        "rejected_alternatives": [],
        "evidence": [],
        "confidence_basis": "client picture",
    }
    body.update(kw)
    return json.dumps(body)


def _settlement_sub(
    *,
    subjects: list[str],
    root_cause: str,
    action: str = "resubmit_settlement",
    by: str = "settlement",
) -> Finding:
    return Finding(
        subject=SubjectRef(type="trade", id=subjects[0]),
        outcome=Outcome.RESOLVED_CAUSE,
        root_cause=root_cause,
        evidence=[EvidenceRef(kind="tool", ref="get_ssi_history", cited=True)],
        proposed_actions=[
            ProposedAction(
                action_type=action,
                rationale="fix it",
                impact=[SubjectRef(type="trade", id=s) for s in subjects],
                proposed_by=by,
            )
        ],
        rejected_alternatives=[
            RejectedAlternative(action_type="update_ssi", reason="our SSI is current")
        ],
    )


@pytest.fixture
def _stub_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _no_trades(_client_id: str) -> list[dict[str, Any]]:
        return [{"trade_id": "T1"}, {"trade_id": "T4"}]

    monkeypatch.setattr(supervisor, "_failed_trades", _no_trades)


def _install_dispatch(monkeypatch: pytest.MonkeyPatch, findings: list[Finding]) -> None:
    async def _dispatch(_client: Any, _subtasks: Any, _scenario_id: Any) -> list[Finding]:
        return findings

    monkeypatch.setattr(supervisor, "_dispatch", _dispatch)


# --- allowlist -------------------------------------------------------------------


def test_supervisor_allowlist_is_case_bookkeeping_only() -> None:
    assert policy.allowed("supervisor", "create_case") is True
    assert policy.allowed("supervisor", "update_case") is True
    assert policy.allowed("supervisor", "resubmit_settlement") is False
    assert policy.allowed("supervisor", "update_ssi") is False


# --- correlation ---------------------------------------------------------------


async def test_correlates_two_sub_findings_into_grouped_actions(
    _stub_pipeline: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    subs = [
        _settlement_sub(subjects=["T1", "T2", "T3"], root_cause="COUNTERPARTY_INSTRUCTION_STALE"),
        _settlement_sub(subjects=["T4"], root_cause="DELIVERY_SHORTFALL"),
    ]
    _install_dispatch(monkeypatch, subs)
    fake = FakeModelClient(
        [
            ModelResponse(
                text=_decompose({"agent": "settlement", "subject_ids": ["T1"], "question": "q"})
            ),
            ModelResponse(
                text=_client_finding(
                    proposed_actions=[
                        {
                            "action_type": "resubmit_settlement",
                            "rationale": "three SSI fails, one cause",
                            "impact": [{"type": "trade", "id": t} for t in ["T1", "T2", "T3"]],
                            "proposed_by": "settlement",
                        },
                        {
                            "action_type": "resubmit_settlement",
                            "rationale": "short position",
                            "impact": [{"type": "trade", "id": "T4"}],
                            "proposed_by": "settlement",
                        },
                    ]
                )
            ),
        ]
    )

    finding = await supervisor.investigate_client("HEDGE_FUND_101", client=fake)

    assert finding.subject.type == "client"
    assert len(finding.sub_findings) == 2
    assert len(finding.proposed_actions) == 2
    impacts = sorted(sorted(s.id for s in a.impact) for a in finding.proposed_actions)
    assert impacts == [["T1", "T2", "T3"], ["T4"]]
    assert finding.case_id
    assert cases.get_case(finding.case_id)["subject_type"] == "client"


async def test_insufficient_sub_finding_is_surfaced_verbatim(
    _stub_pipeline: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    gap = Finding(
        subject=SubjectRef(type="trade", id="T9"),
        outcome=Outcome.INSUFFICIENT_EVIDENCE,
        confidence_basis="no failure_code and nothing anomalous",
    )
    _install_dispatch(monkeypatch, [gap])
    fake = FakeModelClient(
        [
            ModelResponse(
                text=_decompose({"agent": "settlement", "subject_ids": ["T9"], "question": "q"})
            ),
            ModelResponse(
                text=_client_finding(outcome="INSUFFICIENT_EVIDENCE")
            ),  # says nothing about T9
        ]
    )

    finding = await supervisor.investigate_client("HEDGE_FUND_101", client=fake)

    assert any("T9" in q and "INSUFFICIENT_EVIDENCE" in q for q in finding.open_questions)
    assert finding.outcome is Outcome.INSUFFICIENT_EVIDENCE


async def test_known_actions_registry_catches_a_dropped_proposal(
    _stub_pipeline: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    sub = _settlement_sub(subjects=["T1"], root_cause="COMPLIANCE_RESTRICTION", action="escalate")
    _install_dispatch(monkeypatch, [sub])
    fake = FakeModelClient(
        [
            ModelResponse(
                text=_decompose({"agent": "settlement", "subject_ids": ["T1"], "question": "q"})
            ),
            ModelResponse(text=_client_finding()),  # no proposed_actions at all — drops `escalate`
        ]
    )

    finding = await supervisor.investigate_client("HEDGE_FUND_101", client=fake)

    assert any("escalate" in q and "not carried" in q for q in finding.open_questions)


async def test_grouped_action_is_repoliced_against_the_proposing_specialist(
    _stub_pipeline: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A malformed synthesis carries an update_ssi action tagged as Settlement's — the
    # Supervisor must drop it (Settlement has no update_ssi) even though a specialist
    # "proposed" it.
    sub = _settlement_sub(subjects=["T1"], root_cause="CLIENT_SSI_STALE", action="update_ssi")
    _install_dispatch(monkeypatch, [sub])
    fake = FakeModelClient(
        [
            ModelResponse(
                text=_decompose({"agent": "settlement", "subject_ids": ["T1"], "question": "q"})
            ),
            ModelResponse(
                text=_client_finding(
                    proposed_actions=[
                        {
                            "action_type": "update_ssi",
                            "rationale": "our record is stale",
                            "impact": [{"type": "trade", "id": "T1"}],
                            "proposed_by": "settlement",
                        }
                    ]
                )
            ),
        ]
    )

    finding = await supervisor.investigate_client("HEDGE_FUND_101", client=fake)

    assert [a.action_type for a in finding.proposed_actions] == []
    assert any("update_ssi" in q and "settlement allowlist" in q for q in finding.open_questions)
