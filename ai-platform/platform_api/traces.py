"""The Agent Trace API — backs the portal's Traces screen.

GET  /traces?case_id=&scenario_id=&limit=   list summaries, newest first
GET  /traces/{id}                            trace + parent-ordered spans + payloads + links
GET  /traces/{id}/export                     OpenTelemetry-shaped JSON
POST /traces/{id}/replay                     re-run the investigation, return both traces
GET  /traces/diff?a=&b=                      structured delta between two traces
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException

from agent_core.loop import investigate
from platform_api import trace_store
from platform_api.schemas import (
    EvidenceLink,
    SpanRow,
    TraceDetail,
    TraceDiff,
    TraceReplay,
    TraceSummary,
)

router = APIRouter(prefix="/traces", tags=["traces"])


def _iso(value: Any) -> Any:
    return value.isoformat() if hasattr(value, "isoformat") else value


def _model_from_row[M: TraceSummary | SpanRow](model: type[M], row: dict[str, Any]) -> M:
    fields = model.model_fields
    data = {
        k: (_iso(row[k]) if k in ("started_at", "ended_at") else row[k]) for k in fields if k in row
    }
    return model(**data)


def _ordered_spans(spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_parent: dict[str, list[dict[str, Any]]] = {}
    for s in spans:
        by_parent.setdefault(s.get("parent_span_id") or "", []).append(s)
    ordered: list[dict[str, Any]] = []

    def walk(parent: str) -> None:
        for s in sorted(by_parent.get(parent, []), key=lambda x: x.get("started_at") or ""):
            ordered.append(s)
            walk(s["span_id"])

    walk("")
    seen = {s["span_id"] for s in ordered}
    ordered.extend(s for s in spans if s["span_id"] not in seen)  # orphans, if any
    return ordered


def _resolve_links(
    finding: dict[str, Any] | None, spans: list[dict[str, Any]]
) -> list[EvidenceLink]:
    if not finding:
        return []
    tool_spans = {s["name"].split(".")[-1]: s["span_id"] for s in spans if s["span_type"] == "tool"}
    retrieval_spans = [s for s in spans if s["span_type"] == "retrieval"]
    links: list[EvidenceLink] = []
    for ev in finding.get("evidence", []):
        ref = str(ev.get("ref", ""))
        if ref in tool_spans:
            links.append(EvidenceLink(ref=ref, span_id=tool_spans[ref]))
            continue
        blob = ref.lower()
        hit = next(
            (
                s["span_id"]
                for s in retrieval_spans
                if blob and blob in json.dumps(s.get("attributes", {})).lower()
            ),
            retrieval_spans[0]["span_id"] if retrieval_spans else None,
        )
        if hit:
            links.append(EvidenceLink(ref=ref, span_id=hit))
    return links


@router.get("")
def list_traces(
    case_id: str | None = None, scenario_id: str | None = None, limit: int = 50
) -> list[TraceSummary]:
    rows = trace_store.list_traces(case_id=case_id, scenario_id=scenario_id, limit=limit)
    return [_model_from_row(TraceSummary, r) for r in rows]


@router.get("/diff")
def diff_traces(a: str, b: str) -> TraceDiff:
    ta, tb = trace_store.get_trace(a), trace_store.get_trace(b)
    if ta is None or tb is None:
        raise HTTPException(status_code=404, detail="one or both traces not found")

    def tools(t: dict[str, Any]) -> list[str]:
        return [s["name"] for s in t["spans"] if s["span_type"] == "tool"]

    def actions(t: dict[str, Any]) -> list[str]:
        f = t.get("finding") or {}
        return sorted(x.get("action_type", "") for x in f.get("proposed_actions", []))

    def retrievals(t: dict[str, Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for s in t["spans"]:
            if s["span_type"] != "retrieval":
                continue
            raw = (s.get("attributes") or {}).get("finops.retrieval.results")
            try:
                out.extend(json.loads(raw) if isinstance(raw, str) else raw or [])
            except (TypeError, json.JSONDecodeError):
                pass
        return out

    tools_a, tools_b = tools(ta), tools(tb)
    fa, fb = ta.get("finding") or {}, tb.get("finding") or {}
    return TraceDiff(
        a=a,
        b=b,
        same_scenario=bool(ta["scenario_id"]) and ta["scenario_id"] == tb["scenario_id"],
        root_cause={"a": fa.get("root_cause"), "b": fb.get("root_cause")},
        outcome={"a": fa.get("outcome"), "b": fb.get("outcome")},
        tool_calls_added=[t for t in tools_b if t not in tools_a],
        tool_calls_removed=[t for t in tools_a if t not in tools_b],
        tool_calls_reordered=sorted(tools_a) == sorted(tools_b) and tools_a != tools_b,
        retrieval_delta=[{"only_in": "a", **r} for r in retrievals(ta) if r not in retrievals(tb)]
        + [{"only_in": "b", **r} for r in retrievals(tb) if r not in retrievals(ta)],
        proposed_actions={"a": actions(ta), "b": actions(tb)},
        tokens_delta=(tb["tokens_in"] + tb["tokens_out"]) - (ta["tokens_in"] + ta["tokens_out"]),
        duration_ms_delta=tb["duration_ms"] - ta["duration_ms"],
        cost_usd_delta=round(tb["cost_usd"] - ta["cost_usd"], 6),
    )


@router.get("/{trace_id}")
def get_trace(trace_id: str) -> TraceDetail:
    row = trace_store.get_trace(trace_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"no trace {trace_id}")
    spans = _ordered_spans(row.pop("spans"))
    return TraceDetail(
        **_model_from_row(TraceSummary, row).model_dump(),
        finding=row.get("finding"),
        spans=[_model_from_row(SpanRow, s) for s in spans],
        links=_resolve_links(row.get("finding"), spans),
    )


@router.get("/{trace_id}/export")
def export_trace(trace_id: str) -> dict[str, Any]:
    row = trace_store.get_trace(trace_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"no trace {trace_id}")
    return {
        "trace_id": trace_id,
        "resource": {"service.name": "ai-platform"},
        "meta": {k: row[k] for k in ("request", "scenario_id", "case_id", "outcome", "root_cause")},
        "finding": row.get("finding"),
        "spans": [
            {
                "spanId": s["span_id"],
                "parentSpanId": s.get("parent_span_id") or None,
                "name": s["name"],
                "startTimeUnixNano": _iso(s.get("started_at")),
                "endTimeUnixNano": _iso(s.get("ended_at")),
                "status": s.get("status"),
                "attributes": s.get("attributes", {}),
                "payload": {"in": s.get("payload_in"), "out": s.get("payload_out")},
            }
            for s in row["spans"]
        ],
    }


@router.post("/{trace_id}/replay")
async def replay_trace(trace_id: str) -> TraceReplay:
    row = trace_store.get_trace(trace_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"no trace {trace_id}")
    finding = await investigate(row["subject_id"], scenario_id=row["scenario_id"] or None)
    return TraceReplay(
        original_trace_id=trace_id,
        replay_trace_id=finding.trace_id,
        original_finding=row.get("finding"),
        replay_finding=finding.model_dump(mode="json"),
    )
