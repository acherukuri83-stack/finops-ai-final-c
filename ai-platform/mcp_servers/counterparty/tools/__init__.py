"""counterparty-server read tools. Docstrings are the exposed descriptions (docs/tool-contracts.md)."""

from __future__ import annotations

from typing import Any

from mcp_servers._common import shape
from mcp_servers.counterparty.client import get_enterprise_client, guard
from mcp_servers.counterparty.models import Affirmation, Counterparty, CptySSI


@guard
async def get_counterparty(cpty_id: str) -> dict[str, Any]:
    """Counterparty name, status, contacts."""
    data = await get_enterprise_client().get_json("get_counterparty", f"/counterparties/{cpty_id}")
    return shape(Counterparty, data)


@guard
async def get_counterparty_ssi(cpty_id: str) -> dict[str, Any]:
    """The instruction the counterparty has on file for us, with valid_to. Use to check expiry."""
    data = await get_enterprise_client().get_json(
        "get_counterparty_ssi", f"/counterparties/{cpty_id}/ssi"
    )
    return shape(CptySSI, data)


@guard
async def get_affirmation(trade_id: str) -> dict[str, Any]:
    """Whether and how the counterparty affirmed the trade: affirmed, cpty_dtc, affirmed_at. Compare cpty_dtc with our current SSI to detect mismatch."""
    data = await get_enterprise_client().get_json(
        "get_affirmation", f"/trades/{trade_id}/affirmation"
    )
    return shape(Affirmation, data)
