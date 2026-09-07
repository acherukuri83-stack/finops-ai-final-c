"""Outcome rules are code, not prompt (agent_core/outcomes.py)."""

from __future__ import annotations

from agent_core.outcomes import Observation, classify
from agent_core.schemas.finding import Finding, Outcome, SubjectRef
from agent_core.schemas.plan import PlanStep

_SUBJECT = SubjectRef(type="trade", id="T1")


def _obs(server: str, tool: str, result: object) -> Observation:
    return Observation(PlanStep(server=server, tool=tool, args={}, why="x"), result)


def _finding(**kw: object) -> Finding:
    return Finding(subject=_SUBJECT, outcome=Outcome.RESOLVED_CAUSE, **kw)


def test_required_tool_error_forces_tool_degraded() -> None:
    obs = [
        _obs("trade", "get_trade", {"trade_id": "T1", "status": "FAILED"}),
        _obs("trade", "get_settlement_status", {"code": "UPSTREAM_503", "retryable": True}),
    ]
    out = classify(_finding(root_cause="COUNTERPARTY_INSTRUCTION_STALE"), obs)
    assert out.outcome is Outcome.TOOL_DEGRADED
    assert out.degraded_tools == ["trade.get_settlement_status"]


def test_no_failure_code_and_clean_forces_insufficient_evidence() -> None:
    obs = [
        _obs("trade", "get_trade", {"trade_id": "T1", "status": "FAILED"}),
        _obs("trade", "get_settlement_status", {"trade_id": "T1", "failure_code": "UNKNOWN"}),
        _obs("client", "get_account", {"account_id": "ACC-1", "restrictions": []}),
        _obs("ops", "search_logs", []),
    ]
    out = classify(_finding(root_cause="GUESS"), obs)
    assert out.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert out.root_cause is None
    assert "client.get_account" in out.checked


def test_failure_code_present_keeps_resolved_cause() -> None:
    obs = [
        _obs("trade", "get_trade", {"trade_id": "T1", "status": "FAILED"}),
        _obs("trade", "get_settlement_status", {"failure_code": "COUNTERPARTY_SSI_MISMATCH"}),
    ]
    out = classify(_finding(root_cause="COUNTERPARTY_INSTRUCTION_STALE"), obs)
    assert out.outcome is Outcome.RESOLVED_CAUSE


def test_no_root_cause_with_an_anomaly_is_insufficient_not_resolved() -> None:
    obs = [
        _obs("trade", "get_trade", {"status": "FAILED"}),
        _obs("trade", "get_settlement_status", {"failure_code": "UNKNOWN"}),
        _obs(
            "ops", "search_logs", [{"msg": "something happened"}]
        ),  # anomaly -> not the clean path
    ]
    out = classify(_finding(root_cause=None), obs)
    assert out.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert out.checked == []  # not the "clean sweep" path, so no checked list
