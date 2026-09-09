"""margin-server tools (Phase F). Docstrings are the exposed descriptions.

Reads over the simulated margin book (`mcp_servers.margin.store`). Three writes
(`post_collateral`, `substitute_collateral`, `escalate_margin`) validate an APPROVED
`approval_id`. The call-window rule (meet vs close-out) is code, in
`agent_core/margin.py`.
"""

from __future__ import annotations

from typing import Any

from mcp_servers._common import check_approval
from mcp_servers.margin import store


def _nf(what: str, tool: str) -> dict[str, Any]:
    return {"code": "NOT_FOUND", "message": what, "retryable": False, "tool": tool}


async def get_margin_call(call_id: str) -> Any:
    """A margin call: account, issued, due_by, amount, reason, status."""
    row = store.get_margin_call(call_id)
    return row or _nf(f"no margin call {call_id}", "get_margin_call")


async def list_margin_calls(account_id: str = "") -> Any:
    """Open and met margin calls, filterable by `account_id`."""
    return store.list_margin_calls(account_id or None)


async def get_margin_status(account_id: str) -> Any:
    """Account margin: {requirement, posted, shortfall, as_of}. shortfall > 0 means a call is due."""
    row = store.get_margin_status(account_id)
    return row or _nf(f"no margin status for {account_id}", "get_margin_status")


async def get_collateral(account_id: str = "") -> Any:
    """Posted collateral: [{security_id, market_value, haircut_pct, eligible}]. Value after haircut is what counts toward the requirement."""
    return store.get_collateral(account_id)


async def get_eligibility(security_id: str) -> Any:
    """Collateral eligibility for a security: {eligible, haircut_pct, rating}. A downgrade can make posted collateral ineligible."""
    row = store.get_eligibility(security_id)
    return row or _nf(f"no eligibility for {security_id}", "get_eligibility")


async def post_collateral(call_id: str, security_id: str, amount: str, approval_id: str) -> Any:
    """Post eligible collateral to meet a margin call. Requires an APPROVED approval_id. Only valid while the call's window is still open."""
    denied = check_approval("post_collateral", call_id, approval_id)
    if denied:
        return denied
    row = store.record_action(
        "post_collateral", call_id, {"security_id": security_id, "amount": amount}, approval_id
    )
    _audit(approval_id, f"posted {amount} {security_id} to {call_id} via {row['action_id']}")
    return row


async def substitute_collateral(
    call_id: str, out_security: str, in_security: str, approval_id: str
) -> Any:
    """Swap ineligible / downgraded collateral for eligible. Requires an APPROVED approval_id."""
    denied = check_approval("substitute_collateral", call_id, approval_id)
    if denied:
        return denied
    row = store.record_action(
        "substitute_collateral", call_id, {"out": out_security, "in": in_security}, approval_id
    )
    _audit(approval_id, f"substituted {out_security}->{in_security} on {call_id}")
    return row


async def escalate_margin(call_id: str, reason: str, approval_id: str) -> Any:
    """Escalate a margin call to the credit / close-out desk (used when the window has passed). Requires an APPROVED approval_id."""
    denied = check_approval("escalate_margin", call_id, approval_id)
    if denied:
        return denied
    row = store.record_action("escalate", call_id, {"reason": reason}, approval_id)
    _audit(approval_id, f"escalated {call_id}: {reason}")
    return row


def _audit(approval_id: str, event: str) -> None:
    from platform_api import cases

    approval = cases.get_approval(approval_id)
    if approval:
        cases.log_audit(approval["case_id"], f"executed {event} via {approval_id}")
