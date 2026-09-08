"""Trace API — shape, span ordering, evidence links, and the diff math — with the
store monkeypatched (no DB). The real round-trip is a `-m contract` test.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from platform_api import trace_store
from platform_api import traces as traces_mod

app = FastAPI()
app.include_router(traces_mod.router)
client = TestClient(app)


def _trace(
    trace_id: str, *, spans: list[dict[str, Any]], finding: dict[str, Any]
) -> dict[str, Any]:
    return {
        "trace_id": trace_id,
        "subject_type": "trade",
        "subject_id": "T100245",
        "request": "Investigate why trade T100245 failed settlement.",
        "scenario_id": "1",
        "case_id": "CS-0001",
        "agent": "investigator",
        "outcome": finding.get("outcome", "RESOLVED_CAUSE"),
        "root_cause": finding.get("root_cause", ""),
        "status": "COMPLETE",
        "started_at": None,
        "ended_at": None,
        "duration_ms": 14200,
        "tool_calls": sum(s["span_type"] == "tool" for s in spans),
        "retrievals": sum(s["span_type"] == "retrieval" for s in spans),
        "model_calls": 3,
        "tokens_in": 5000,
        "tokens_out": 1800,
        "cost_usd": 0.042,
        "finding": finding,
        "spans": spans,
    }


def _span(sid: str, parent: str, name: str, stype: str, **attrs: Any) -> dict[str, Any]:
    return {
        "span_id": sid,
        "trace_id": "t",
        "parent_span_id": parent,
        "name": name,
        "span_type": stype,
        "agent": "investigator",
        "step": attrs.pop("step", ""),
        "started_at": attrs.pop("started_at", sid),
        "ended_at": None,
        "duration_ms": 10,
        "status": "OK",
        "attributes": attrs,
        "payload_in": None,
        "payload_out": None,
    }


_SPANS = [
    _span("root", "", "investigate", "agent", started_at="01"),
    _span("s_tool", "root", "trade.get_ssi_history", "tool", started_at="02"),
    _span(
        "s_ret",
        "root",
        "ops.find_incidents",
        "retrieval",
        started_at="03",
        **{"finops.retrieval.results": '[{"incident_id": "INC-1001", "score": 0.88}]'},
    ),
]
_FINDING = {
    "outcome": "RESOLVED_CAUSE",
    "root_cause": "COUNTERPARTY_INSTRUCTION_STALE",
    "evidence": [
        {"kind": "tool", "ref": "get_ssi_history"},
        {"kind": "incident", "ref": "INC-1001"},
    ],
    "proposed_actions": [{"action_type": "resubmit_settlement"}],
}


@pytest.fixture(autouse=True)
def _stub_store(monkeypatch: pytest.MonkeyPatch) -> None:
    a = _trace("aaaa", spans=_SPANS, finding=_FINDING)
    b = _trace(
        "bbbb",
        spans=[_SPANS[0], _span("s_tool2", "root", "trade.get_trade", "tool")],
        finding={
            **_FINDING,
            "root_cause": "CLIENT_SSI_STALE",
            "proposed_actions": [
                {"action_type": "update_ssi"},
                {"action_type": "resubmit_settlement"},
            ],
        },
    )
    b["tokens_in"], b["tokens_out"], b["duration_ms"], b["cost_usd"] = 6000, 2000, 15000, 0.05
    store = {"aaaa": a, "bbbb": b}
    monkeypatch.setattr(trace_store, "get_trace", lambda tid: store.get(tid))
    monkeypatch.setattr(
        trace_store,
        "list_traces",
        lambda **_k: [{k: v for k, v in t.items() if k != "spans"} for t in store.values()],
    )


def test_list_traces_returns_summaries() -> None:
    r = client.get("/traces")
    assert r.status_code == 200
    assert {t["trace_id"] for t in r.json()} == {"aaaa", "bbbb"}
    assert "spans" not in r.json()[0]


def test_get_trace_orders_spans_and_resolves_evidence_links() -> None:
    r = client.get("/traces/aaaa")
    assert r.status_code == 200
    body = r.json()
    assert [s["span_id"] for s in body["spans"]] == ["root", "s_tool", "s_ret"]
    links = {lk["ref"]: lk["span_id"] for lk in body["links"]}
    assert links["get_ssi_history"] == "s_tool"
    assert links["INC-1001"] == "s_ret"


def test_get_trace_404() -> None:
    assert client.get("/traces/nope").status_code == 404


def test_export_is_otel_shaped() -> None:
    body = client.get("/traces/aaaa/export").json()
    assert body["trace_id"] == "aaaa"
    assert {s["spanId"] for s in body["spans"]} == {"root", "s_tool", "s_ret"}
    assert body["spans"][0]["parentSpanId"] is None


def test_diff_reports_the_deltas() -> None:
    d = client.get("/traces/diff?a=aaaa&b=bbbb").json()
    assert d["same_scenario"] is True
    assert d["root_cause"] == {"a": "COUNTERPARTY_INSTRUCTION_STALE", "b": "CLIENT_SSI_STALE"}
    assert d["tool_calls_added"] == ["trade.get_trade"]
    assert d["tool_calls_removed"] == ["trade.get_ssi_history"]
    assert d["proposed_actions"]["b"] == ["resubmit_settlement", "update_ssi"]
    assert d["tokens_delta"] == (6000 + 2000) - (5000 + 1800)
    assert d["duration_ms_delta"] == 15000 - 14200


def test_diff_404_when_a_trace_is_missing() -> None:
    assert client.get("/traces/diff?a=aaaa&b=zzzz").status_code == 404


# --- contract: a real investigation persists a full trace -----------------------

import json  # noqa: E402
import os  # noqa: E402
from collections.abc import Iterator  # noqa: E402

from agent_core.loop import investigate  # noqa: E402
from agent_core.reasoning.model_client import FakeModelClient, ModelResponse  # noqa: E402
from platform_api.settings import settings  # noqa: E402


@pytest.fixture
def _sql_traces() -> Iterator[None]:
    if not os.environ.get("ENTERPRISE_BASE_URL"):
        pytest.skip("needs the running stack + seeded Postgres")
    from mcp_servers import _enterprise
    from mcp_servers._enterprise import HttpEnterpriseClient
    from platform_api import cases, store
    from platform_api.telemetry import init_tracing

    settings.traces_enabled = True
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


@pytest.mark.contract
async def test_a_real_investigation_persists_every_span_type(_sql_traces: None) -> None:
    from platform_api import trace_store

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
    assert "update_ssi" in json.dumps(synth["payload_out"])
    assert "Handbook §8.4" in json.dumps(synth["payload_out"])
