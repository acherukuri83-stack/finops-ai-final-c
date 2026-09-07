"""reference-server read tools. Docstrings are the exposed descriptions (docs/tool-contracts.md)."""

from __future__ import annotations

from typing import Any

from mcp_servers._common import shape
from mcp_servers.reference.client import get_enterprise_client, guard
from mcp_servers.reference.models import CalendarDay, Security


@guard
async def get_security(security_id: str) -> dict[str, Any]:
    """isin, cusip, ticker, description, settle_cycle, status. Use to validate identifiers when a reference-data problem is suspected."""
    data = await get_enterprise_client().get_json("get_security", f"/securities/{security_id}")
    return shape(Security, data)


@guard
async def get_market_calendar(date: str, market: str) -> dict[str, Any]:
    """is_business_day, holiday?. Use when a settle_date looks wrong."""
    data = await get_enterprise_client().get_json(
        "get_market_calendar", "/calendar", {"date": date, "market": market}
    )
    return shape(CalendarDay, data)
