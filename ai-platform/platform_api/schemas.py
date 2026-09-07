"""Response shapes for the platform API — used to type the portal's generated client."""

from __future__ import annotations

from pydantic import BaseModel


class ToolInfo(BaseModel):
    name: str
    access: str
    description: str


class ServerInfo(BaseModel):
    name: str
    access: str
    healthy: bool
    tools: list[ToolInfo]


class ConnectionsResponse(BaseModel):
    enterprise_base_url: str
    healthy: bool
    servers: list[ServerInfo]


class TradeRow(BaseModel):
    trade_id: str
    client_id: str | None = None
    account_id: str | None = None
    security_id: str | None = None
    qty: int | None = None
    side: str | None = None
    price: float | None = None
    trade_date: str | None = None
    settle_date: str | None = None
    status: str | None = None
    cpty_id: str | None = None
    booked_at: str | None = None
