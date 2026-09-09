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


def _stockloan_sub(
    *, loan_id: str, root_cause: str = "RECALL_REQUIRED", action: str = "initiate_recall"
) -> Finding:
    return Finding(
        subject=SubjectRef(type="loan", id=loan_id),
        outcome=Outcome.RESOLVED_CAUSE,
        root_cause=root_cause,
        evidence=[EvidenceRef(kind="tool", ref="get_loan", cited=True)],
        proposed_actions=[
            ProposedAction(
                action_type=action,
                rationale="account short to settle; shares out on loan",
                impact=[SubjectRef(type="loan", id=loan_id)],
                proposed_by="stockloan",
            )
        ],
    )


def _knowledge_sub(*, about: str = "T1") -> Finding:
    """A retrieval-only sub-finding — the shape `run_knowledge` returns."""
    return Finding(
        subject=SubjectRef(type="knowledge", id=about),
        outcome=Outcome.RESOLVED_CAUSE,
        evidence=[EvidenceRef(kind="knowledge", ref="Settlement Handbook §8.4", cited=True)],
        checked=["Settlement Handbook §8.4 — re-affirm with the cpty; do not overwrite SSI"],
        confidence_basis="retrieval-only: 1 SOP section(s), 0 past incident(s)",
    )


@pytest.fixture
def _stub_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _no_trades(_client_id: str) -> list[dict[str, Any]]:
        return [{"trade_id": "T1"}, {"trade_id": "T4"}]

    monkeypatch.setattr(supervisor, "_failed_trades", _no_trades)


def _install_dispatch(monkeypatch: pytest.MonkeyPatch, findings: list[Finding]) -> None:
    async def _dispatch(*_a: Any, **_k: Any) -> list[Finding]:
        return findings

    monkeypatch.setattr(supervisor, "_dispatch", _dispatch)


# --- discovery: open stock loans (Sc. 30) ------------------------------------


