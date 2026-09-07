"""ops-server read tools. Docstrings are the exposed descriptions (docs/tool-contracts.md).

`search_logs` goes through the enterprise `/logs` endpoint. `search_knowledge` /
`find_incidents` query the pgvector corpus directly (Python-tier — the Java tier has no
knowledge store); run `python -m knowledge.ingest` first.
"""

from __future__ import annotations

from typing import Any

from knowledge import retrieval
from mcp_servers._common import shape_list
from mcp_servers.ops.client import get_enterprise_client, guard
from mcp_servers.ops.models import LogEntry


@guard
async def search_logs(
    query: str = "",
    trade_id: str | None = None,
    system: str | None = None,
    from_ts: str | None = None,
    to_ts: str | None = None,
) -> Any:
    """Application logs across simulated services. Use with trade_id to find corroborating errors. Returns newest first, max 50."""
    data = await get_enterprise_client().get_json(
        "search_logs",
        "/logs",
        {"q": query or None, "tradeId": trade_id, "system": system, "from": from_ts, "to": to_ts},
    )
    return shape_list(LogEntry, data)


async def search_knowledge(query: str, k: int = 5) -> list[dict[str, Any]]:
    """Operating procedures and policies, section-level. Returns {doc, section, title, text, score}. Cite as "doc §section". Use after the failure code is known."""
    return retrieval.search_knowledge(query, k)


async def find_incidents(query: str, k: int = 3) -> list[dict[str, Any]]:
    """Historical incidents {incident_id, summary, root_cause, resolution, similarity}."""
    return retrieval.find_incidents(query, k)
