"""Response shapes for the platform API — used to type the portal's generated client."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ToolInfo(BaseModel):
    name: str
    access: str
    description: str


class ServerInfo(BaseModel):
    name: str
    access: str
    healthy: bool
    tools: list[ToolInfo]


class ConnectionsResponse(BaseModel):
    enterprise_base_url: str
    healthy: bool
    servers: list[ServerInfo]


class KnowledgeHit(BaseModel):
    doc: str
    section: str = ""
    title: str = ""
    text: str
    score: float


class TradeRow(BaseModel):
    trade_id: str
    client_id: str | None = None
    account_id: str | None = None
    security_id: str | None = None
    qty: int | None = None
    side: str | None = None
    price: float | None = None
    trade_date: str | None = None
    settle_date: str | None = None
    status: str | None = None
    cpty_id: str | None = None
    booked_at: str | None = None


# --- Agent Trace screen ----------------------------------------------------


class TraceSummary(BaseModel):
    trace_id: str
    subject_type: str = ""
    subject_id: str = ""
    request: str = ""
    scenario_id: str = ""
    case_id: str = ""
    agent: str = ""
    outcome: str = ""
    root_cause: str = ""
    status: str = ""
    started_at: str | None = None
    ended_at: str | None = None
    duration_ms: int = 0
    tool_calls: int = 0
    retrievals: int = 0
    model_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0


class SpanRow(BaseModel):
    span_id: str
    trace_id: str
    parent_span_id: str = ""
    name: str
    span_type: str = ""
    agent: str = ""
    step: str = ""
    started_at: str | None = None
    ended_at: str | None = None
    duration_ms: int = 0
    status: str = ""
    attributes: dict[str, Any] = {}
    payload_in: Any = None
    payload_out: Any = None


class EvidenceLink(BaseModel):
    ref: str
    span_id: str


class TraceDetail(TraceSummary):
    finding: dict[str, Any] | None = None
    spans: list[SpanRow] = []
    links: list[EvidenceLink] = []


class TraceReplay(BaseModel):
    original_trace_id: str
    replay_trace_id: str
    original_finding: dict[str, Any] | None = None
    replay_finding: dict[str, Any] | None = None


class TraceDiff(BaseModel):
    a: str
    b: str
    same_scenario: bool
    root_cause: dict[str, str | None]
    outcome: dict[str, str | None]
    tool_calls_added: list[str] = []
    tool_calls_removed: list[str] = []
    tool_calls_reordered: bool = False
    retrieval_delta: list[dict[str, Any]] = []
    proposed_actions: dict[str, list[str]]
    tokens_delta: int = 0
    duration_ms_delta: int = 0
    cost_usd_delta: float = 0.0
