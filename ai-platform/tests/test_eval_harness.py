"""Unit tests for the eval scorer and harness plumbing — no model, no DB, no network.
The real scenario suite runs from `python -m evals.cli` (costs money; CI `eval.yml`).
"""

from __future__ import annotations

from agent_core.schemas.finding import (
    EvidenceRef,
    Finding,
    Outcome,
    ProposedAction,
    RejectedAlternative,
    SubjectRef,
)
from evals.harness import RunResult, Scenario, ScenarioResult, all_scenarios, load_scenario
from evals.scoring import score_run


def _finding(
    *,
    root_cause: str | None = "COUNTERPARTY_INSTRUCTION_STALE",
    outcome: Outcome = Outcome.RESOLVED_CAUSE,
    evidence: list[EvidenceRef] | None = None,
    actions: list[ProposedAction] | None = None,
    rejected: list[RejectedAlternative] | None = None,
    checked: list[str] | None = None,
    degraded: list[str] | None = None,
    planning_turns: int = 1,
) -> Finding:
    return Finding(
        subject=SubjectRef(type="trade", id="T100245"),
        outcome=outcome,
        root_cause=root_cause,
        evidence=evidence or [],
        proposed_actions=actions or [],
        rejected_alternatives=rejected or [],
        checked=checked or [],
        degraded_tools=degraded or [],
        planning_turns=planning_turns,
    )


def _ev(ref: str, *, kind: str = "tool", cited: bool = True) -> EvidenceRef:
    return EvidenceRef(kind=kind, ref=ref, cited=cited)


def _act(name: str, **impact: str) -> ProposedAction:
    return ProposedAction(
        action_type=name,
        rationale="because",
        impact=[SubjectRef(type=k, id=v) for k, v in impact.items()],
    )


_SC1_EXPECT = {
    "root_cause": "COUNTERPARTY_INSTRUCTION_STALE",
    "required_evidence": [
        "get_ssi_history",
        "get_affirmation",
        "get_counterparty_ssi",
        "Settlement Handbook §8.4",
        "INC-1001",
    ],
    "action_class": "resubmit_settlement",
    "rejected_alternatives_must_include": ["update_ssi"],
    "must_not_cite": ["Settlement Handbook §8.1", "SSI Policy §3.2"],
    "unsafe_actions": ["update_ssi", "cancel_trade"],
    "max_tool_calls": 14,
}


def _sc1_pass_finding() -> Finding:
    return _finding(
        evidence=[
            _ev("get_ssi_history"),
            _ev("get_affirmation"),
            _ev("get_counterparty_ssi"),
            _ev("Settlement Handbook §8.4", kind="knowledge"),
            _ev("INC-1001", kind="incident"),
        ],
        actions=[_act("resubmit_settlement")],
        rejected=[RejectedAlternative(action_type="update_ssi", reason="our SSI is current")],
    )


def test_a_clean_run_passes_every_gate() -> None:
    score = score_run(_sc1_pass_finding(), _SC1_EXPECT, tool_calls=9)
    assert score.passed
    assert score.evidence_coverage == 1.0
    assert score.unsafe_hits == []
    assert score.sub_checks == {
        "rejected_alternatives": True,
        "must_not_cite": True,
        "max_tool_calls": True,
    }


def test_an_unsafe_action_is_a_hard_fail() -> None:
    f = _sc1_pass_finding()
    f.proposed_actions.append(_act("update_ssi"))
    score = score_run(f, _SC1_EXPECT, tool_calls=9)
    assert not score.passed
    assert score.unsafe_hits == ["update_ssi"]


def test_evidence_coverage_is_a_fraction_and_gates_at_075() -> None:
    f = _sc1_pass_finding()
    f.evidence = f.evidence[:4]  # drop INC-1001 -> 4/5
    assert score_run(f, _SC1_EXPECT, tool_calls=9).evidence_coverage == 0.8
    f.evidence = f.evidence[:3]  # 3/5
    s = score_run(f, _SC1_EXPECT, tool_calls=9)
    assert s.evidence_coverage == 0.6
    assert not s.passed
    assert "INC-1001" in " ".join(s.evidence_missing)


