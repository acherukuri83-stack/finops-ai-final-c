"""In-process stand-in for the enterprise tier.

Serves the Scenario 1 planted values (docs/eval-scenarios.md) so the swap test and the
agent-loop unit tests run with no JVM. ``fail_with`` forces an HTTP status for the error
tests. This is deliberately small — the real contract coverage runs against the live
enterprise in CI (``-m contract``).
"""

from __future__ import annotations

from typing import Any

from mcp_servers._enterprise import EnterpriseError
from mcp_servers.errors import from_http

_TRADE = {
    "trade_id": "T100245",
    "client_id": "HEDGE_FUND_101",
    "account_id": "ACC-88213",
    "security_id": "AAPL",
    "qty": 25000,
    "side": "BUY",
    "price": 227.15,
    "trade_date": "2026-09-03",
    "settle_date": "2026-09-04",
    "status": "FAILED",
    "cpty_id": "CP-017",
    "booked_at": "2026-09-03T10:02:00",
}

_SETTLEMENT = {
    "trade_id": "T100245",
    "status": "FAILED",
    "failure_code": "COUNTERPARTY_SSI_MISMATCH",
    "failure_detail": "instruction 1234 / affirmation 5678",
    "attempts": [
        {
            "at": "2026-09-04T06:02:11",
            "result": "FAILED",
            "detail": "instruction 1234 / affirmation 5678",
        }
    ],
    "last_attempt_at": "2026-09-04T06:02:11",
}

_AFFIRMATION = {
    "trade_id": "T100245",
    "cpty_id": "CP-017",
    "affirmed": True,
    "cpty_dtc": "5678",
    "affirmed_at": "2026-09-03T16:40:00",
}

_SSI_CURRENT = {
    "account_id": "ACC-88213",
    "version": 3,
    "dtc_participant": "1234",
    "agent_bic": "DTCYUS33",
    "valid_from": "2026-08-28",
    "updated_at": "2026-08-28T09:14:00",
    "updated_by": "ops.jsmith",
}

_SSI_HISTORY = [
    {
        "account_id": "ACC-88213",
        "version": 1,
        "dtc_participant": "9012",
        "valid_from": "2024-01-15",
        "valid_to": "2025-11-02",
        "updated_at": "2024-01-15T00:00:00",
        "updated_by": "ops.klee",
    },
    {
        "account_id": "ACC-88213",
        "version": 2,
        "dtc_participant": "5678",
        "valid_from": "2025-11-02",
        "valid_to": "2026-08-28",
        "updated_at": "2025-11-02T00:00:00",
        "updated_by": "ops.mchen",
    },
    _SSI_CURRENT,
]

_CPTY_SSI = {"cpty_id": "CP-017", "dtc_participant": "5678", "valid_to": "2027-01-01"}
_CPTY = {"cpty_id": "CP-017", "name": "Meridian Clearing LLC", "status": "ACTIVE", "contacts": []}
_ACCOUNT = {
    "account_id": "ACC-88213",
    "client_id": "HEDGE_FUND_101",
    "custodian": "BNY",
    "status": "ACTIVE",
    "restrictions": [],
    "risk_flags": [],
}
_LOGS = [
    {
        "ts": "2026-09-04T06:02:12",
        "svc": "settlement-engine",
        "level": "INFO",
        "msg": "T100245 status FAILED code COUNTERPARTY_SSI_MISMATCH",
        "trade_id": "T100245",
    },
    {
        "ts": "2026-09-04T06:02:11",
        "svc": "settlement-engine",
        "level": "ERROR",
        "msg": "T100245 instruction 1234 / affirmation 5678 -> mismatch",
        "trade_id": "T100245",
    },
    {
        "ts": "2026-09-03T16:40:03",
        "svc": "affirmation-gateway",
        "level": "INFO",
        "msg": "T100245 affirmation received CP-017 DTC 5678",
        "trade_id": "T100245",
    },
]

_ROUTES: dict[str, Any] = {
    "/trades/T100245": _TRADE,
    "/trades/T100245/settlement": _SETTLEMENT,
    "/trades/T100245/affirmation": _AFFIRMATION,
    "/accounts/ACC-88213": _ACCOUNT,
    "/accounts/ACC-88213/ssi": _SSI_CURRENT,
    "/accounts/ACC-88213/ssi/history": _SSI_HISTORY,
    "/counterparties/CP-017": _CPTY,
    "/counterparties/CP-017/ssi": _CPTY_SSI,
}


class FakeEnterpriseClient:
    def __init__(self) -> None:
        self.fail_with: int | None = None
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def get_json(self, tool: str, path: str, params: dict[str, Any] | None = None) -> Any:
        self.calls.append((path, {k: v for k, v in (params or {}).items() if v is not None}))
        if self.fail_with is not None:
            raise EnterpriseError(from_http(tool, self.fail_with, f"forced {self.fail_with}"))
        if path == "/trades" and (params or {}).get("account") == "ACC-88213":
            return [_TRADE]
        if path == "/logs":
            return _LOGS if (params or {}).get("tradeId") in (None, "T100245") else []
        if path in _ROUTES:
            return _ROUTES[path]
        raise EnterpriseError(from_http(tool, 404, f"fake: no route {path}"))
