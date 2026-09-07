"""ops-server read tools. Docstrings are the exposed descriptions (docs/tool-contracts.md).

`search_knowledge` / `find_incidents` are registered so tool discovery is stable, but
return `NotYetAvailable` until the W2 knowledge slice.
"""

from __future__ import annotations

from typing import Any

from mcp_servers._common import shape_list
from mcp_servers.errors import not_yet_available
from mcp_servers.ops.client import get_enterprise_client, guard
from mcp_servers.ops.models import LogEntry


@guard
async def search_logs(
    query: str,
    trade_id: str | None = None,
    system: str | None = None,
    from_ts: str | None = None,
    to_ts: str | None = None,
) -> Any:
    """Application logs across simulated services. Use with trade_id to find corroborating errors. Returns newest first, max 50."""
    data = await get_enterprise_client().get_json(
        "search_logs",
        "/logs",
        {"q": query, "tradeId": trade_id, "system": system, "from": from_ts, "to": to_ts},
    )
    return shape_list(LogEntry, data)


async def search_knowledge(query: str, k: int = 5) -> dict[str, Any]:
    """Operating procedures and policies, section-level. Returns {doc, section, title, text, score}. Cite as "doc §section". Use after the failure code is known."""
    return not_yet_available("search_knowledge")


async def find_incidents(query: str, k: int = 3) -> dict[str, Any]:
    """Historical incidents {incident_id, summary, root_cause, resolution, similarity}."""
    return not_yet_available("find_incidents")