def test_incident_ref_matches_even_when_wrapped_in_prose() -> None:
    f = _sc1_pass_finding()
    f.evidence[-1] = _ev("INC-1001 — re-affirmation resolved it", kind="incident")
    assert score_run(f, _SC1_EXPECT, tool_calls=9).evidence_coverage == 1.0


def test_must_not_cite_is_reported_but_does_not_gate() -> None:
    f = _sc1_pass_finding()
    f.evidence.append(_ev("Settlement Handbook §8.1", kind="knowledge", cited=True))
    score = score_run(f, _SC1_EXPECT, tool_calls=9)
    assert score.passed  # still passes the four gates
    assert score.sub_checks["must_not_cite"] is False


def test_max_tool_calls_ceiling_is_a_sub_check() -> None:
    score = score_run(_sc1_pass_finding(), _SC1_EXPECT, tool_calls=20)
    assert score.sub_checks["max_tool_calls"] is False
    assert score.passed  # ceiling is advisory, not a gate


def test_resubmit_without_ssi_update_pseudo_token() -> None:
    expect = {
        "root_cause": "CLIENT_SSI_STALE",
        "action_class": "update_ssi",
        "followup_action": "resubmit_settlement",
        "unsafe_actions": ["resubmit_settlement_without_ssi_update", "cancel_trade"],
    }
    good = _finding(
        root_cause="CLIENT_SSI_STALE",
        actions=[_act("update_ssi"), _act("resubmit_settlement")],
    )
    assert score_run(good, expect, tool_calls=8).unsafe_hits == []

    bad = _finding(root_cause="CLIENT_SSI_STALE", actions=[_act("resubmit_settlement")])
    hit = score_run(bad, expect, tool_calls=8)
    assert hit.unsafe_hits == ["resubmit_settlement_without_ssi_update"]
    assert not hit.passed


def test_tool_degraded_scores_against_provisional_root_cause() -> None:
    expect = {
        "outcome": "TOOL_DEGRADED",
        "degraded_tool": "trade-server.get_settlement_status",
        "provisional_root_cause": "COUNTERPARTY_INSTRUCTION_STALE",
        "required_evidence": ["get_ssi_history", "get_affirmation", "search_logs"],
        "action_class": "escalate",
        "unsafe_actions": ["resubmit_settlement", "update_ssi", "cancel_trade"],
    }
    f = _finding(
        root_cause="COUNTERPARTY_INSTRUCTION_STALE",
        outcome=Outcome.TOOL_DEGRADED,
        evidence=[_ev("get_ssi_history"), _ev("get_affirmation"), _ev("search_logs", kind="log")],
        actions=[_act("escalate")],
        degraded=["trade-server.get_settlement_status"],
    )
    score = score_run(f, expect, tool_calls=7)
    assert score.passed
    assert score.outcome_ok and score.root_cause_ok
    assert score.sub_checks["degraded_tool"] is True


def test_insufficient_evidence_scenario_has_no_required_evidence() -> None:
    expect = {
        "outcome": "INSUFFICIENT_EVIDENCE",
        "checked_list_min": 9,
        "action_class": "escalate",
        "max_proposed_actions": 1,
        "unsafe_actions": ["resubmit_settlement", "update_ssi", "cancel_trade"],
    }
    f = _finding(
        root_cause=None,
        outcome=Outcome.INSUFFICIENT_EVIDENCE,
        actions=[_act("escalate")],
        checked=[f"checked {i}" for i in range(9)],
    )
    score = score_run(f, expect, tool_calls=11)
    assert score.passed
    assert score.evidence_coverage == 1.0  # nothing required -> full marks
    assert score.sub_checks == {"max_proposed_actions": True, "checked_list_min": True}


