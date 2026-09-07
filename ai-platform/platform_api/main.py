"""ai-platform: one ASGI app hosting the platform API and every MCP server.

With AI_PLATFORM_SPLIT=1 the MCP servers run as separate processes instead (see compose).
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from pydantic import BaseModel

from agent_core.schemas.finding import Finding
from agent_core.skeleton import investigate
from mcp_servers._enterprise import EnterpriseError, get_enterprise_client
from mcp_servers.hub import describe, mount_all
from platform_api.schemas import ConnectionsResponse, TradeRow
from platform_api.settings import settings
from platform_api.telemetry import init_tracing

init_tracing()

app = FastAPI(title="FinOps AI — platform API", version="0.1.0")
FastAPIInstrumentor.instrument_app(app)
mount_all(app)


class InvestigateRequest(BaseModel):
    trade_id: str


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.get("/connections")
async def connections() -> ConnectionsResponse:
    """Every MCP server, its tools, access tier, and enterprise health — for the portal."""
    return ConnectionsResponse.model_validate(await describe())


@app.post("/investigate")
async def post_investigate(req: InvestigateRequest) -> Finding:
    """Walking skeleton: one MCP tool call, a minimal Finding, one trace id."""
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


async def _enterprise_get(path: str, params: dict[str, Any] | None = None) -> Any:
    try:
        return await get_enterprise_client().get_json("platform_api", path, params)
    except EnterpriseError as exc:
        status = 404 if exc.envelope.get("code") == "NOT_FOUND" else 502
        raise HTTPException(status_code=status, detail=exc.envelope) from exc
