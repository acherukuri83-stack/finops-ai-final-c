"""Phase C — the Investigator split into specialists over one shared runner.

Covers the wiring (each spec's tool scope + allowlist key), that `run_specialist`
reproduces a single-trade Settlement `Finding`, and the policy demo the split exists for:
**Settlement cannot write SSI** — a `update_ssi` it proposes is dropped by the policy
engine with a REJECTED span and a note in `open_questions`; only Risk/Client owns it.

FakeModelClient (queued Plan then Finding JSON) + the in-process fake enterprise — no
network, no DB.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest

from agent_core import policy
from agent_core.agents import KNOWLEDGE, RISK_CLIENT, SETTLEMENT, run_specialist, spec_for
from agent_core.reasoning.model_client import FakeModelClient, ModelResponse
from agent_core.schemas.finding import Finding, Outcome, ProposedAction, SubjectRef
from mcp_servers._fake_enterprise import FakeEnterpriseClient


def _plan(*steps: tuple[str, str, dict[str, str]]) -> str:
    return json.dumps(
        {
            "assumptions": [],
            "steps": [{"server": s, "tool": t, "args": a, "why": "x"} for s, t, a in steps],
        }
    )


_SETTLEMENT_FINDING = json.dumps(
    {
        "subject": {"type": "trade", "id": "T100245"},
        "outcome": "RESOLVED_CAUSE",
        "root_cause": "COUNTERPARTY_INSTRUCTION_STALE",
        "evidence": [{"kind": "tool", "ref": "get_ssi_history", "cited": True}],
        "proposed_actions": [
            {"action_type": "resubmit_settlement", "rationale": "cpty re-affirms", "impact": []}
        ],
        "rejected_alternatives": [
            {"action_type": "update_ssi", "reason": "our SSI is current", "evidence": []}
        ],
        "confidence_basis": "SSI history plus the affirmation",
    }
)

# Settlement over-reaches: it proposes the SSI write it is structurally barred from.
_SETTLEMENT_PROPOSES_UPDATE_SSI = json.dumps(
    {
        "subject": {"type": "trade", "id": "T100245"},
        "outcome": "RESOLVED_CAUSE",
        "root_cause": "CLIENT_SSI_STALE",
        "evidence": [{"kind": "tool", "ref": "get_ssi_history", "cited": True}],
        "proposed_actions": [
            {"action_type": "update_ssi", "rationale": "our record looks stale", "impact": []},
            {"action_type": "resubmit_settlement", "rationale": "after the fix", "impact": []},
        ],
        "rejected_alternatives": [],
        "confidence_basis": "SSI history",
    }
)


# --- span capture ---------------------------------------------------------------


@pytest.fixture
def spans() -> Iterator[Any]:
    from opentelemetry import trace as _t
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = _t.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        provider = TracerProvider()
        _t.set_tracer_provider(provider)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    exporter.clear()
    try:
        yield exporter
    finally:
        exporter.clear()


def _policy_decisions(exporter: Any) -> dict[str, str]:
    """action_type -> ALLOWED/REJECTED from the `policy` spans."""
    out: dict[str, str] = {}
    for s in exporter.get_finished_spans():
        attrs = s.attributes or {}
        if s.name == "policy":
            out[str(attrs.get("finops.action"))] = str(attrs.get("finops.policy.decision"))
    return out


# --- spec wiring --------------------------------------------------------------


def test_specs_pin_tool_scope_and_allowlist_key() -> None:
    assert SETTLEMENT.allowlist_key == "settlement"
    assert SETTLEMENT.tool_servers == frozenset(
        {"trade", "counterparty", "position", "client", "ops"}
    )
    # Settlement reads client/SSI to establish "our instruction is current" — but the
    # `client` server's write tool is not on its policy allowlist (see the policy test).

    assert RISK_CLIENT.allowlist_key == "risk_client"
    assert {"client", "compliance"} <= RISK_CLIENT.tool_servers
    assert "trade" not in RISK_CLIENT.tool_servers  # the trade is Settlement's to inspect
    assert RISK_CLIENT.subject_type == "account"

    assert KNOWLEDGE.allowlist_key == "knowledge"
    assert KNOWLEDGE.tool_servers == frozenset({"ops"})

    assert spec_for("settlement") is SETTLEMENT
    assert spec_for("risk_client") is RISK_CLIENT


def test_allowlists_split_the_ssi_write_out_of_settlement() -> None:
    assert policy.allowed("settlement", "resubmit_settlement") is True
    assert policy.allowed("settlement", "cancel_trade") is True
    assert policy.allowed("settlement", "update_ssi") is False  # the split's whole point

    assert policy.allowed("risk_client", "update_ssi") is True
    assert policy.allowed("risk_client", "resubmit_settlement") is False  # not its job

    assert policy.allowed("knowledge", "escalate") is False  # retrieval-only, proposes nothing


# --- run_specialist ---------------------------------------------------------


async def test_run_specialist_reproduces_a_settlement_finding(
    fake_enterprise: FakeEnterpriseClient,
) -> None:
    fake = FakeModelClient(
        [
            ModelResponse(
                text=_plan(
                    ("trade", "get_trade", {"trade_id": "T100245"}),
                    ("trade", "get_settlement_status", {"trade_id": "T100245"}),
                )
            ),
            ModelResponse(text=_plan()),
            ModelResponse(text=_SETTLEMENT_FINDING),
        ]
    )
    finding = await run_specialist(
        SETTLEMENT,
        subject=SubjectRef(type="trade", id="T100245"),
        request="Investigate why trade T100245 failed settlement.",
        client=fake,
    )
    assert finding.outcome is Outcome.RESOLVED_CAUSE
    assert finding.root_cause == "COUNTERPARTY_INSTRUCTION_STALE"
    assert [a.action_type for a in finding.proposed_actions] == ["resubmit_settlement"]
    assert finding.proposed_actions[0].proposed_by == "settlement"
    assert finding.trace_id
    assert len(fake.calls) == 3


async def test_settlement_cannot_propose_update_ssi(
    fake_enterprise: FakeEnterpriseClient, spans: Any
) -> None:
    fake = FakeModelClient(
        [ModelResponse(text=_plan()), ModelResponse(text=_SETTLEMENT_PROPOSES_UPDATE_SSI)]
    )
    finding = await run_specialist(
        SETTLEMENT,
        subject=SubjectRef(type="trade", id="T100245"),
        request="Investigate why trade T100245 failed settlement.",
        client=fake,
    )

    kept = [a.action_type for a in finding.proposed_actions]
    assert "update_ssi" not in kept  # dropped by the policy engine
    assert kept == ["resubmit_settlement"]
    assert any("update_ssi" in q and "settlement" in q for q in finding.open_questions)

    decisions = _policy_decisions(spans)
    assert decisions.get("update_ssi") == "REJECTED"
    assert decisions.get("resubmit_settlement") == "ALLOWED"


def test_risk_client_keeps_the_ssi_write_settlement_lost() -> None:
    finding = Finding(
        subject=SubjectRef(type="account", id="ACC-1"),
        outcome=Outcome.RESOLVED_CAUSE,
        root_cause="CLIENT_SSI_STALE",
        proposed_actions=[
            ProposedAction(action_type="update_ssi", rationale="our record is stale")
        ],
    )
    out = policy.apply(finding, RISK_CLIENT.allowlist_key)
    assert [a.action_type for a in out.proposed_actions] == ["update_ssi"]
    assert out.open_questions == []
