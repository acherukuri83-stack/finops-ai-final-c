"""position-server read tools. Docstrings are the exposed descriptions (docs/tool-contracts.md)."""

from __future__ import annotations

from typing import Any

from mcp_servers._common import shape
from mcp_servers.position.client import get_enterprise_client, guard
from mcp_servers.position.models import BorrowAvailability, Position


@guard
async def get_position(
    account_id: str, security_id: str, as_of: str | None = None
) -> dict[str, Any]:
    """qty, available, pending_deliver, pending_receive. Use for delivery shortfalls."""
    data = await get_enterprise_client().get_json(
        "get_position",
        "/positions",
        {"account": account_id, "security": security_id, "asOf": as_of},
    )
    return shape(Position, data)


@guard
async def get_borrow_availability(security_id: str) -> dict[str, Any]:
    """available_qty, rate, recalls[]. Use only after a shortfall is confirmed."""
    data = await get_enterprise_client().get_json(
        "get_borrow_availability", f"/borrow/{security_id}"
    )
    return shape(BorrowAvailability, data)
