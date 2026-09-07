"""Response shapes for reference-server, mirroring docs/tool-contracts.md."""

from __future__ import annotations

from pydantic import BaseModel


class Security(BaseModel):
    security_id: str
    ticker: str | None = None
    isin: str | None = None
    cusip: str | None = None
    description: str | None = None
    settle_cycle: str | None = None
    status: str | None = None


class CalendarDay(BaseModel):
    market: str
    calendar_date: str
    is_business_day: bool | None = None
    holiday_name: str | None = None
