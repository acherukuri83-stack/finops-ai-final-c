"""stockloan-server tools (Phase F core slice). Docstrings are the exposed descriptions.

Reads over the simulated securities-lending book (`mcp_servers.stockloan.store`). The
three writes (`initiate_recall`, `rerate_loan`, `book_buy_in`) validate an APPROVED
`approval_id` in the tool (ADR-0001). The recall-notice-window rule that decides recall
vs buy-in is code, in `agent_core/stockloan.py`, not a tool and not a prompt.
"""

from __future__ import annotations

from typing import Any

from mcp_servers._common import check_approval
from mcp_servers.stockloan import store


def _not_found(what: str, tool: str) -> dict[str, Any]:
    return {"code": "NOT_FOUND", "message": what, "retryable": False, "tool": tool}


async def get_loan(loan_id: str) -> Any:
    """A stock-loan record: account, security, counterparty, qty, rate_bps, open, return_needed_by."""
    row = store.get_loan(loan_id)
    return row or _not_found(f"no loan {loan_id}", "get_loan")


async def list_loans(security_id: str = "", account_id: str = "") -> Any:
    """Open and closed loans, filterable by `security_id` and/or `account_id`."""
    return store.list_loans(security_id or None, account_id or None)


async def get_recall(loan_id: str) -> Any:
    """The recall on a loan if one has been issued: {status, issued_at, due_date, satisfied}. NOT_FOUND if none."""
    row = store.get_recall(loan_id)
    return row or _not_found(f"no recall for {loan_id}", "get_recall")


async def get_rerate_history(loan_id: str) -> Any:
    """Rate changes on a loan: [{at, from_bps, to_bps, by}]."""
    return store.get_rerate_history(loan_id)


async def get_lending_availability(security_id: str) -> Any:
    """Street lending availability for a security: {lendable_qty, on_loan_qty, gc_rate_bps}. Compare gc_rate_bps with a loan's rate_bps to spot an off-market rate."""
    row = store.get_lending_availability(security_id)
    return row or _not_found(f"no availability for {security_id}", "get_lending_availability")


async def initiate_recall(loan_id: str, qty: str, reason: str, approval_id: str) -> Any:
    """Issue a recall to the borrower for `qty` of the loan. Requires an APPROVED approval_id. Only valid while the recall notice window is still open — otherwise a buy-in is forced."""
    denied = check_approval("initiate_recall", loan_id, approval_id)
    if denied:
        return denied
    row = store.record_action("recall", loan_id, {"qty": qty, "reason": reason}, approval_id)
    _audit(approval_id, f"initiated recall {row['action_id']} on {loan_id} ({qty})")
    return row


async def rerate_loan(loan_id: str, new_rate_bps: str, reason: str, approval_id: str) -> Any:
    """Change a loan's fee rate. Requires an APPROVED approval_id."""
    denied = check_approval("rerate_loan", loan_id, approval_id)
    if denied:
        return denied
    row = store.record_action(
        "rerate", loan_id, {"new_rate_bps": new_rate_bps, "reason": reason}, approval_id
    )
    _audit(approval_id, f"rerated {loan_id} -> {new_rate_bps}bps via {row['action_id']}")
    return row


async def book_buy_in(loan_id: str, qty: str, reason: str, approval_id: str) -> Any:
    """Book a buy-in to cover a loan whose recall window has passed. Requires an APPROVED approval_id."""
    denied = check_approval("book_buy_in", loan_id, approval_id)
    if denied:
        return denied
    row = store.record_action("buy_in", loan_id, {"qty": qty, "reason": reason}, approval_id)
    _audit(approval_id, f"booked buy-in {row['action_id']} for {loan_id} ({qty})")
    return row


def _audit(approval_id: str, event: str) -> None:
    from platform_api import cases

    approval = cases.get_approval(approval_id)
    if approval:
        cases.log_audit(approval["case_id"], f"executed {event} via {approval_id}")
