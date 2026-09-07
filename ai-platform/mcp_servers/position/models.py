"""Response shapes for position-server, mirroring docs/tool-contracts.md."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class Position(BaseModel):
    account_id: str
    security_id: str
    as_of: str | None = None
    qty: int | None = None
    available: int | None = None
    pending_deliver: int | None = None
    pending_receive: int | None = None


class BorrowAvailability(BaseModel):
    security_id: str
    available_qty: int | None = None
    rate: float | None = None
    recalls: list[dict[str, Any]] = []
