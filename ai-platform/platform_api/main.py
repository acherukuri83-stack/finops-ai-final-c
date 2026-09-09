"""ai-platform: one ASGI app hosting the platform API and every MCP server.

With AI_PLATFORM_SPLIT=1 the MCP servers run as separate processes instead (see compose).
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from pydantic import BaseModel

from agent_core.cash import investigate_cash_break
from agent_core.corpactions import investigate_ca_event
from agent_core.developer import investigate_incident, verify_change
from agent_core.loop import investigate
from agent_core.margin import investigate_margin_call
from agent_core.review import review_pr
from agent_core.schemas.finding import Finding
from agent_core.schemas.review import Review
from agent_core.stockloan import investigate_loan
from agent_core.supervisor import investigate_client
from knowledge import retrieval
from mcp_servers._enterprise import EnterpriseError, get_enterprise_client
from mcp_servers.hub import describe, mount_all
from platform_api import cases, store, trace_store
from platform_api.events import Event, get_bus, run_poller
from platform_api.schemas import ConnectionsResponse, KnowledgeHit, TradeRow
from platform_api.settings import settings
from platform_api.telemetry import init_tracing
from platform_api.traces import router as traces_router

init_tracing()
if os.environ.get("CASES_INMEMORY") != "1":
    store.ensure_schema()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Phase D: run the in-process event consumer while the app is up."""
    task: asyncio.Task[None] | None = None
    stop = asyncio.Event()
    if settings.events_enabled and settings.event_bus != "none":
        task = asyncio.create_task(run_poller(get_bus(), stop=stop))
    try:
        yield
    finally:
        stop.set()
        if task is not None:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass


