"""Planter: applies one scenario's `plant:` block on top of the baseline.

One handler per `PLANT_KEYS` entry (`simulator/scenario.py`). Every handler is
idempotent — it deletes exactly the rows it is about to replace (scoped by the
natural key it owns) before inserting, so re-planting the same scenario, or
seeding several scenarios that share a trade id (Sc. 1/2/9/12 all use
T100245/ACC-88213), never raises a primary-key collision.

Facts only: this module never decides *why* something happened — it writes
exactly the rows the YAML describes. The leak check runs on the YAML, not here.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, time
from typing import Any

from sqlalchemy import Connection, delete, text

from simulator.finance_tables import (
    ca_entitlements,
    ca_events,
    cash_breaks,
    lending_availability,
    margin_calls,
    stock_loans,
)
from simulator.scenario import Scenario
from simulator.tables import (
    affirmations,
    app_logs,
    borrow_availability,
    counterparty_ssi,
    incidents,
    positions,
    restrictions,
    securities,
    settlement_attempts,
    ssi_versions,
    trades,
)


def _parse_date(v: Any) -> date:
    return v if isinstance(v, date) else date.fromisoformat(str(v))


def _parse_dt(v: Any) -> datetime:
    if isinstance(v, datetime):
        return v
    if isinstance(v, date):
        return datetime.combine(v, time(0, 0))
    return datetime.fromisoformat(str(v))


def _plant_accounts_ssi(conn: Connection, rows: list[dict[str, Any]]) -> None:
    account_ids = {r["account"] for r in rows}
    conn.execute(delete(ssi_versions).where(ssi_versions.c.account_id.in_(account_ids)))
    conn.execute(
        ssi_versions.insert(),
        [
            {
                "account_id": r["account"],
                "version": r["version"],
                "dtc_participant": str(r["dtc"]),
                "agent_bic": r.get("agent_bic"),
                "valid_from": _parse_date(r["valid_from"]),
                "valid_to": _parse_date(r["valid_to"]) if r.get("valid_to") else None,
                "updated_at": datetime.combine(_parse_date(r["valid_from"]), time(9, 0)),
                "updated_by": r.get("by", "ops.system"),
            }
            for r in rows
        ],
    )


def _plant_counterparties_ssi(conn: Connection, rows: list[dict[str, Any]]) -> None:
    cpty_ids = {r["cpty"] for r in rows}
    conn.execute(delete(counterparty_ssi).where(counterparty_ssi.c.cpty_id.in_(cpty_ids)))
    conn.execute(
        counterparty_ssi.insert(),
        [
            {
                "cpty_id": r["cpty"],
                "dtc_participant": str(r["dtc"]),
                "valid_to": _parse_date(r["valid_to"]) if r.get("valid_to") else None,
            }
            for r in rows
        ],
    )


def _plant_trades(conn: Connection, rows: list[dict[str, Any]]) -> None:
    trade_ids = {r["id"] for r in rows}
    # Cascades to settlement_attempts / affirmations for these trade ids.
    conn.execute(delete(trades).where(trades.c.trade_id.in_(trade_ids)))
    conn.execute(
        trades.insert(),
        [
            {
                "trade_id": r["id"],
                "client_id": r["client"],
                "account_id": r["account"],
                "security_id": r["security"],
                "qty": r["qty"],
                "side": r["side"],
                "price": r["price"],
                "trade_date": _parse_date(r["trade_date"]),
                "settle_date": _parse_date(r["settle_date"]),
                "status": r["status"],
                "failure_code": r.get("failure_code"),
                "cpty_id": r["cpty"],
                "booked_at": _parse_dt(r.get("booked_at", r["trade_date"])),
            }
            for r in rows
        ],
    )


def _plant_settlement_attempts(conn: Connection, rows: list[dict[str, Any]]) -> None:
    trade_ids = {r["trade"] for r in rows}
    conn.execute(delete(settlement_attempts).where(settlement_attempts.c.trade_id.in_(trade_ids)))
    conn.execute(
        settlement_attempts.insert(),
        [
            {
                "trade_id": r["trade"],
                "at": _parse_dt(r["at"]),
                "result": r["result"],
                "detail": r.get("detail"),
            }
            for r in rows
        ],
    )


def _plant_affirmations(conn: Connection, rows: list[dict[str, Any]]) -> None:
    trade_ids = {r["trade"] for r in rows}
    conn.execute(delete(affirmations).where(affirmations.c.trade_id.in_(trade_ids)))
    conn.execute(
        affirmations.insert(),
        [
            {
                "trade_id": r["trade"],
                "cpty_id": r["cpty"],
                "cpty_dtc": str(r["cpty_dtc"]),
                "affirmed": r.get("affirmed", bool(r.get("affirmed_at"))),
                "affirmed_at": _parse_dt(r["affirmed_at"]) if r.get("affirmed_at") else None,
            }
            for r in rows
        ],
    )


def _plant_positions(conn: Connection, rows: list[dict[str, Any]]) -> None:
    for r in rows:
        as_of = _parse_date(r["as_of"]) if r.get("as_of") else date(2026, 9, 4)
        conn.execute(
            delete(positions).where(
                (positions.c.account_id == r["account"])
                & (positions.c.security_id == r["security"])
                & (positions.c.as_of == as_of)
            )
        )
        conn.execute(
            positions.insert().values(
                account_id=r["account"],
                security_id=r["security"],
                as_of=as_of,
                qty=r["qty"],
                available=r["available"],
                pending_deliver=r.get("pending_deliver", 0),
                pending_receive=r.get("pending_receive", 0),
            )
        )


def _plant_borrow(conn: Connection, rows: list[dict[str, Any]]) -> None:
    for r in rows:
        conn.execute(
            delete(borrow_availability).where(borrow_availability.c.security_id == r["security"])
        )
        conn.execute(
            borrow_availability.insert().values(
                security_id=r["security"],
                available_qty=r["available_qty"],
                rate=r.get("rate", 0.5),
                recalls=r.get("recalls", []),
            )
        )


def _plant_restrictions(conn: Connection, rows: list[dict[str, Any]]) -> None:
    account_ids = {r["account"] for r in rows}
    conn.execute(delete(restrictions).where(restrictions.c.account_id.in_(account_ids)))
    conn.execute(
        restrictions.insert(),
        [
            {
                "account_id": r["account"],
                "type": r["type"],
                "reason": r["reason"],
                "set_by": r["set_by"],
                "set_at": _parse_dt(r["set_at"]),
                "active": r.get("active", True),
            }
            for r in rows
        ],
    )


def _plant_securities(conn: Connection, rows: list[dict[str, Any]]) -> None:
    ids = {r["id"] for r in rows}
    conn.execute(delete(securities).where(securities.c.security_id.in_(ids)))
    conn.execute(
        securities.insert(),
        [
            {
                "security_id": r["id"],
                "isin": r["isin"],
                "cusip": r["cusip"],
                "description": r.get("description", r["id"]),
                "settle_cycle": r.get("settle_cycle", "T+1"),
                "status": r.get("status", "ACTIVE"),
            }
            for r in rows
        ],
    )


def _plant_logs(conn: Connection, rows: list[dict[str, Any]]) -> None:
    trade_ids = {r["trade_id"] for r in rows if r.get("trade_id")}
    if trade_ids:
        conn.execute(delete(app_logs).where(app_logs.c.trade_id.in_(trade_ids)))
    conn.execute(
        app_logs.insert(),
        [
            {
                "ts": _parse_dt(r["ts"]),
                "svc": r["svc"],
                "level": r["level"],
                "msg": r["msg"],
                "trade_id": r.get("trade_id"),
            }
            for r in rows
        ],
    )


def _plant_loans(conn: Connection, rows: list[dict[str, Any]]) -> None:
    loan_ids = {r["id"] for r in rows}
    conn.execute(delete(stock_loans).where(stock_loans.c.loan_id.in_(loan_ids)))
    conn.execute(
        stock_loans.insert(),
        [
            {
                "loan_id": r["id"],
                "account_id": r["account"],
                "security_id": r["security"],
                "counterparty": r.get("counterparty", r.get("cpty")),
                "qty": r["qty"],
                "rate_bps": r.get("rate_bps", 25),
                "trade_date": _parse_date(r["trade_date"]) if r.get("trade_date") else None,
                "open": r.get("open", True),
                "return_needed_by": (
                    _parse_date(r["return_needed_by"]) if r.get("return_needed_by") else None
                ),
            }
            for r in rows
        ],
    )


def _plant_lending(conn: Connection, rows: list[dict[str, Any]]) -> None:
    for r in rows:
        conn.execute(
            delete(lending_availability).where(lending_availability.c.security_id == r["security"])
        )
        conn.execute(
            lending_availability.insert().values(
                security_id=r["security"],
                lendable_qty=r["lendable_qty"],
                on_loan_qty=r["on_loan_qty"],
                gc_rate_bps=r.get("gc_rate_bps", 25),
            )
        )


def _plant_margin_calls(conn: Connection, rows: list[dict[str, Any]]) -> None:
    call_ids = {r["id"] for r in rows}
    conn.execute(delete(margin_calls).where(margin_calls.c.call_id.in_(call_ids)))
    conn.execute(
        margin_calls.insert(),
        [
            {
                "call_id": r["id"],
                "account_id": r["account"],
                "issued": _parse_date(r["issued"]) if r.get("issued") else None,
                "due_by": _parse_date(r["due_by"]) if r.get("due_by") else None,
                "amount": r["amount"],
                "reason": r.get("reason", "PRICE_MOVE"),
                "status": r.get("status", "OPEN"),
            }
            for r in rows
        ],
    )


def _plant_ca_events(conn: Connection, rows: list[dict[str, Any]]) -> None:
    event_ids = {r["id"] for r in rows}
    conn.execute(delete(ca_events).where(ca_events.c.event_id.in_(event_ids)))
    conn.execute(
        ca_events.insert(),
        [
            {
                "event_id": r["id"],
                "security_id": r["security"],
                "type": r["type"],
                "record_date": _parse_date(r["record_date"]) if r.get("record_date") else None,
                "pay_date": _parse_date(r["pay_date"]) if r.get("pay_date") else None,
                "gross_rate": r.get("gross_rate", 0.0),
                "elective": r.get("elective", False),
                "election_deadline": (
                    _parse_date(r["election_deadline"]) if r.get("election_deadline") else None
                ),
            }
            for r in rows
        ],
    )


def _plant_ca_entitlements(conn: Connection, rows: list[dict[str, Any]]) -> None:
    for r in rows:
        conn.execute(
            delete(ca_entitlements).where(
                (ca_entitlements.c.account_id == r["account"])
                & (ca_entitlements.c.event_id == r["event"])
            )
        )
        conn.execute(
            ca_entitlements.insert().values(
                account_id=r["account"],
                event_id=r["event"],
                record_date_qty=r["record_date_qty"],
                held_qty=r["held_qty"],
                lent_qty=r["lent_qty"],
                gross_entitlement=r.get("gross_entitlement", 0.0),
            )
        )


def _plant_cash_breaks(conn: Connection, rows: list[dict[str, Any]]) -> None:
    break_ids = {r["id"] for r in rows}
    conn.execute(delete(cash_breaks).where(cash_breaks.c.break_id.in_(break_ids)))
    conn.execute(
        cash_breaks.insert(),
        [
            {
                "break_id": r["id"],
                "account_id": r["account"],
                "currency": r["currency"],
                "projected_close": r["projected_close"],
                "min_buffer": r.get("min_buffer", 0),
                "funding_cutoff": _parse_dt(r["funding_cutoff"])
                if r.get("funding_cutoff")
                else None,
                "driver": r.get("driver", ""),
            }
            for r in rows
        ],
    )


def _plant_incidents(conn: Connection, ids: list[str]) -> None:
    conn.execute(delete(incidents).where(incidents.c.incident_id.in_(ids)))
    conn.execute(
        incidents.insert(),
        [
            {"incident_id": i, "occurred_at": datetime(2026, 6, 1, 9, 0), "status": "CLOSED"}
            for i in ids
        ],
    )


def _plant_corpus_fixtures(conn: Connection, ids: list[str]) -> None:
    # W2 consumes these (corpus ingestion). W1 just validates the shape.
    assert isinstance(ids, list)


HANDLERS: dict[str, Callable[[Connection, Any], None]] = {
    "accounts.ssi": _plant_accounts_ssi,
    "counterparties.ssi": _plant_counterparties_ssi,
    "trades": _plant_trades,
    "settlement_attempts": _plant_settlement_attempts,
    "affirmations": _plant_affirmations,
    "positions": _plant_positions,
    "borrow": _plant_borrow,
    "restrictions": _plant_restrictions,
    "securities": _plant_securities,
    "loans": _plant_loans,
    "lending": _plant_lending,
    "margin_calls": _plant_margin_calls,
    "ca_events": _plant_ca_events,
    "ca_entitlements": _plant_ca_entitlements,
    "cash_breaks": _plant_cash_breaks,
    "logs": _plant_logs,
    "incidents": _plant_incidents,
    "corpus_fixtures": _plant_corpus_fixtures,
}


def plant(conn: Connection, scenario: Scenario) -> None:
    if scenario.unknown_plant_keys():
        raise ValueError(f"unknown plant keys: {scenario.unknown_plant_keys()}")
    if scenario.leaks():
        raise ValueError(f"interpretive language in planted data: {scenario.leaks()}")
    # Order matters: trades before their attempts/affirmations; securities
    # before anything that references them.
    order = [
        "securities",
        "accounts.ssi",
        "counterparties.ssi",
        "trades",
        "settlement_attempts",
        "affirmations",
        "positions",
        "borrow",
        "restrictions",
        "loans",
        "lending",
        "margin_calls",
        "ca_events",
        "ca_entitlements",
        "cash_breaks",
        "logs",
        "incidents",
        "corpus_fixtures",
    ]
    for key in order:
        if key in scenario.plant:
            HANDLERS[key](conn, scenario.plant[key])
    if scenario.fault_inject:
        conn.execute(
            text("select 1")
        )  # fault injection is enterprise-side (FAULT_INJECT env); no DB action
