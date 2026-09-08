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
