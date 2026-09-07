"""Response shapes for ops-server, mirroring docs/tool-contracts.md.

`search_knowledge` and `find_incidents` are registered but not implemented until the
W2 knowledge slice; they return `errors.not_yet_available(...)`.
"""

from __future__ import annotations

from pydantic import BaseModel


class LogEntry(BaseModel):
    ts: str
    svc: str | None = None
    level: str | None = None
    msg: str
    trade_id: str | None = None
