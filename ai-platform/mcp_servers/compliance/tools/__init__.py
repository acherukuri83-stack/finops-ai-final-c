"""compliance-server read tools. Docstrings are the exposed descriptions (docs/tool-contracts.md)."""

from __future__ import annotations

from typing import Any

from mcp_servers._common import shape, shape_list
from mcp_servers.compliance.client import get_enterprise_client, guard
from mcp_servers.compliance.models import Restriction, Screening


@guard
async def get_restrictions(account_id: str) -> Any:
    """Active restrictions with reason, set_by, set_at. A settlement restriction means the trade cannot settle regardless of SSI."""
    data = await get_enterprise_client().get_json(
        "get_restrictions", "/restrictions", {"account": account_id}
    )
    return shape_list(Restriction, data)


@guard
async def get_screening_result(client_id: str) -> dict[str, Any]:
    """Latest sanctions screening status. Phase A data is always CLEAR."""
    data = await get_enterprise_client().get_json(
        "get_screening_result", "/screening", {"client": client_id}
    )
    return shape(Screening, data)