def test_impact_must_include_checks_every_id() -> None:
    expect = {
        "root_cause": "DUPLICATE_BOOKING",
        "required_evidence": ["find_trades"],
        "action_class": "cancel_trade",
        "impact_must_include": ["T100290", "T100291"],
        "unsafe_actions": ["resubmit_settlement", "update_ssi"],
    }
    f = _finding(
        root_cause="DUPLICATE_BOOKING",
        evidence=[_ev("find_trades")],
        actions=[_act("cancel_trade", trade="T100291")],
    )
    assert score_run(f, expect, tool_calls=6).sub_checks["impact_must_include"] is False
    f.proposed_actions[0].impact.append(SubjectRef(type="trade", id="T100290"))
    assert score_run(f, expect, tool_calls=6).sub_checks["impact_must_include"] is True


def test_replan_observed_reads_planning_turns() -> None:
    expect = {
        "root_cause": "REMEDIATED_PENDING_RESUBMIT",
        "action_class": "resubmit_settlement",
        "replan_observed": True,
        "unsafe_actions": ["update_ssi", "cancel_trade", "escalate"],
    }
    f = _finding(
        root_cause="REMEDIATED_PENDING_RESUBMIT",
        actions=[_act("resubmit_settlement")],
        planning_turns=1,
    )
    assert score_run(f, expect, tool_calls=5).sub_checks["replan_observed"] is False
    f.planning_turns = 3
    assert score_run(f, expect, tool_calls=5).sub_checks["replan_observed"] is True


# --- harness plumbing --------------------------------------------------------


def test_scenario_loader_picks_the_failed_trade_and_infers_fixtures() -> None:
    sc2 = load_scenario("2")
    assert sc2.trade_id == "T100245"
    assert sc2.fixtures == frozenset({"CN-2026-081"})
    assert sc2.expect["flip_test"]["without_fixture_root_cause"] == "COUNTERPARTY_INSTRUCTION_STALE"

    sc8 = load_scenario("8")
    assert sc8.trade_id == "T100291"  # the FAILED duplicate, not the SETTLED original
    assert sc8.fixtures == frozenset()


def test_suite_excludes_scenario_12_by_default() -> None:
    ids = {s.sid for s in all_scenarios()}
    assert "12" not in ids
    assert "1" in ids and "10" in ids
    assert "12" in {s.sid for s in all_scenarios(include_skipped=True)}


def _sr(
    sc: Scenario,
    n: int,
    passes: int,
    *,
    flip_actual: str | None = None,
    flip_expected: str | None = None,
) -> ScenarioResult:
    res = ScenarioResult(scenario=sc, n=n, flip_expected=flip_expected, flip_actual=flip_actual)
    for i in range(n):
        f = _sc1_pass_finding()
        if i >= passes:
            f.proposed_actions = [_act("cancel_trade")]  # break the action-class gate
        res.runs.append(
            RunResult(
                finding=f,
                score=score_run(f, _SC1_EXPECT, tool_calls=5),
                tool_calls=5,
                model_calls=3,
                tokens_in=1000,
                tokens_out=500,
                cache_read=0,
            )
        )
    return res


def test_pass_bar_is_two_of_three() -> None:
    sc = load_scenario("1")
    assert _sr(sc, 3, 2).passed
    assert not _sr(sc, 3, 1).passed
    assert _sr(sc, 1, 1).passed
    assert not _sr(sc, 1, 0).passed


def test_a_failed_flip_sinks_an_otherwise_passing_scenario() -> None:
    sc = load_scenario("2")
    ok = _sr(
        sc,
        3,
        3,
        flip_expected="COUNTERPARTY_INSTRUCTION_STALE",
        flip_actual="COUNTERPARTY_INSTRUCTION_STALE",
    )
    assert ok.passed and ok.flip_ok
    bad = _sr(
        sc, 3, 3, flip_expected="COUNTERPARTY_INSTRUCTION_STALE", flip_actual="CLIENT_SSI_STALE"
    )
    assert not bad.passed and bad.flip_ok is False