async def test_open_loans_discovered_from_a_failed_trades_account(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_open_loans` looks up loans on every account the client's FAILED trades touch —
    LN-5001 is on ACC-88213 in the seeded stockloan store."""

    async def _failed(_client_id: str) -> list[dict[str, Any]]:
        return [{"trade_id": "T100245", "account_id": "ACC-88213"}]

    monkeypatch.setattr(supervisor, "_failed_trades", _failed)
    loans = await supervisor._open_loans(await supervisor._failed_trades("HEDGE_FUND_101"))
    assert {ln["loan_id"] for ln in loans} == {"LN-5001", "LN-5002"}  # both open, on ACC-88213
    assert all(ln["open"] for ln in loans)


async def test_open_loans_empty_when_no_failed_trade_names_an_account() -> None:
    assert await supervisor._open_loans([{"trade_id": "T1"}]) == []


async def test_held_wires_discovered_for_a_client() -> None:
    """`_held_wires` pulls the client's HELD wires from the seeded `wire` store — HF-201
    has W300915 and W300917 held."""
    wires = await supervisor._held_wires("HF-201")
    assert {w["wire_id"] for w in wires} == {"W300915", "W300917"}
    assert all(w["status"] == "HELD" for w in wires)
    assert await supervisor._held_wires("NOBODY") == []


def test_fan_out_applies_the_domain_hard_rule_to_a_sub_finding() -> None:
    """The Supervisor calls `run_specialist` directly, so `_apply_domain_rule` must run the
    per-domain `_enforce_*` that the `investigate_*` entry points apply. LN-5002's recall
    notice window has passed in the seeded store — `initiate_recall` -> `book_buy_in`."""
    sub = _stockloan_sub(loan_id="LN-5002", action="initiate_recall")
    supervisor._apply_domain_rule("stockloan", sub, "LN-5002", set())
    assert [a.action_type for a in sub.proposed_actions] == ["book_buy_in"]
    assert sub.root_cause == "RECALL_WINDOW_MISSED"


def test_fan_out_corpactions_rule_notes_a_missing_account() -> None:
    sub = _stockloan_sub(loan_id="CA-7002", action="submit_election")
    supervisor._apply_domain_rule("corpactions", sub, "CA-7002", set())
    assert any("no account in scope" in q for q in sub.open_questions)


async def test_decompose_input_carries_open_loans(monkeypatch: pytest.MonkeyPatch) -> None:
    """The loan line reaches the decompose prompt so the model can raise a `stockloan`
    sub-task for a client-level ask."""
    seen: dict[str, str] = {}

    async def _capture(client: Any, **kw: Any) -> Any:
        seen["content"] = kw["messages"][0]["content"]
        from agent_core.schemas.subtask import DecomposePlan

        return DecomposePlan(subtasks=[]), ModelResponse(text="{}")

    monkeypatch.setattr(supervisor, "complete_structured_traced", _capture)
    await supervisor._decompose(
        FakeModelClient([]),
        "investigate HF101",
        "HEDGE_FUND_101",
        [{"trade_id": "T100245", "account_id": "ACC-88213", "failure_code": "X"}],
        [
            {
                "loan_id": "LN-5001",
                "security_id": "NVDA",
                "qty": 30000,
                "counterparty": "CP-020",
                "account_id": "ACC-88213",
                "rate_bps": 45,
                "return_needed_by": "2026-09-10",
                "open": True,
            }
        ],
    )
    assert "Open stock loans" in seen["content"]
    assert "LN-5001" in seen["content"]


async def test_decompose_input_carries_held_wires(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, str] = {}

    async def _capture(client: Any, **kw: Any) -> Any:
        seen["content"] = kw["messages"][0]["content"]
        from agent_core.schemas.subtask import DecomposePlan

        return DecomposePlan(subtasks=[]), ModelResponse(text="{}")

    monkeypatch.setattr(supervisor, "complete_structured_traced", _capture)
    await supervisor._decompose(
        FakeModelClient([]),
        "investigate HF-201",
        "HF-201",
        [],
        [],
        [
            {
                "wire_id": "W300917",
                "client_id": "HF-201",
                "account_id": "ACCT-201",
                "currency": "USD",
                "amount": 3_100_000,
                "beneficiary": "Orion Freight Co",
                "beneficiary_account": "BEN-777",
                "hold_reason": "NEW_BENEFICIARY",
                "value_date": "2026-09-06",
            }
        ],
    )
    assert "Held outgoing wires" in seen["content"]
    assert "W300917" in seen["content"]


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


async def test_all_insufficient_recommends_a_platform_incident_review(
    _stub_pipeline: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bounded Supervisor -> Developer hand-off: when *every* specialist returns
    INSUFFICIENT_EVIDENCE, the client Finding carries a recommendation to run a platform
    incident review — a recommendation only, never an auto-dispatch."""
    subs = [
        Finding(
            subject=SubjectRef(type="trade", id="T1"),
            outcome=Outcome.INSUFFICIENT_EVIDENCE,
            confidence_basis="no failure_code",
        ),
        Finding(
            subject=SubjectRef(type="trade", id="T4"),
            outcome=Outcome.INSUFFICIENT_EVIDENCE,
            confidence_basis="nothing anomalous",
        ),
    ]
    _install_dispatch(monkeypatch, subs)
    fake = FakeModelClient(
        [
            ModelResponse(
                text=_decompose({"agent": "settlement", "subject_ids": ["T1"], "question": "q"})
            ),
            ModelResponse(text=_client_finding(outcome="INSUFFICIENT_EVIDENCE")),
        ]
    )

    finding = await supervisor.investigate_client("HEDGE_FUND_101", client=fake)

    rec = [q for q in finding.open_questions if "POST /diagnose" in q]
    assert rec, finding.open_questions
    assert "Not auto-dispatched" in rec[0]
    # it is a note, not an action
    assert not any(a.action_type == "diagnose" for a in finding.proposed_actions)


async def test_knowledge_subtask_is_routable_and_stays_background(
    _stub_pipeline: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A `knowledge` sub-finding is retrieval-only: it carries no action, does not drive
    the client outcome, and is excluded from the all-INSUFFICIENT incident recommendation.
    Here the one business specialist resolved, so the client resolves — Knowledge neither
    helps nor blocks that."""
    subs = [
        _settlement_sub(subjects=["T1"], root_cause="COUNTERPARTY_INSTRUCTION_STALE"),
        _knowledge_sub(about="T1"),
    ]
    _install_dispatch(monkeypatch, subs)
    fake = FakeModelClient(
        [
            ModelResponse(
                text=_decompose(
                    {"agent": "settlement", "subject_ids": ["T1"], "question": "why fail?"},
                    {
                        "agent": "knowledge",
                        "subject_ids": ["T1"],
                        "question": "what does the SOP say?",
                    },
                )
            ),
            ModelResponse(
                text=_client_finding(
                    proposed_actions=[
                        {
                            "action_type": "resubmit_settlement",
                            "rationale": "cpty re-affirms",
                            "impact": [{"type": "trade", "id": "T1"}],
                            "proposed_by": "settlement",
                        }
                    ]
                )
            ),
        ]
    )

    finding = await supervisor.investigate_client("HEDGE_FUND_101", client=fake)

    assert {sf.subject.type for sf in finding.sub_findings} == {"trade", "knowledge"}
    assert [a.action_type for a in finding.proposed_actions] == ["resubmit_settlement"]
    assert finding.outcome is Outcome.RESOLVED_CAUSE
    assert not any("POST /diagnose" in q for q in finding.open_questions)


async def test_knowledge_does_not_mask_an_all_insufficient_business_result(
    _stub_pipeline: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # settlement came back empty; only the knowledge lookup "resolved". The incident
    # recommendation must still fire, and the client outcome must not read RESOLVED.
    subs = [
        Finding(
            subject=SubjectRef(type="trade", id="T1"),
            outcome=Outcome.INSUFFICIENT_EVIDENCE,
            confidence_basis="no failure_code",
        ),
        _knowledge_sub(about="T1"),
    ]
    _install_dispatch(monkeypatch, subs)
    fake = FakeModelClient(
        [
            ModelResponse(
                text=_decompose({"agent": "settlement", "subject_ids": ["T1"], "question": "q"})
            ),
            ModelResponse(text=_client_finding(outcome="INSUFFICIENT_EVIDENCE")),
        ]
    )

    finding = await supervisor.investigate_client("HEDGE_FUND_101", client=fake)

    assert finding.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert any("POST /diagnose" in q for q in finding.open_questions)


async def test_mixed_outcomes_do_not_trigger_the_incident_recommendation(
    _stub_pipeline: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    subs = [
        _settlement_sub(subjects=["T1"], root_cause="COUNTERPARTY_INSTRUCTION_STALE"),
        Finding(
            subject=SubjectRef(type="trade", id="T4"),
            outcome=Outcome.INSUFFICIENT_EVIDENCE,
            confidence_basis="nothing anomalous",
        ),
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
                            "rationale": "cpty re-affirms",
                            "impact": [{"type": "trade", "id": "T1"}],
                            "proposed_by": "settlement",
                        }
                    ]
                )
            ),
        ]
    )

    finding = await supervisor.investigate_client("HEDGE_FUND_101", client=fake)

    assert not any("POST /diagnose" in q for q in finding.open_questions)


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


# --- Scenario 30: mixed-domain client (settlement + stock loan) ---------------


async def test_correlates_a_mixed_domain_client(
    _stub_pipeline: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sc. 30 (wire-free): one client with a settlement fail and a stock-loan recall.
    The Supervisor dispatches a `settlement` and a `stockloan` sub-task and synthesizes
    one client answer carrying both domains' actions."""
    subs = [
        _settlement_sub(subjects=["T1"], root_cause="COUNTERPARTY_INSTRUCTION_STALE"),
        _stockloan_sub(loan_id="LN-5001"),
    ]
    _install_dispatch(monkeypatch, subs)
    fake = FakeModelClient(
        [
            ModelResponse(
                text=_decompose(
                    {"agent": "settlement", "subject_ids": ["T1"], "question": "settlement fail?"},
                    {"agent": "stockloan", "subject_ids": ["LN-5001"], "question": "recall?"},
                )
            ),
            ModelResponse(
                text=_client_finding(
                    proposed_actions=[
                        {
                            "action_type": "resubmit_settlement",
                            "rationale": "cpty re-affirms",
                            "impact": [{"type": "trade", "id": "T1"}],
                            "proposed_by": "settlement",
                        },
                        {
                            "action_type": "initiate_recall",
                            "rationale": "shares out on LN-5001, needed to settle",
                            "impact": [{"type": "loan", "id": "LN-5001"}],
                            "proposed_by": "stockloan",
                        },
                    ]
                )
            ),
        ]
    )

    finding = await supervisor.investigate_client("HEDGE_FUND_101", client=fake)

    assert {sf.subject.type for sf in finding.sub_findings} == {"trade", "loan"}
    kept = {a.action_type for a in finding.proposed_actions}
    assert kept == {"resubmit_settlement", "initiate_recall"}  # both survive re-policy
    # the known-actions registry sees both sub-proposals carried forward
    assert not any("not carried" in q for q in finding.open_questions)


async def test_mixed_client_drops_a_stockloan_action_settlement_cannot_own(
    _stub_pipeline: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # synthesis tags a `book_buy_in` as Settlement's — Settlement has no such action.
    _install_dispatch(monkeypatch, [_stockloan_sub(loan_id="LN-5002", action="book_buy_in")])
    fake = FakeModelClient(
        [
            ModelResponse(
                text=_decompose(
                    {"agent": "stockloan", "subject_ids": ["LN-5002"], "question": "buy-in?"}
                )
            ),
            ModelResponse(
                text=_client_finding(
                    proposed_actions=[
                        {
                            "action_type": "book_buy_in",
                            "rationale": "recall window missed",
                            "impact": [{"type": "loan", "id": "LN-5002"}],
                            "proposed_by": "settlement",
                        }
                    ]
                )
            ),
        ]
    )

    finding = await supervisor.investigate_client("HEDGE_FUND_101", client=fake)

    assert [a.action_type for a in finding.proposed_actions] == []
    assert any("book_buy_in" in q and "settlement allowlist" in q for q in finding.open_questions)
