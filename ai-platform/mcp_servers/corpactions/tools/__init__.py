"""corpactions-server tools (Phase F). Docstrings are the exposed descriptions.

Reads over the simulated corporate-actions book (`mcp_servers.corpactions.store`). Three
writes (`submit_election`, `raise_claim`, `escalate_ca`) validate an APPROVED
`approval_id`. The record-date / election-deadline rule is code, in
`agent_core/corpactions.py`.
"""

from __future__ import annotations

from typing import Any

from mcp_servers._common import check_approval
from mcp_servers.corpactions import store


def _nf(what: str, tool: str) -> dict[str, Any]:
    return {"code": "NOT_FOUND", "message": what, "retryable": False, "tool": tool}


async def get_ca_event(event_id: str) -> Any:
    """A corporate-action event: type, record_date, pay_date, gross_rate, elective, election_deadline."""
    row = store.get_ca_event(event_id)
    return row or _nf(f"no CA event {event_id}", "get_ca_event")


async def list_ca_events(security_id: str = "") -> Any:
    """Corporate-action events, filterable by `security_id`."""
    return store.list_ca_events(security_id or None)


async def get_entitlement(account_id: str, event_id: str) -> Any:
    """An account's entitlement for an event: {record_date_qty, held_qty, lent_qty, gross_entitlement}. lent_qty > 0 means part of the position was out on loan over the record date."""
    row = store.get_entitlement(account_id, event_id)
    return row or _nf(f"no entitlement for {account_id} on {event_id}", "get_entitlement")


async def get_election(event_id: str) -> Any:
    """Election options and the deadline for an elective event: {options, default, submitted}."""
    row = store.get_election(event_id)
    return row or _nf(f"no election for {event_id}", "get_election")


async def submit_election(event_id: str, account_id: str, option: str, approval_id: str) -> Any:
    """Submit an election for an elective event. Requires an APPROVED approval_id. Only valid before the election deadline."""
    denied = check_approval("submit_election", event_id, approval_id)
    if denied:
        return denied
    row = store.record_action(
        "submit_election", event_id, {"account_id": account_id, "option": option}, approval_id
    )
    _audit(approval_id, f"submitted election {option} for {account_id} on {event_id}")
    return row


async def raise_claim(event_id: str, account_id: str, qty: str, approval_id: str) -> Any:
    """Raise a manufactured-payment claim against the borrower for the lent portion of an entitlement. Requires an APPROVED approval_id."""
    denied = check_approval("raise_claim", event_id, approval_id)
    if denied:
        return denied
    row = store.record_action(
        "raise_claim", event_id, {"account_id": account_id, "qty": qty}, approval_id
    )
    _audit(approval_id, f"raised claim for {qty} on {event_id} ({account_id})")
    return row


async def escalate_ca(event_id: str, reason: str, approval_id: str) -> Any:
    """Escalate a corporate-action item to asset servicing (used when an election deadline has passed). Requires an APPROVED approval_id."""
    denied = check_approval("escalate_ca", event_id, approval_id)
    if denied:
        return denied
    row = store.record_action("escalate", event_id, {"reason": reason}, approval_id)
    _audit(approval_id, f"escalated {event_id}: {reason}")
    return row


def _audit(approval_id: str, event: str) -> None:
    from platform_api import cases

    approval = cases.get_approval(approval_id)
    if approval:
        cases.log_audit(approval["case_id"], f"executed {event} via {approval_id}")
