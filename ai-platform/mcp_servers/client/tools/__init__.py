"""client-server tools. Docstrings are the exposed descriptions (docs/tool-contracts.md).

`update_ssi` is a write tool — it validates `approval_id` against the case store before
touching the enterprise (ADR-0001), and is only appropriate when *our* instruction is
confirmed wrong (ADR-0002).
"""

from __future__ import annotations

from typing import Any

from mcp_servers._common import check_approval, shape, shape_list
from mcp_servers.client.client import get_enterprise_client, guard
from mcp_servers.client.models import SSI, Account, Client
from mcp_servers.errors import is_error


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


@guard
async def update_ssi(
    account_id: str, dtc_participant: str, valid_from: str, approval_id: str
) -> Any:
    """Replace the account's current SSI. Requires an APPROVED approval_id. Only appropriate when *our* instruction is confirmed wrong; a counterparty mismatch alone is not grounds."""
    denied = check_approval("update_ssi", account_id, approval_id)
    if denied:
        return denied
    result = await get_enterprise_client().put_json(
        "update_ssi",
        f"/accounts/{account_id}/ssi",
        {"dtcParticipant": dtc_participant, "validFrom": valid_from, "updatedBy": "agent.approved"},
    )
    if is_error(result):
        return result
    from platform_api import cases

    approval = cases.get_approval(approval_id)
    if approval:
        cases.log_audit(
            approval["case_id"],
            f"executed update_ssi {account_id} -> {dtc_participant} via {approval_id}",
        )
    return result
