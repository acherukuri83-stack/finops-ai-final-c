"""trade-server tools. Docstrings are the exposed descriptions (docs/tool-contracts.md).

Write tools (`resubmit_settlement`, `cancel_trade`) validate `approval_id` against the
case store *inside the tool* before touching the enterprise (ADR-0001).
"""

from __future__ import annotations

from typing import Any

from mcp_servers._common import check_approval, shape, shape_list
from mcp_servers.errors import is_error
from mcp_servers.trade.client import get_enterprise_client, guard
from mcp_servers.trade.models import SettlementStatus, Trade


@guard
async def get_trade(trade_id: str) -> dict[str, Any]:
    """Full trade record: client, account, security, qty, side, dates, status, counterparty. Use first for any trade question."""
    data = await get_enterprise_client().get_json("get_trade", f"/trades/{trade_id}")
    return shape(Trade, data)


@guard
async def get_settlement_status(trade_id: str) -> dict[str, Any]:
    """Settlement state, failure_code, failure_detail, attempts[] with timestamps. Use to learn *why* a trade is not settled. Returns failure_code=null if never attempted."""
    data = await get_enterprise_client().get_json(
        "get_settlement_status", f"/trades/{trade_id}/settlement"
    )
    return shape(SettlementStatus, data)


@guard
async def find_trades(
    client_id: str | None = None,
    account_id: str | None = None,
    status: str | None = None,
    security_id: str | None = None,
    trade_date: str | None = None,
    settle_date: str | None = None,
) -> Any:
    """Search trades by filters. Use to find related trades (same client, same security, same day) e.g. for duplicates or blast radius. Do not use to fetch a known trade_id — use get_trade."""
    data = await get_enterprise_client().get_json(
        "find_trades",
        "/trades",
        {
            "client": client_id,
            "account": account_id,
            "status": status,
            "security": security_id,
            "tradeDate": trade_date,
            "settleDate": settle_date,
        },
    )
    return shape_list(Trade, data)


@guard
async def resubmit_settlement(trade_id: str, approval_id: str) -> Any:
    """Resubmit a failed trade for settlement using current instructions. Requires an APPROVED approval_id. Does not change any SSI."""
    denied = check_approval("resubmit_settlement", trade_id, approval_id)
    if denied:
        return denied
    result = await get_enterprise_client().post_json(
        "resubmit_settlement", f"/trades/{trade_id}/resubmit", {"note": f"approval {approval_id}"}
    )
    return _audited(result, approval_id, f"executed resubmit_settlement {trade_id}")


@guard
async def cancel_trade(trade_id: str, reason: str, approval_id: str) -> Any:
    """Cancel a trade (e.g. a duplicate booking). Requires an APPROVED approval_id. Irreversible."""
    denied = check_approval("cancel_trade", trade_id, approval_id)
    if denied:
        return denied
    result = await get_enterprise_client().post_json(
        "cancel_trade", f"/trades/{trade_id}/cancel", {"reason": reason}
    )
    return _audited(result, approval_id, f"executed cancel_trade {trade_id} ({reason})")


def _audited(result: Any, approval_id: str, event: str) -> Any:
    from platform_api import cases

    if is_error(result):
        return result
    approval = cases.get_approval(approval_id)
    if approval:
        cases.log_audit(approval["case_id"], f"{event} via {approval_id}")
    return result
