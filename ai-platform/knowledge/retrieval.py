"""What `ops.search_knowledge` / `ops.find_incidents` call. Embeds the query, hits pgvector.

Returns the exact shapes from docs/tool-contracts.md:
- search_knowledge -> [{doc, section, title, text, score}]
- find_incidents   -> [{incident_id, summary, root_cause, resolution, similarity}]
"""

from __future__ import annotations

from typing import Any

from knowledge import store
from knowledge.embeddings import embed_one


def search_knowledge(query: str, k: int = 5) -> list[dict[str, Any]]:
    with store.engine().connect() as conn:
        rows = store.search(conn, embed_one(query), k, kinds=["sop", "fixture"])
    return [
        {
            "doc": r["doc"],
            "section": r["section"],
            "title": r["title"],
            "text": r["text"],
            "score": r["score"],
        }
        for r in rows
    ]


def find_incidents(query: str, k: int = 3) -> list[dict[str, Any]]:
    with store.engine().connect() as conn:
        rows = store.search(conn, embed_one(query), k, kinds=["incident"])
    return [
        {
            "incident_id": r["incident_id"],
            "summary": r["summary"],
            "root_cause": r["root_cause"],
            "resolution": r["resolution"],
            "similarity": r["score"],
        }
        for r in rows
    ]
