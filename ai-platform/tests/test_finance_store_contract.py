"""Contract tests for the seeded prime-finance stores (Phase F).

`-m contract`: needs a reachable Postgres with the finance tables created and the
simulator baseline seeded (CI runs `simulator.cli seed --scenario all` first). Skipped
when no database is reachable.

Covers the SQL backend of `mcp_servers._finance_store`: a round-trip through real tables
(reads come back JSON-safe — dates as ISO strings, `Numeric` as float), the action
write/read path, and that `make seed`'s baseline rows are visible to each domain store.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from mcp_servers import _finance_store
from mcp_servers.cash import store as cash_store
from mcp_servers.corpactions import store as ca_store
from mcp_servers.margin import store as margin_store
from mcp_servers.stockloan import store as sl_store
from mcp_servers.wire import store as wire_store

pytestmark = pytest.mark.contract


@pytest.fixture
def sql_mode() -> Iterator[None]:
    try:
        with _finance_store._engine().connect() as c:
            c.execute(text("select 1"))
    except OperationalError:
        pytest.skip("no database reachable")
    _finance_store.set_memory(False)
    for s in (sl_store, margin_store, ca_store, cash_store, wire_store):
        s.ensure_schema()
    try:
        yield
    finally:
        _finance_store.set_memory(True)


def test_sql_roundtrip_is_json_safe(sql_mode: None) -> None:
    with _finance_store._engine().begin() as conn:
        conn.execute(text("delete from stock_loans where loan_id = 'LN-TEST1'"))
        conn.execute(
            sl_store.stock_loans.insert().values(
                loan_id="LN-TEST1",
                account_id="ACC-TEST",
                security_id="NVDA",
                counterparty="CP-020",
                qty=100,
                rate_bps=45,
                trade_date="2026-07-01",
                open=True,
                return_needed_by="2026-09-10",
            )
        )

    loan = sl_store.get_loan("LN-TEST1")
    assert loan is not None
    assert loan["return_needed_by"] == "2026-09-10"  # date -> ISO string, not a date object
    assert loan["open"] is True
    assert "LN-TEST1" in {r["loan_id"] for r in sl_store.list_loans(None, "ACC-TEST")}

    with _finance_store._engine().begin() as conn:
        conn.execute(text("delete from stock_loans where loan_id = 'LN-TEST1'"))


def test_action_write_and_reset(sql_mode: None) -> None:
    sl_store.reset()  # clears the action table
    assert sl_store.actions() == []
    row = sl_store.record_action("recall", "LN-5001", {"qty": "30000"}, "ap_x")
    assert row["kind"] == "recall" and row["loan_id"] == "LN-5001"
    assert row["action_id"].startswith("SL-")
    assert len(sl_store.actions()) == 1
    sl_store.reset()
    assert sl_store.actions() == []


def test_make_seed_baseline_is_visible_to_each_domain(sql_mode: None) -> None:
    assert (sl_store.get_loan("LN-5001") or {}).get("account_id") == "ACC-88213"
    assert (margin_store.get_margin_call("MC-9001") or {}).get("account_id") == "ACC-88213"
    assert (ca_store.get_ca_event("CA-7001") or {}).get("type") == "CASH_DIVIDEND"
    ent = ca_store.get_entitlement("ACC-88213", "CA-7001") or {}
    assert ent.get("lent_qty") == 30000
    assert (cash_store.get_cash_break("CB-8001") or {}).get("currency") == "USD"
    ladder = cash_store.get_funding_ladder("ACC-88213", "USD")
    assert ladder and all(set(r) == {"time", "flow", "kind"} for r in ladder)


def test_wire_seeded_baseline_and_roundtrip(sql_mode: None) -> None:
    w = wire_store.get_wire("W300917") or {}
    assert w.get("client_id") == "HF-201"
    assert w.get("value_date") == "2026-09-06"  # date -> ISO string
    assert {x["wire_id"] for x in wire_store.list_wires(client_id="HF-201", status="HELD")} == {
        "W300915",
        "W300917",
    }
    assert wire_store.get_wire_screening("HF-205")["status"] == "HIT"
    assert wire_store.get_wire_screening("HF-999")["status"] == "CLEAR"  # fallback row
    assert (wire_store.get_available_balance("ACCT-206", "USD") or {}).get("available") == 1_200_000

    wire_store.reset()
    row = wire_store.record_action("route_to_reviewer", "W300917", {"reason": "x"}, "ap_y")
    assert row["wire_id"] == "W300917" and row["action_id"].startswith("WR-")
    assert [q["wire_id"] for q in wire_store.get_approval_queue()] == ["W300917"]
    wire_store.reset()
    assert wire_store.get_approval_queue() == []
