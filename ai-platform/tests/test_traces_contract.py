"""Contract: the trace store round-trips against a real Postgres, and a real
investigation persists a full trace. Kept in its own module so the unit-test
`_stub_store` monkeypatch (test_traces_api.py) can't reach it.

Runs only where the stack is up (`-m contract`).
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator

import pytest

from agent_core.loop import investigate
from agent_core.reasoning.model_client import FakeModelClient, ModelResponse
from platform_api import trace_store
from platform_api.settings import settings

pytestmark = pytest.mark.contract


@pytest.fixture
def _sql_traces(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    if not os.environ.get("ENTERPRISE_BASE_URL"):
        pytest.skip("needs the running stack + seeded Postgres")
    from mcp_servers import _enterprise
    from mcp_servers._enterprise import HttpEnterpriseClient
    from platform_api import cases, store
    from platform_api.telemetry import init_tracing

    settings.traces_enabled = True
    monkeypatch.setattr(trace_store, "_STRICT", True)  # surface write failures in CI
    store.ensure_schema()
    init_tracing()  # register the PostgresSpanProcessor for this run
    cases.set_backend(cases.SqlBackend())
    _enterprise.set_enterprise_client(HttpEnterpriseClient(os.environ["ENTERPRISE_BASE_URL"]))
    try:
        yield
    finally:
        settings.traces_enabled = False
        cases.set_backend(None)
        _enterprise.set_enterprise_client(None)


def _plan(*steps: tuple[str, str, dict[str, str]]) -> str:
    return json.dumps(
        {
            "assumptions": [],
            "steps": [{"server": s, "tool": t, "args": a, "why": "x"} for s, t, a in steps],
        }
    )


_FINDING_JSON = json.dumps(
    {
        "subject": {"type": "trade", "id": "T100245"},
        "outcome": "RESOLVED_CAUSE",
        "root_cause": "COUNTERPARTY_INSTRUCTION_STALE",
        "evidence": [{"kind": "tool", "ref": "get_ssi_history", "cited": True}],
        "proposed_actions": [
            {"action_type": "resubmit_settlement", "rationale": "cpty re-affirms", "impact": []}
        ],
        "rejected_alternatives": [
            {
                "action_type": "update_ssi",
                "reason": "our SSI is current (Handbook §8.4 ¶3)",
                "evidence": [],
            }
        ],
        "confidence_basis": "SSI history plus the affirmation",
    }
)


def test_trace_store_round_trips_against_postgres(_sql_traces: None) -> None:
    """Isolates the store layer from the loop: a hand-built trace persists and reads back."""
    tid = "deadbeef" * 4
    trace_store.finalize_trace(
        tid,
        request="manual",
        subject_type="trade",
        subject_id="T1",
        scenario_id=None,
        case_id="",
        agent="investigator",
        outcome="RESOLVED_CAUSE",
        root_cause="X",
        status="COMPLETE",
        finding={"root_cause": "X"},
    )
    try:
        got = trace_store.get_trace(tid)
        assert got is not None and got["root_cause"] == "X"
    finally:
        trace_store.delete_trace(tid)


async def test_a_real_investigation_persists_every_span_type(_sql_traces: None) -> None:
    fake = FakeModelClient(
        [
            ModelResponse(
                text=_plan(
                    ("trade", "get_trade", {"trade_id": "T100245"}),
                    ("trade", "get_settlement_status", {"trade_id": "T100245"}),
                    ("client", "get_ssi_history", {"account_id": "ACC-88213"}),
                )
            ),
            ModelResponse(text=_plan()),
            ModelResponse(text=_FINDING_JSON),
        ]
    )
    finding = await investigate("T100245", client=fake)
    assert finding.trace_id and set(finding.trace_id) != {"0"}, "tracer provider was not active"

    row = trace_store.get_trace(finding.trace_id)
    assert row is not None, f"no trace row for {finding.trace_id}"
    types = {s["span_type"] for s in row["spans"]}
    assert {"agent", "tool"} <= types, f"span types were {types}"
    synth = next(s for s in row["spans"] if s["step"] == "synthesize")
    payload = json.dumps(synth["payload_out"], ensure_ascii=False)
    assert "update_ssi" in payload
    assert "Handbook §8.4" in payload
