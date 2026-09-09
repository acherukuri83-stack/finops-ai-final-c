"""cash-server tools (Phase F). Docstrings are the exposed descriptions.

Reads over the simulated cash & funding book (`mcp_servers.cash.store`). Three writes
(`arrange_funding`, `move_cash`, `escalate_cash`) validate an APPROVED `approval_id`. The
funding-cutoff rule (fund vs escalate) is code, in `agent_core/cash.py`.
"""

from __future__ import annotations

from typing import Any

from mcp_servers._common import check_approval
from mcp_servers.cash import store


def _nf(what: str, tool: str) -> dict[str, Any]:
    return {"code": "NOT_FOUND", "message": what, "retryable": False, "tool": tool}


async def get_cash_break(break_id: str) -> Any:
    """A projected cash break: account, currency, projected_close (negative = shortfall), min_buffer, funding_cutoff, driver."""
    row = store.get_cash_break(break_id)
    return row or _nf(f"no cash break {break_id}", "get_cash_break")


async def list_cash_breaks(account_id: str = "") -> Any:
    """Open projected cash breaks, filterable by `account_id`."""
    return store.list_cash_breaks(account_id or None)


async def get_funding_ladder(account_id: str, currency: str) -> Any:
    """The timed inflows / outflows for an account+currency today: [{time, flow, kind}]. The projected close is opening + sum(flow)."""
    return store.get_funding_ladder(account_id, currency)


async def get_facility(account_id: str, currency: str) -> Any:
    """The credit facility for an account+currency: {limit, drawn, headroom}. headroom is what a draw can still pull."""
    row = store.get_facility(account_id, currency)
    return row or _nf(f"no facility for {account_id} {currency}", "get_facility")


async def arrange_funding(break_id: str, source: str, amount: str, approval_id: str) -> Any:
    """Cover a projected shortfall by drawing on a facility or an FX swap (`source`). Requires an APPROVED approval_id. Only valid before the currency funding cutoff."""
    denied = check_approval("arrange_funding", break_id, approval_id)
    if denied:
        return denied
    row = store.record_action(
        "arrange_funding", break_id, {"source": source, "amount": amount}, approval_id
    )
    _audit(approval_id, f"arranged {amount} funding for {break_id} via {source}")
    return row


async def move_cash(
    break_id: str, from_account: str, to_account: str, amount: str, approval_id: str
) -> Any:
    """Sweep surplus cash between the client's accounts to cover a shortfall. Requires an APPROVED approval_id."""
    denied = check_approval("move_cash", break_id, approval_id)
    if denied:
        return denied
    row = store.record_action(
        "move_cash",
        break_id,
        {"from": from_account, "to": to_account, "amount": amount},
        approval_id,
    )
    _audit(approval_id, f"moved {amount} {from_account}->{to_account} for {break_id}")
    return row


async def escalate_cash(break_id: str, reason: str, approval_id: str) -> Any:
    """Escalate a cash break to treasury / the client (used when the funding cutoff has passed — overdraft / next-day). Requires an APPROVED approval_id."""
    denied = check_approval("escalate_cash", break_id, approval_id)
    if denied:
        return denied
    row = store.record_action("escalate", break_id, {"reason": reason}, approval_id)
    _audit(approval_id, f"escalated {break_id}: {reason}")
    return row


def _audit(approval_id: str, event: str) -> None:
    from platform_api import cases

    approval = cases.get_approval(approval_id)
    if approval:
        cases.log_audit(approval["case_id"], f"executed {event} via {approval_id}")
