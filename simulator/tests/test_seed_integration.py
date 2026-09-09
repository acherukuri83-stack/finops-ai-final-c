"""DB-backed tests: run baseline + planter against a real Postgres and assert
the invariants PR2 promises. Skipped if no database is reachable (e.g. a
sandbox with no Postgres at all) rather than failing the whole suite.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Connection, text
from sqlalchemy.exc import OperationalError

from simulator import baseline, planter
from simulator.db import connect
from simulator.scenario import Scenario

SCENARIOS = Path(__file__).resolve().parents[1] / "scenarios"


@pytest.fixture
def conn() -> Iterator[Connection]:
    try:
        with connect() as c:
            c.execute(text("select 1"))
            yield c
    except OperationalError:
        pytest.skip("no database reachable at DATABASE_URL")


def test_baseline_meets_required_invariants(conn: Connection) -> None:
    baseline.populate(conn)

    failed = conn.execute(text("select count(*) from trades where status = 'FAILED'")).scalar_one()
    assert failed >= 8, "baseline must include >= 8 FAILED trades unrelated to planted scenarios"

    distinct_codes = conn.execute(
        text("select count(distinct failure_code) from trades where status = 'FAILED'")
    ).scalar_one()
    assert distinct_codes >= 2, "baseline FAILED trades must span more than one failure_code"

    hf101_settled = conn.execute(
        text("select count(*) from trades where account_id = 'ACC-88213' and status = 'SETTLED'")
    ).scalar_one()
    assert hf101_settled >= 5, "HF101 must have >= 5 healthy SETTLED trades in the baseline"

    n_clients = conn.execute(text("select count(*) from clients")).scalar_one()
    n_accounts = conn.execute(text("select count(*) from accounts")).scalar_one()
    n_securities = conn.execute(text("select count(*) from securities")).scalar_one()
    n_cptys = conn.execute(text("select count(*) from counterparties")).scalar_one()
    assert n_clients >= 45
    assert n_accounts >= 75
    assert n_securities >= 195
    assert n_cptys >= 18


def test_baseline_populates_the_prime_finance_tables(conn: Connection) -> None:
    baseline.populate(conn)

    loan = conn.execute(
        text("select account_id, return_needed_by from stock_loans where loan_id = 'LN-5001'")
    ).one()
    assert loan[0] == "ACC-88213"
    for tbl, key, val in [
        ("margin_calls", "call_id", "MC-9001"),
        ("ca_events", "event_id", "CA-7001"),
        ("cash_breaks", "break_id", "CB-8001"),
    ]:
        n = conn.execute(
            text(f"select count(*) from {tbl} where {key} = :v"), {"v": val}
        ).scalar_one()
        assert n == 1, f"{tbl} missing {val} after baseline"


def test_prime_finance_planter_handlers_are_idempotent(conn: Connection) -> None:
    """The margin / corpactions / cash plant handlers land with a scenario that needs
    them; exercise each directly here (delete-then-insert, safe to re-run)."""
    baseline.populate(conn)
    block = {
        "margin_calls": [
            {
                "id": "MC-TEST",
                "account": "ACC-88213",
                "issued": "2026-09-05",
                "due_by": "2026-09-06",
                "amount": 9_000_000,
            }
        ],
        "ca_events": [
            {
                "id": "CA-TEST",
                "security": "AAPL",
                "type": "CASH_DIVIDEND",
                "record_date": "2026-09-01",
                "pay_date": "2026-09-10",
                "gross_rate": 0.3,
            }
        ],
        "ca_entitlements": [
            {
                "account": "ACC-88213",
                "event": "CA-TEST",
                "record_date_qty": 5000,
                "held_qty": 1000,
                "lent_qty": 4000,
            }
        ],
        "cash_breaks": [
            {
                "id": "CB-TEST",
                "account": "ACC-88213",
                "currency": "GBP",
                "projected_close": -3_000_000,
                "funding_cutoff": "2026-09-06T16:00",
            }
        ],
    }
    for _ in range(2):  # idempotent
        for key, rows in block.items():
            planter.HANDLERS[key](conn, rows)

    assert (
        conn.execute(text("select amount from margin_calls where call_id = 'MC-TEST'")).scalar_one()
        == 9_000_000
    )
    assert (
        conn.execute(
            text("select lent_qty from ca_entitlements where event_id = 'CA-TEST'")
        ).scalar_one()
        == 4000
    )
    assert (
        conn.execute(
            text("select currency from cash_breaks where break_id = 'CB-TEST'")
        ).scalar_one()
        == "GBP"
    )


def test_scenario_30_plants_an_open_loan_and_a_settlement_fail(conn: Connection) -> None:
    baseline.populate(conn)
    planter.plant(conn, Scenario.load(SCENARIOS / "030_mixed_domain_client.yaml"))

    loan = conn.execute(
        text("select account_id, open, return_needed_by from stock_loans where loan_id = 'LN-5001'")
    ).one()
    assert loan[0] == "ACC-88213" and loan[1] is True
    trade = conn.execute(
        text("select status, failure_code from trades where trade_id = 'T100245'")
    ).one()
    assert trade == ("FAILED", "COUNTERPARTY_SSI_MISMATCH")


def test_seed_scenario_1_plants_expected_values(conn: Connection) -> None:
    baseline.populate(conn)
    sc = Scenario.load(SCENARIOS / "001_counterparty_ssi_stale.yaml")
    planter.plant(conn, sc)

    ssi_versions = conn.execute(
        text("select count(*) from ssi_versions where account_id = 'ACC-88213'")
    ).scalar_one()
    assert ssi_versions >= 3, ">= 3 SSI versions must exist for ACC-88213 after Sc. 1 plant"

    affirmation_dtc = conn.execute(
        text("select cpty_dtc from affirmations where trade_id = 'T100245'")
    ).scalar_one()
    assert affirmation_dtc == "5678"

    trade_status, failure_code = conn.execute(
        text("select status, failure_code from trades where trade_id = 'T100245'")
    ).one()
    assert trade_status == "FAILED"
    assert failure_code == "COUNTERPARTY_SSI_MISMATCH"

    cpty_dtc = conn.execute(
        text("select dtc_participant from counterparty_ssi where cpty_id = 'CP-017'")
    ).scalar_one()
    assert cpty_dtc == "5678"


def test_seed_is_deterministic_on_reseed(conn: Connection) -> None:
    sc = Scenario.load(SCENARIOS / "001_counterparty_ssi_stale.yaml")

    baseline.populate(conn)
    planter.plant(conn, sc)
    first = conn.execute(text("select trade_id, booked_at from trades order by trade_id")).all()

    baseline.populate(conn)
    planter.plant(conn, sc)
    second = conn.execute(text("select trade_id, booked_at from trades order by trade_id")).all()

    assert first == second, "make seed must be deterministic: same ids and timestamps on reseed"


def test_seed_all_plants_every_scenario_without_collision(conn: Connection) -> None:
    baseline.populate(conn)
    for f in sorted(SCENARIOS.glob("*.yaml")):
        planter.plant(conn, Scenario.load(f))
