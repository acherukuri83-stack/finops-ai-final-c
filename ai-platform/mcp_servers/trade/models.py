"""Response shapes for trade-server, mirroring docs/tool-contracts.md."""

from __future__ import annotations

from pydantic import BaseModel


class Attempt(BaseModel):
    at: str
    result: str
    detail: str | None = None


class Trade(BaseModel):
    trade_id: str
    client_id: str
    account_id: str
    security_id: str
    qty: int
    side: str
    price: float | None = None
    trade_date: str
    settle_date: str
    status: str
    cpty_id: str | None = None
    booked_at: str | None = None


class SettlementStatus(BaseModel):
    trade_id: str
    status: str
    failure_code: str | None = None
    failure_detail: str | None = None
    attempts: list[Attempt] = []
    last_attempt_at: str | None = None
