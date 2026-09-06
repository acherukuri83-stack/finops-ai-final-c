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
