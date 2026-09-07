"""Response shapes for compliance-server, mirroring docs/tool-contracts.md."""

from __future__ import annotations

from pydantic import BaseModel


class Restriction(BaseModel):
    account_id: str
    type: str
    reason: str | None = None
    set_by: str | None = None
    set_at: str | None = None
    active: bool | None = None


class Screening(BaseModel):
    client_id: str
    status: str
    checked_at: str | None = None
