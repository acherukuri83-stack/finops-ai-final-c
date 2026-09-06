"""ai-platform: one ASGI app hosting the platform API and (from W1 PR3) every MCP server.

With AI_PLATFORM_SPLIT=1 the MCP servers run as separate processes instead (see compose).
"""

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from platform_api.settings import settings
from platform_api.telemetry import init_tracing

init_tracing()

app = FastAPI(title="FinOps AI — platform API", version="0.1.0")
FastAPIInstrumentor.instrument_app(app)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


# W1 PR3 mounts MCP servers here when not split, e.g.:
#   from mcp_servers.trade.server import mcp as trade_mcp
#   app.mount("/mcp/trade", trade_mcp.sse_app())
