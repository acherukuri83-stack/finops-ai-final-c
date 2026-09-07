"""Response shapes for client-server, mirroring docs/tool-contracts.md."""

from __future__ import annotations

from pydantic import BaseModel


class Restriction(BaseModel):
    account_id: str
    type: str
    reason: str | None = None
    set_by: str | None = None
    set_at: str | None = None
    active: bool | None = None


class Client(BaseModel):
    client_id: str
    name: str
    type: str | None = None
    status: str | None = None
    restrictions: list[Restriction] = []


class Account(BaseModel):
    account_id: str
    client_id: str
    custodian: str | None = None
    status: str | None = None
    restrictions: list[Restriction] = []
    risk_flags: list[str] = []


class SSI(BaseModel):
    account_id: str
    version: int
    dtc_participant: str | None = None
    agent_bic: str | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    updated_at: str | None = None
    updated_by: str | None = None
