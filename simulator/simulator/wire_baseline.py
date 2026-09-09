"""Baseline rows for the wire tables (Phase B — Wires, optional module).

The generic wire world a plain `make seed` exposes: the five held wires (`W300915`,
`W300917`, `W300918`, `W300920`, `W300921`) on `HF-201` / `HF-203` / `HF-205` / `HF-206`,
their standing instructions, one screening hit, and available balances. Scenario-specific
rows are the planter's job (Sc. 7 / 13–16 re-plant their own wire with its own dates).

Mirrors the `_seed()` snapshot in `ai-platform/mcp_servers/wire/store.py` by hand.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import Connection, text

from simulator.wire_tables import (
    WIRE_TABLES,
    ensure,
    wire_audit_events,
    wire_balances,
    wire_screening,
    wire_standing_instructions,
    wires,
)


def _d(v: str | None) -> date | None:
    return date.fromisoformat(v) if v else None


def _dt(v: str | None) -> datetime | None:
    return datetime.fromisoformat(v) if v else None


def populate_wire(conn: Connection) -> None:
    ensure(conn)
    for tbl in WIRE_TABLES:
        conn.execute(text(f'TRUNCATE TABLE "{tbl.name}" RESTART IDENTITY CASCADE'))

    conn.execute(
        wires.insert(),
        [
            _w(
                "W300915",
                "HF-201",
                "ACCT-201",
                "USD",
                2_500_000,
                "ACME Corp",
                "BEN-999",
                "BENEFICIARY_MISMATCH",
            ),
            _w(
                "W300917",
                "HF-201",
                "ACCT-201",
                "USD",
                3_100_000,
                "Orion Freight Co",
                "BEN-777",
                "NEW_BENEFICIARY",
            ),
            _w(
                "W300918",
                "HF-203",
                "ACCT-203",
                "EUR",
                900_000,
                "Beta Logistics LLC",
                "BEN-200",
                "AWAITING_RELEASE",
            ),
            _w(
                "W300920",
                "HF-205",
                "ACCT-205",
                "USD",
                1_750_000,
                "Cedar Holdings",
                "BEN-305",
                "SCREENING",
            ),
            _w(
                "W300921",
                "HF-206",
                "ACCT-206",
                "USD",
                5_000_000,
                "Delta Partners",
                "BEN-410",
                "FUNDING",
            ),
        ],
    )
    conn.execute(
        wire_standing_instructions.insert(),
        [
            _si("HF-201", "ACME Corp", "BEN-100", "2025-04-02", "ops.klee"),
            _si("HF-203", "Beta Logistics LLC", "BEN-200", "2025-08-19", "ops.mchen"),
            _si("HF-205", "Cedar Holdings", "BEN-305", "2025-01-10", "ops.jsmith"),
            _si("HF-206", "Delta Partners", "BEN-410", "2026-02-01", "ops.rpatel"),
        ],
    )
    conn.execute(
        wire_screening.insert(),
        [
            {
                "client_id": "HF-205",
                "status": "HIT",
                "matched_list": "OFAC SDN",
                "checked_at": _dt("2026-09-06T14:55"),
            }
        ],
    )
    conn.execute(
        wire_balances.insert(),
        [
            {"account_id": "ACCT-201", "currency": "USD", "available": 40_000_000},
            {"account_id": "ACCT-203", "currency": "EUR", "available": 12_000_000},
            {"account_id": "ACCT-205", "currency": "USD", "available": 8_000_000},
            {"account_id": "ACCT-206", "currency": "USD", "available": 1_200_000},
        ],
    )
    conn.execute(
        wire_audit_events.insert(),
        [
            _ae(
                "W300917",
                "2026-09-06T15:20",
                "wire-gateway",
                "received OUT 3,100,000 USD to BEN-777",
            ),
            _ae(
                "W300917",
                "2026-09-06T15:21",
                "wire-gateway",
                "held: beneficiary not on standing instructions",
            ),
            _ae(
                "W300918", "2026-09-05T17:00", "wire-gateway", "received OUT 900,000 EUR to BEN-200"
            ),
            _ae(
                "W300918",
                "2026-09-06T15:01",
                "cutoff-monitor",
                "TARGET2 cutoff 15:00 passed, value date 2026-09-06",
            ),
            _ae(
                "W300920",
                "2026-09-06T14:55",
                "screening-gateway",
                "screening returned HIT (OFAC SDN)",
            ),
            _ae("W300920", "2026-09-06T14:55", "wire-gateway", "held: screening"),
        ],
    )


def _w(
    wid: str, client: str, acct: str, ccy: str, amount: int, ben: str, ben_acct: str, hold: str
) -> dict[str, Any]:
    return {
        "wire_id": wid,
        "client_id": client,
        "account_id": acct,
        "direction": "OUT",
        "currency": ccy,
        "amount": amount,
        "beneficiary": ben,
        "beneficiary_account": ben_acct,
        "value_date": date(2026, 9, 6),
        "status": "HELD",
        "hold_reason": hold,
    }


def _si(client: str, ben: str, ben_acct: str, added_at: str, by: str) -> dict[str, Any]:
    return {
        "client_id": client,
        "beneficiary": ben,
        "beneficiary_account": ben_acct,
        "added_at": _d(added_at),
        "added_by": by,
    }


def _ae(wid: str, at: str, actor: str, event: str) -> dict[str, Any]:
    return {"wire_id": wid, "at": _dt(at), "actor": actor, "event": event}