app = FastAPI(title="FinOps AI — platform API", version="0.1.0", lifespan=lifespan)
# The portal is a separate origin (its own Railway domain / :5173 locally).
# CORS_ALLOW_ORIGINS is a comma-separated list; "*" for the public demo.
_origins = [o.strip() for o in os.environ.get("CORS_ALLOW_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
FastAPIInstrumentor.instrument_app(app)
mount_all(app)
app.include_router(traces_router)


class InvestigateRequest(BaseModel):
    trade_id: str | None = None
    client_id: str | None = None  # Phase C: a client-level ask fans out via the Supervisor
    loan_id: str | None = None  # Phase F: a stock-loan question -> the StockLoan specialist
    margin_call_id: str | None = None  # Phase F: a margin call -> the Margin specialist
    cash_break_id: str | None = None  # Phase F: a projected cash break -> the Cash specialist


class DecideRequest(BaseModel):
    decision: str  # APPROVED | REJECTED
    decided_by: str
    role: str = "OPS_ANALYST"


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.get("/connections")
async def connections() -> ConnectionsResponse:
    """Every MCP server, its tools, access tier, and enterprise health — for the portal."""
    return ConnectionsResponse.model_validate(await describe())


@app.post("/investigate")
async def post_investigate(req: InvestigateRequest) -> Finding:
    """Investigate a trade (Settlement specialist) or a whole client (Supervisor fan-out).

    `{"trade_id": ...}` runs the single-trade path; `{"client_id": ...}` decomposes across
    specialists, correlates, and returns one client-level Finding with `sub_findings`.
    """
    if req.client_id:
        return await investigate_client(req.client_id)
    if req.loan_id:
        return await investigate_loan(req.loan_id)
    if req.margin_call_id:
        return await investigate_margin_call(req.margin_call_id)
    if req.cash_break_id:
        return await investigate_cash_break(req.cash_break_id)
    if req.trade_id:
        return await investigate(req.trade_id)
    raise HTTPException(
        status_code=422,
        detail="provide trade_id, client_id, loan_id, margin_call_id, or cash_break_id",
    )


class DiagnoseRequest(BaseModel):
    subject_id: str  # a job id (job-4471) or a service name
    request: str | None = None


class VerifyRequest(BaseModel):
    ticket_id: str  # an applied change ticket (CHG-xxxx)


class CorpActionRequest(BaseModel):
    event_id: str
    account_id: str


@app.post("/corpaction")
async def post_corpaction(req: CorpActionRequest) -> Finding:
    """CorpActions specialist — an account's entitlement for a corporate-action event,
    the held/lent split over the record date, and whether an election is still open."""
    return await investigate_ca_event(req.event_id, req.account_id)


@app.post("/diagnose")
async def post_diagnose(req: DiagnoseRequest) -> Finding:
    """Developer Agent — incident mode. Diagnose a platform fault (failing job / degraded
    service): find the causing change, the blast radius, and revert-vs-fix-forward, and
    propose a change ticket + rerun for a human to approve."""
    return await investigate_incident(req.subject_id, request=req.request)


class ReviewRequest(BaseModel):
    pr_id: str


@app.post("/review")
async def post_review_pr(req: ReviewRequest) -> Review:
    """Developer Agent — PR-review mode. Classify the touched surfaces, run the
    deterministic checks, apply the platform hard rules (write tool w/o approval_id →
    BLOCKER, new action not on an allowlist → MAJOR, PII into a model call → BLOCKER,
    agent-authored scenario → needs a human), and return a structured `Review`. It posts
    comments only — there is no approve/merge tool."""
    return await review_pr(req.pr_id)


@app.post("/verify")
async def post_verify(req: VerifyRequest) -> Finding:
    """Developer Agent — verification mode. Apply a change ticket, re-check the signals
    the diagnosis used, hand residual trades to Settlement, and write an incident on a
    clean fix. On failure it reports — it never proposes a second fix."""
    return await verify_change(req.ticket_id)


@app.post("/events")
async def publish_event(event: Event) -> dict[str, str]:
    """Publish an estate event onto the bus (demo / portal convenience — the simulator is
    the usual publisher). The in-process consumer picks it up and opens a case."""
    if not settings.events_enabled or settings.event_bus == "none":
        raise HTTPException(status_code=409, detail="events are disabled (set EVENTS_ENABLED=1)")
    event_id = await get_bus().publish(event)
    return {"event_id": event_id, "dedup_key": event.dedup_key}


@app.get("/trades")
async def list_trades(
    client: str | None = None,
    account: str | None = None,
    status: str | None = None,
    security: str | None = None,
) -> list[TradeRow]:
    """Proxy to the enterprise trade search — the portal talks only to platform-api."""
    rows = await _enterprise_get(
        "/trades", {"client": client, "account": account, "status": status, "security": security}
    )
    return [TradeRow.model_validate(r) for r in rows]


@app.get("/trades/{trade_id}")
async def get_trade(trade_id: str) -> TradeRow:
    return TradeRow.model_validate(await _enterprise_get(f"/trades/{trade_id}"))


@app.get("/knowledge")
async def knowledge(q: str, k: int = 5) -> list[KnowledgeHit]:
    """Search the SOP / fixture corpus — for the portal's Knowledge tab."""
    return [KnowledgeHit.model_validate(hit) for hit in retrieval.search_knowledge(q, k)]


@app.get("/cases")
async def list_cases() -> list[dict[str, Any]]:
    """All cases, newest first — for the portal's Cases tab."""
    return cases.list_cases()


@app.get("/cases/{case_id}")
async def get_case(case_id: str) -> dict[str, Any]:
    try:
        return cases.get_case(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"no case {case_id}") from exc


@app.post("/approvals/{approval_id}/decide")
async def decide_approval(approval_id: str, req: DecideRequest) -> dict[str, Any]:
    """A human (role `OPS_ANALYST`) approves or rejects a proposed action."""
    try:
        approval = cases.decide(approval_id, req.decision, req.decided_by, req.role)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"no approval {approval_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:  # stitch the decision into the investigation's trace as an `approval` span
        case = cases.get_case(approval["case_id"])
        elapsed = _elapsed_ms(approval.get("created_at"), approval.get("decided_at"))
        trace_store.record_approval_span(
            case.get("trace_id", ""),
            approval_id=approval_id,
            status=approval["status"],
            by=str(approval.get("decided_by") or ""),
            role=str(approval.get("role") or ""),
            elapsed_ms=elapsed,
        )
    except Exception:  # noqa: BLE001 — the decision succeeded; tracing is best-effort
        pass
    return approval


def _elapsed_ms(created: Any, decided: Any) -> int:
    if hasattr(created, "timestamp") and hasattr(decided, "timestamp"):
        return max(0, int((decided.timestamp() - created.timestamp()) * 1000))
    return 0


async def _enterprise_get(path: str, params: dict[str, Any] | None = None) -> Any:
    try:
        return await get_enterprise_client().get_json("platform_api", path, params)
    except EnterpriseError as exc:
        status = 404 if exc.envelope.get("code") == "NOT_FOUND" else 502
        raise HTTPException(status_code=status, detail=exc.envelope) from exc
