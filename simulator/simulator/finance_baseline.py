"""Baseline rows for the prime-finance tables (stockloan / margin / corpactions / cash).

The generic broker/dealer world for these four domains: the demo ids a plain `make seed`
must expose (`LN-5001`, `MC-9001`, `CA-7001`, `CB-8001`, ...) on `ACC-88213`, plus street
lending availability. Scenario-specific rows are the planter's job — Sc. 30 re-plants
`LN-5001` with its own dates, the way Sc. 5 re-plants `borrow_availability` for NVDA.

Mirrors the `_seed()` snapshots in `ai-platform/mcp_servers/<domain>/store.py` by hand.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Connection, text

from simulator.finance_tables import (
    FINANCE_TABLES,
    ca_elections,
    ca_entitlements,
    ca_events,
    cash_breaks,
    collateral,
    collateral_eligibility,
    credit_facilities,
    ensure,
    funding_ladders,
    lending_availability,
    loan_recalls,
    loan_rerates,
    margin_calls,
    margin_status,
    stock_loans,
)


def _d(v: str | None) -> date | None:
    return date.fromisoformat(v) if v else None


def _dt(v: str | None) -> datetime | None:
    return datetime.fromisoformat(v) if v else None


def populate_finance(conn: Connection) -> None:
    ensure(conn)
    for tbl in FINANCE_TABLES:
        conn.execute(text(f'TRUNCATE TABLE "{tbl.name}" RESTART IDENTITY CASCADE'))

    conn.execute(
        stock_loans.insert(),
        [
            {
                "loan_id": "LN-5001",
                "account_id": "ACC-88213",
                "security_id": "NVDA",
                "counterparty": "CP-020",
                "qty": 30000,
                "rate_bps": 45,
                "trade_date": _d("2026-07-01"),
                "open": True,
                "return_needed_by": _d("2026-09-10"),
            },
            {
                "loan_id": "LN-5002",
                "account_id": "ACC-88213",
                "security_id": "AMZN",
                "counterparty": "CP-020",
                "qty": 12000,
                "rate_bps": 30,
                "trade_date": _d("2026-06-15"),
                "open": True,
                "return_needed_by": _d("2026-09-04"),
            },
            {
                "loan_id": "LN-5003",
                "account_id": "ACC-77120",
                "security_id": "AAPL",
                "counterparty": "CP-031",
                "qty": 5000,
                "rate_bps": 500,
                "trade_date": _d("2026-08-20"),
                "open": True,
                "return_needed_by": None,
            },
        ],
    )
    conn.execute(
        loan_recalls.insert(),
        [
            {
                "loan_id": "LN-5002",
                "status": "ISSUED",
                "issued_at": _dt("2026-09-03T14:00"),
                "due_date": _d("2026-09-04"),
                "satisfied": False,
            }
        ],
    )
    conn.execute(
        loan_rerates.insert(),
        [
            {
                "loan_id": "LN-5003",
                "at": _d("2026-08-20"),
                "from_bps": 30,
                "to_bps": 500,
                "by": "desk.auto",
            }
        ],
    )
    conn.execute(
        lending_availability.insert(),
        [
            {
                "security_id": "NVDA",
                "lendable_qty": 500000,
                "on_loan_qty": 180000,
                "gc_rate_bps": 25,
            },
            {
                "security_id": "AMZN",
                "lendable_qty": 200000,
                "on_loan_qty": 40000,
                "gc_rate_bps": 20,
            },
            {
                "security_id": "AAPL",
                "lendable_qty": 800000,
                "on_loan_qty": 120000,
                "gc_rate_bps": 15,
            },
        ],
    )

    conn.execute(
        margin_calls.insert(),
        [
            {
                "call_id": "MC-9001",
                "account_id": "ACC-88213",
                "issued": _d("2026-09-05"),
                "due_by": _d("2026-09-06"),
                "amount": 4_200_000,
                "reason": "PRICE_MOVE",
                "status": "OPEN",
            },
            {
                "call_id": "MC-9002",
                "account_id": "ACC-88213",
                "issued": _d("2026-09-02"),
                "due_by": _d("2026-09-03"),
                "amount": 1_100_000,
                "reason": "PRICE_MOVE",
                "status": "OPEN",
            },
        ],
    )
    conn.execute(
        margin_status.insert(),
        [
            {
                "account_id": "ACC-88213",
                "requirement": 18_400_000,
                "posted": 14_200_000,
                "shortfall": 4_200_000,
                "as_of": _d("2026-09-05"),
            }
        ],
    )
    conn.execute(
        collateral.insert(),
        [
            {
                "account_id": "ACC-88213",
                "security_id": "AAPL",
                "market_value": 9_000_000,
                "haircut_pct": 5,
                "eligible": True,
            },
            {
                "account_id": "ACC-88213",
                "security_id": "NVDA",
                "market_value": 5_200_000,
                "haircut_pct": 8,
                "eligible": True,
            },
            {
                "account_id": "ACC-88213",
                "security_id": "XLOW",
                "market_value": 2_000_000,
                "haircut_pct": 100,
                "eligible": False,
            },
        ],
    )
    conn.execute(
        collateral_eligibility.insert(),
        [
            {"security_id": "AAPL", "eligible": True, "haircut_pct": 5, "rating": "A"},
            {"security_id": "NVDA", "eligible": True, "haircut_pct": 8, "rating": "A"},
            {"security_id": "XLOW", "eligible": False, "haircut_pct": 100, "rating": "CCC"},
        ],
    )

    conn.execute(
        ca_events.insert(),
        [
            {
                "event_id": "CA-7001",
                "security_id": "AAPL",
                "type": "CASH_DIVIDEND",
                "record_date": _d("2026-09-01"),
                "pay_date": _d("2026-09-10"),
                "gross_rate": 0.25,
                "elective": False,
                "election_deadline": None,
            },
            {
                "event_id": "CA-7002",
                "security_id": "NVDA",
                "type": "RIGHTS_ISSUE",
                "record_date": _d("2026-09-02"),
                "pay_date": _d("2026-09-20"),
                "gross_rate": 0.0,
                "elective": True,
                "election_deadline": _d("2026-09-04"),
            },
        ],
    )
    conn.execute(
        ca_entitlements.insert(),
        [
            {
                "account_id": "ACC-88213",
                "event_id": "CA-7001",
                "record_date_qty": 40000,
                "held_qty": 10000,
                "lent_qty": 30000,
                "gross_entitlement": 10000.0,
            },
            {
                "account_id": "ACC-88213",
                "event_id": "CA-7002",
                "record_date_qty": 12000,
                "held_qty": 12000,
                "lent_qty": 0,
                "gross_entitlement": 0.0,
            },
        ],
    )
    conn.execute(
        ca_elections.insert(),
        [
            {
                "event_id": "CA-7002",
                "options": ["TAKE_UP", "LAPSE", "SELL_RIGHTS"],
                "default": "LAPSE",
                "submitted": None,
            }
        ],
    )

    conn.execute(
        cash_breaks.insert(),
        [
            {
                "break_id": "CB-8001",
                "account_id": "ACC-88213",
                "currency": "USD",
                "projected_close": -6_500_000,
                "min_buffer": 1_000_000,
                "funding_cutoff": _dt("2026-09-06T16:00"),
                "driver": "unexpected settlement outflow",
            },
            {
                "break_id": "CB-8002",
                "account_id": "ACC-88213",
                "currency": "EUR",
                "projected_close": -2_100_000,
                "min_buffer": 500_000,
                "funding_cutoff": _dt("2026-09-06T12:00"),
                "driver": "coupon payment",
            },
        ],
    )
    conn.execute(
        funding_ladders.insert(),
        [
            {
                "account_id": "ACC-88213",
                "currency": "USD",
                "time": _dt("2026-09-06T10:00"),
                "flow": 3_000_000,
                "kind": "receipt",
            },
            {
                "account_id": "ACC-88213",
                "currency": "USD",
                "time": _dt("2026-09-06T14:30"),
                "flow": -9_500_000,
                "kind": "settlement",
            },
            {
                "account_id": "ACC-88213",
                "currency": "USD",
                "time": _dt("2026-09-06T15:00"),
                "flow": 0,
                "kind": "expected",
            },
            {
                "account_id": "ACC-88213",
                "currency": "EUR",
                "time": _dt("2026-09-06T09:00"),
                "flow": 400_000,
                "kind": "receipt",
            },
            {
                "account_id": "ACC-88213",
                "currency": "EUR",
                "time": _dt("2026-09-06T11:30"),
                "flow": -2_500_000,
                "kind": "coupon",
            },
        ],
    )
    conn.execute(
        credit_facilities.insert(),
        [
            {
                "account_id": "ACC-88213",
                "currency": "USD",
                "limit": 20_000_000,
                "drawn": 4_000_000,
                "headroom": 16_000_000,
            },
            {
                "account_id": "ACC-88213",
                "currency": "EUR",
                "limit": 5_000_000,
                "drawn": 0,
                "headroom": 5_000_000,
            },
        ],
    )
