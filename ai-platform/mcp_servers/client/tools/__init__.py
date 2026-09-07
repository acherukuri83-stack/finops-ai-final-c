"""client-server read tools. Docstrings are the exposed descriptions (docs/tool-contracts.md)."""

from __future__ import annotations

from typing import Any

from mcp_servers._common import shape, shape_list
from mcp_servers.client.client import get_enterprise_client, guard
from mcp_servers.client.models import SSI, Account, Client


@guard
async def get_client(client_id: str) -> dict[str, Any]:
    """Client name, type, status, restrictions[]. Use for client-level restrictions."""
    data = await get_enterprise_client().get_json("get_client", f"/clients/{client_id}")
    return shape(Client, data)


@guard
async def get_account(account_id: str) -> dict[str, Any]:
    """Account custodian, status, restrictions[], risk_flags[]. Use to check whether an account can settle. Takes account_id, not client_id."""
    data = await get_enterprise_client().get_json("get_account", f"/accounts/{account_id}")
    return shape(Account, data)


@guard
async def get_ssi(account_id: str, security_type: str | None = None) -> dict[str, Any]:
    """The **current** standing settlement instruction for an account (dtc_participant, agent_bic, valid_from, valid_to, updated_at, updated_by). Use for the current value only."""
    data = await get_enterprise_client().get_json(
        "get_ssi", f"/accounts/{account_id}/ssi", {"securityType": security_type}
    )
    return shape(SSI, data)


@guard
async def get_ssi_history(account_id: str) -> Any:
    """All SSI versions with effective ranges and who changed them. Use when the SSI may have changed recently or when comparing our instruction against a counterparty's."""
    data = await get_enterprise_client().get_json(
        "get_ssi_history", f"/accounts/{account_id}/ssi/history"
    )
    return shape_list(SSI, data)
