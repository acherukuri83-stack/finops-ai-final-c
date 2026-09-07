"""market-server read tools. Docstrings are the exposed descriptions (docs/tool-contracts.md)."""

from __future__ import annotations

from typing import Any

from mcp_servers._common import shape
from mcp_servers.market.client import get_enterprise_client, guard
from mcp_servers.market.models import Price


@guard
async def get_price(security_id: str, as_of: str | None = None) -> dict[str, Any]:
    """Close/last price. Realism only in Phase A; rarely needed for settlement investigations."""
    data = await get_enterprise_client().get_json(
        "get_price", f"/prices/{security_id}", {"asOf": as_of}
    )
    return shape(Price, data)
