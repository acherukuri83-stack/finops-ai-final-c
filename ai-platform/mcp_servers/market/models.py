"""Response shapes for market-server, mirroring docs/tool-contracts.md."""

from __future__ import annotations

from pydantic import BaseModel


class Price(BaseModel):
    security_id: str
    price_date: str | None = None
    close_price: float | None = None
