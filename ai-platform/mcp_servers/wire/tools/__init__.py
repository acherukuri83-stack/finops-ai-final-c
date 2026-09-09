"""wire-server tools (Phase B — Wires). Docstrings are the exposed descriptions.

Reads over the simulated outgoing-wire book plus four approval-gated writes
(`route_to_reviewer`, `add_standing_instruction`, `reschedule_value_date`,
`open_compliance_referral`). **There is no `release_wire` tool** — release is a
human-only action in the portal (`WIRE_REVIEWER` role); a test asserts it is absent from
every discovered tool list. The cutoff / screening / new-beneficiary rules that decide the
action are code, in `agent_core/wire.py`, not a tool and not a prompt.
"""

from __future__ import annotations

from typing import Any

from mcp_servers._common import check_approval
from mcp_servers.wire import store


def _not_found(what: str, tool: str) -> dict[str, Any]:
    return {"code": "NOT_FOUND", "message": what, "retryable": False, "tool": tool}


async def get_wire(wire_id: str) -> Any:
    """An outgoing wire: client, account, currency, amount, beneficiary, beneficiary_account, value_date, status, hold_reason."""
    row = store.get_wire(wire_id)
    return row or _not_found(f"no wire {wire_id}", "get_wire")


async def list_wires(client_id: str = "", status: str = "") -> Any:
    """Wires filterable by `client_id` and/or `status` (e.g. HELD). Returns the same shape as get_wire, one row each."""
    return store.list_wires(client_id or None, status or None)


async def get_wire_audit_trail(wire_id: str) -> Any:
    """The wire's event history: [{at, actor, event}] — receipt, hold, cutoff, screening."""
    return store.get_wire_audit_trail(wire_id)


async def get_standing_instructions(client_id: str) -> Any:
    """A client's approved wire beneficiaries: [{beneficiary, beneficiary_account, added_at, added_by}]. A beneficiary_account not on this list is a new beneficiary and needs reviewer sign-off."""
    return store.get_standing_instructions(client_id)


async def get_approval_queue() -> Any:
    """Wires currently routed to a reviewer: [{wire_id, routed_at, reviewer, packet}]."""
    return store.get_approval_queue()


async def get_cutoff(currency: str) -> Any:
    """The same-day value cutoff for a currency: {currency, cutoff (HH:MM local), tz, network}. Compare with the platform clock — past it, the value date must move, it cannot be a same-day release."""
    row = store.get_cutoff(currency)
    return row or _not_found(f"no cutoff for {currency}", "get_cutoff")


async def get_wire_screening(client_id: str) -> Any:
    """Latest sanctions screening for the client: {status: CLEAR | HIT, matched_list, checked_at}. A HIT freezes all remediation — the only action is a compliance referral."""
    return store.get_wire_screening(client_id)


async def get_available_balance(account_id: str, currency: str) -> Any:
    """Available balance on an account in a currency: {account_id, currency, available}. If it is below the wire amount the wire cannot be released until funding is arranged."""
    row = store.get_available_balance(account_id, currency)
    return row or _not_found(f"no balance for {account_id} {currency}", "get_available_balance")


async def route_to_reviewer(wire_id: str, reason: str, packet: str, approval_id: str) -> Any:
    """Route a held wire to a WIRE_REVIEWER with a review packet (evidence + audit-message draft + cutoff warning). Requires an APPROVED approval_id. The agent is the maker; it never releases."""
    denied = check_approval("route_to_reviewer", wire_id, approval_id)
    if denied:
        return denied
    row = store.record_action(
        "route_to_reviewer", wire_id, {"reason": reason, "packet": packet}, approval_id
    )
    _audit(approval_id, f"routed {wire_id} to reviewer ({row['action_id']})")
    return row


async def add_standing_instruction(
    client_id: str, beneficiary: str, beneficiary_account: str, approval_id: str
) -> Any:
    """Add a beneficiary to a client's standing wire instructions so future wires to it are not held as new. Requires an APPROVED approval_id. A separate action from routing the wire in front of us."""
    denied = check_approval("add_standing_instruction", client_id, approval_id)
    if denied:
        return denied
    row = store.record_action(
        "add_standing_instruction",
        client_id,
        {"beneficiary": beneficiary, "beneficiary_account": beneficiary_account},
        approval_id,
    )
    _audit(approval_id, f"added standing instruction for {client_id} -> {beneficiary_account}")
    return row


async def reschedule_value_date(
    wire_id: str, new_value_date: str, reason: str, approval_id: str
) -> Any:
    """Move a wire's value date (used when the same-day cutoff has passed — never a forced same-day release). Requires an APPROVED approval_id."""
    denied = check_approval("reschedule_value_date", wire_id, approval_id)
    if denied:
        return denied
    row = store.record_action(
        "reschedule_value_date",
        wire_id,
        {"new_value_date": new_value_date, "reason": reason},
        approval_id,
    )
    _audit(approval_id, f"rescheduled {wire_id} value date -> {new_value_date}")
    return row


async def open_compliance_referral(wire_id: str, reason: str, approval_id: str) -> Any:
    """Open a compliance referral on a wire (a screening hit freezes everything else). Requires an APPROVED approval_id."""
    denied = check_approval("open_compliance_referral", wire_id, approval_id)
    if denied:
        return denied
    row = store.record_action("compliance_referral", wire_id, {"reason": reason}, approval_id)
    _audit(approval_id, f"opened compliance referral on {wire_id}")
    return row


def _audit(approval_id: str, event: str) -> None:
    from platform_api import cases

    approval = cases.get_approval(approval_id)
    if approval:
        cases.log_audit(approval["case_id"], f"executed {event} via {approval_id}")
