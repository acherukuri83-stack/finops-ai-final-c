"""Response shapes for counterparty-server, mirroring docs/tool-contracts.md."""

from __future__ import annotations

from pydantic import BaseModel


class Counterparty(BaseModel):
    cpty_id: str
    name: str
    status: str | None = None
    contacts: list[str] = []


class CptySSI(BaseModel):
    cpty_id: str
    dtc_participant: str | None = None
    valid_to: str | None = None


class Affirmation(BaseModel):
    trade_id: str
    cpty_id: str | None = None
    affirmed: bool | None = None
    cpty_dtc: str | None = None
    affirmed_at: str | None = None
