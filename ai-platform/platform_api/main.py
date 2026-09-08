"""ai-platform: one ASGI app hosting the platform API and every MCP server.

With AI_PLATFORM_SPLIT=1 the MCP servers run as separate processes instead (see compose).
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from pydantic import BaseModel

from agent_core.loop import investigate
from agent_core.schemas.finding import Finding
from knowledge import retrieval
from mcp_servers._enterprise import EnterpriseError, get_enterprise_client
from mcp_servers.hub import describe, mount_all
from platform_api import cases, store, trace_store
from platform_api.schemas import ConnectionsResponse, KnowledgeHit, TradeRow
from platform_api.settings import settings
from platform_api.telemetry import init_tracing
from platform_api.traces import router as traces_router

init_tracing()
if os.environ.get("CASES_INMEMORY") != "1":
    store.ensure_schema()

app = FastAPI(title="FinOps AI — platform API", version="0.1.0")
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
    trade_id: str


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
    """Run the Investigator: plan -> tool loop -> synthesized Finding, one trace id."""
    return await investigate(req.trade_id)


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
