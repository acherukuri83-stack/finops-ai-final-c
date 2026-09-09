"""Data access for the `wire` server (Phase B — Wires, optional module).

Seeded Postgres (`simulator` planter, `make seed`) with an in-memory mode for the unit
suite — the split is `mcp_servers._finance_store.FinanceStore` (generic seeded-store; not
finance-specific despite the module name). The row shapes below are exactly what the
fixtures held before seeding, so the specialist and its prompts don't change.

Facts only — nothing here says a wire *should* be routed or rescheduled; the Wire
specialist derives that, and the maker/checker + cutoff + screening rules are code
(`agent_core/wire.py`), not prompt. `NOW` / `TODAY` are deterministic and back the cutoff
computation. `NOW` is 15:38, so the USD 16:00 cutoff is 22 minutes away (Sc. 13) and the
EUR 15:00 cutoff has passed (Sc. 14). Cutoffs are static config, not a seeded table.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, Column, Date, DateTime, Integer, String, Table
from sqlalchemy.dialects.postgresql import JSONB

from mcp_servers._finance_store import FinanceStore, metadata

NOW = datetime(2026, 9, 6, 15, 38)
TODAY = date(2026, 9, 6)

_CUTOFFS: dict[str, dict[str, Any]] = {
    "USD": {"currency": "USD", "cutoff": "16:00", "tz": "America/New_York", "network": "Fedwire"},
    "EUR": {"currency": "EUR", "cutoff": "15:00", "tz": "Europe/London", "network": "TARGET2"},
}

# --- tables (mirrored by simulator/simulator/wire_tables.py) -------------------

wires = Table(
    "wires",
    metadata,
    Column("wire_id", String, primary_key=True),
    Column("client_id", String),
    Column("account_id", String),
    Column("direction", String),
    Column("currency", String),
    Column("amount", BigInteger),
    Column("beneficiary", String),
    Column("beneficiary_account", String),
    Column("value_date", Date),
    Column("status", String),
    Column("hold_reason", String),
)

wire_standing_instructions = Table(
    "wire_standing_instructions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("client_id", String),
    Column("beneficiary", String),
    Column("beneficiary_account", String),
    Column("added_at", Date),
    Column("added_by", String),
)

wire_screening = Table(
    "wire_screening",
    metadata,
    Column("client_id", String, primary_key=True),
    Column("status", String),
    Column("matched_list", String),
    Column("checked_at", DateTime),
)

wire_balances = Table(
    "wire_balances",
    metadata,
    Column("account_id", String, primary_key=True),
    Column("currency", String, primary_key=True),
    Column("available", BigInteger),
)

wire_audit_events = Table(
    "wire_audit_events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("wire_id", String),
    Column("at", DateTime),
    Column("actor", String),
    Column("event", String),
)

wire_actions = Table(
    "wire_actions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("kind", String),
    Column("subject_id", String),
    Column("detail", JSONB),
    Column("status", String),
    Column("approval_id", String),
)


def _seed() -> dict[str, list[dict[str, Any]]]:
    return {
        "wires": [
            # Sc. 7 — beneficiary mismatch (account not on standing instructions)
            {
                "wire_id": "W300915",
                "client_id": "HF-201",
                "account_id": "ACCT-201",
                "direction": "OUT",
                "currency": "USD",
                "amount": 2_500_000,
                "beneficiary": "ACME Corp",
                "beneficiary_account": "BEN-999",
                "value_date": "2026-09-06",
                "status": "HELD",
                "hold_reason": "BENEFICIARY_MISMATCH",
            },
            # Sc. 13 — new beneficiary, USD cutoff 22 min away
            {
                "wire_id": "W300917",
                "client_id": "HF-201",
                "account_id": "ACCT-201",
                "direction": "OUT",
                "currency": "USD",
                "amount": 3_100_000,
                "beneficiary": "Orion Freight Co",
                "beneficiary_account": "BEN-777",
                "value_date": "2026-09-06",
                "status": "HELD",
                "hold_reason": "NEW_BENEFICIARY",
            },
            # Sc. 14 — cutoff missed (EUR 15:00, now 15:38); beneficiary is known
            {
                "wire_id": "W300918",
                "client_id": "HF-203",
                "account_id": "ACCT-203",
                "direction": "OUT",
                "currency": "EUR",
                "amount": 900_000,
                "beneficiary": "Beta Logistics LLC",
                "beneficiary_account": "BEN-200",
                "value_date": "2026-09-06",
                "status": "HELD",
                "hold_reason": "AWAITING_RELEASE",
            },
            # Sc. 15 — screening hit on the client
            {
                "wire_id": "W300920",
                "client_id": "HF-205",
                "account_id": "ACCT-205",
                "direction": "OUT",
                "currency": "USD",
                "amount": 1_750_000,
                "beneficiary": "Cedar Holdings",
                "beneficiary_account": "BEN-305",
                "value_date": "2026-09-06",
                "status": "HELD",
                "hold_reason": "SCREENING",
            },
            # Sc. 16 — insufficient available balance
            {
                "wire_id": "W300921",
                "client_id": "HF-206",
                "account_id": "ACCT-206",
                "direction": "OUT",
                "currency": "USD",
                "amount": 5_000_000,
                "beneficiary": "Delta Partners",
                "beneficiary_account": "BEN-410",
                "value_date": "2026-09-06",
                "status": "HELD",
                "hold_reason": "FUNDING",
            },
        ],
        "wire_standing_instructions": [
            {
                "client_id": "HF-201",
                "beneficiary": "ACME Corp",
                "beneficiary_account": "BEN-100",
                "added_at": "2025-04-02",
                "added_by": "ops.klee",
            },
            {
                "client_id": "HF-203",
                "beneficiary": "Beta Logistics LLC",
                "beneficiary_account": "BEN-200",
                "added_at": "2025-08-19",
                "added_by": "ops.mchen",
            },
            {
                "client_id": "HF-205",
                "beneficiary": "Cedar Holdings",
                "beneficiary_account": "BEN-305",
                "added_at": "2025-01-10",
                "added_by": "ops.jsmith",
            },
            {
                "client_id": "HF-206",
                "beneficiary": "Delta Partners",
                "beneficiary_account": "BEN-410",
                "added_at": "2026-02-01",
                "added_by": "ops.rpatel",
            },
        ],
        "wire_screening": [
            {
                "client_id": "HF-205",
                "status": "HIT",
                "matched_list": "OFAC SDN",
                "checked_at": "2026-09-06T14:55",
            },
        ],
        "wire_balances": [
            {"account_id": "ACCT-201", "currency": "USD", "available": 40_000_000},
            {"account_id": "ACCT-203", "currency": "EUR", "available": 12_000_000},
            {"account_id": "ACCT-205", "currency": "USD", "available": 8_000_000},
            {"account_id": "ACCT-206", "currency": "USD", "available": 1_200_000},
        ],
        "wire_audit_events": [
            {
                "wire_id": "W300917",
                "at": "2026-09-06T15:20",
                "actor": "wire-gateway",
                "event": "received OUT 3,100,000 USD to BEN-777",
            },
            {
                "wire_id": "W300917",
                "at": "2026-09-06T15:21",
                "actor": "wire-gateway",
                "event": "held: beneficiary not on standing instructions",
            },
            {
                "wire_id": "W300918",
                "at": "2026-09-05T17:00",
                "actor": "wire-gateway",
                "event": "received OUT 900,000 EUR to BEN-200",
            },
            {
                "wire_id": "W300918",
                "at": "2026-09-06T15:01",
                "actor": "cutoff-monitor",
                "event": "TARGET2 cutoff 15:00 passed, value date 2026-09-06",
            },
            {
                "wire_id": "W300920",
                "at": "2026-09-06T14:55",
                "actor": "screening-gateway",
                "event": "screening returned HIT (OFAC SDN)",
            },
            {
                "wire_id": "W300920",
                "at": "2026-09-06T14:55",
                "actor": "wire-gateway",
                "event": "held: screening",
            },
        ],
    }


_S = FinanceStore(
    name="wire",
    read_tables=[
        wires,
        wire_standing_instructions,
        wire_screening,
        wire_balances,
        wire_audit_events,
    ],
    action_table=wire_actions,
    action_prefix="WR",
    subject_key="wire_id",
    seed=_seed,
)


def reset() -> None:
    _S.reset()


def ensure_schema() -> None:
    _S.ensure_schema()


def get_wire(wire_id: str) -> dict[str, Any] | None:
    return _S.get("wires", wire_id=wire_id)


def list_wires(client_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
    return _S.find("wires", client_id=client_id, status=status)


def get_wire_audit_trail(wire_id: str) -> list[dict[str, Any]]:
    rows = _S.find("wire_audit_events", wire_id=wire_id)
    for r in rows:
        r.pop("id", None)
        r.pop("wire_id", None)
    return rows


def get_standing_instructions(client_id: str) -> list[dict[str, Any]]:
    rows = _S.find("wire_standing_instructions", client_id=client_id)
    for r in rows:
        r.pop("id", None)
        r.pop("client_id", None)
    return rows


def get_approval_queue() -> list[dict[str, Any]]:
    """Wires currently routed to a reviewer — derived from the OPEN `route_to_reviewer`
    actions, so there is no separate queue table to keep in sync."""
    out: list[dict[str, Any]] = []
    for a in _S.actions():
        if a["kind"] == "route_to_reviewer" and a["status"] == "OPEN":
            detail = a.get("detail") or {}
            out.append(
                {
                    "wire_id": a["wire_id"],
                    "action_id": a["action_id"],
                    "reviewer": "WIRE_REVIEWER",
                    "reason": detail.get("reason", ""),
                    "packet": detail.get("packet", ""),
                }
            )
    return out


def get_cutoff(currency: str) -> dict[str, Any] | None:
    row = _CUTOFFS.get(currency)
    return dict(row) if row else None


def get_wire_screening(client_id: str) -> dict[str, Any]:
    row = _S.get("wire_screening", client_id=client_id)
    if row:
        return row
    return {
        "client_id": client_id,
        "status": "CLEAR",
        "matched_list": None,
        "checked_at": "2026-09-06T06:00",
    }


def get_available_balance(account_id: str, currency: str) -> dict[str, Any] | None:
    return _S.get("wire_balances", account_id=account_id, currency=currency)


def record_action(
    kind: str, wire_id: str, detail: dict[str, Any], approval_id: str
) -> dict[str, Any]:
    return _S.record_action(kind, wire_id, detail, approval_id)


def actions() -> list[dict[str, Any]]:
    return _S.actions()


def exceptions() -> list[dict[str, Any]]:
    """The wire exception report — every currently HELD wire with its hold reason."""
    rows = list_wires(status="HELD")
    return sorted(rows, key=lambda r: (str(r.get("hold_reason")), str(r.get("wire_id"))))


def release_wire(wire_id: str, by: str) -> dict[str, Any] | None:
    """Mark a HELD wire RELEASED — a human-only WIRE_REVIEWER action. Closes any OPEN
    `route_to_reviewer` action and records a `release` action for the audit trail. Returns
    the released wire, or None if it does not exist or is not HELD."""
    wire = _S.get("wires", wire_id=wire_id)
    if not wire or wire.get("status") != "HELD":
        return None
    _S.update("wires", {"wire_id": wire_id}, {"status": "RELEASED"})
    _S.update(
        "wire_actions",
        {"subject_id": wire_id, "kind": "route_to_reviewer", "status": "OPEN"},
        {"status": "RELEASED"},
    )
    _S.record_action("release", wire_id, {"by": by}, "")
    return _S.get("wires", wire_id=wire_id)
