"""Phase E — Developer Agent, verification mode.

`verify_change` applies a change ticket and re-checks the signals deterministically.
Covers: a clean fix → RESOLVED_CAUSE + an incident written and retrievable; a partial fix
→ residual trade handed to Settlement (sub-finding); a fix that did not work → FAILED
verification with **no proposed action and no second fix**.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest

from agent_core.developer import verify_change
from agent_core.reasoning.model_client import FakeModelClient, ModelResponse
from agent_core.schemas.finding import Outcome
from mcp_servers._fake_enterprise import FakeEnterpriseClient
from mcp_servers.platform import store as platform_store
from mcp_servers.platform.tools import get_incident


@pytest.fixture(autouse=True)
def _reset_platform() -> Iterator[None]:
    platform_store.reset()
    yield
    platform_store.reset()


def _ticket(kind: str, target: str) -> str:
    return str(platform_store.add_change_ticket(kind, target, "x", "ap")["ticket_id"])


async def test_clean_fix_writes_a_retrievable_incident() -> None:
    tid = _ticket("revert", "dep-88")

    finding = await verify_change(tid)

    assert finding.outcome is Outcome.RESOLVED_CAUSE
    assert finding.subject.type == "change" and finding.subject.id == tid
    assert not finding.open_questions  # no residual
    inc_refs = [e.ref for e in finding.evidence if e.kind == "incident"]
    assert inc_refs and inc_refs[0].startswith("INC-3")
    # written into the platform incident store and retrievable via the read tool
    got = await get_incident(inc_refs[0])
    assert got["cause"] == "CONFIG_REGRESSION" and "SUCCEEDED" in got["verification"]


async def test_partial_fix_hands_the_residual_to_settlement(
    fake_enterprise: FakeEnterpriseClient,
) -> None:
    tid = _ticket("fix_forward", "dep-88")
    settlement_finding = json.dumps(
        {
            "subject": {"type": "trade", "id": "T100301"},
            "outcome": "RESOLVED_CAUSE",
            "root_cause": "COUNTERPARTY_INSTRUCTION_STALE",
            "evidence": [{"kind": "tool", "ref": "get_ssi_history", "cited": True}],
            "proposed_actions": [
                {"action_type": "resubmit_settlement", "rationale": "after re-affirm", "impact": []}
            ],
            "rejected_alternatives": [],
            "confidence_basis": "ssi history",
        }
    )
    fake = FakeModelClient(
        [
            ModelResponse(text=json.dumps({"assumptions": [], "steps": []})),
            ModelResponse(text=settlement_finding),
        ]
    )

    finding = await verify_change(tid, client=fake)

    assert finding.outcome is Outcome.RESOLVED_CAUSE
    assert any(
        "T100301" in q and "handed to the Settlement specialist" in q
        for q in finding.open_questions
    )
    assert len(finding.sub_findings) == 1
    assert finding.sub_findings[0].subject.id == "T100301"


async def test_fix_that_did_not_work_reports_and_proposes_nothing() -> None:
    tid = _ticket("revert", "dep-70")  # not the cause -> no effect

    finding = await verify_change(tid)

    assert finding.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert finding.proposed_actions == []  # no autonomous second fix
    assert any("verification FAILED" in q for q in finding.open_questions)
    assert any("re-enter incident mode" in q for q in finding.open_questions)
    assert platform_store.incidents() == []  # nothing written on a failed verification


async def test_unknown_ticket_is_insufficient_evidence() -> None:
    finding = await verify_change("CHG-9999")
    assert finding.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert "no change ticket" in finding.confidence_basis
