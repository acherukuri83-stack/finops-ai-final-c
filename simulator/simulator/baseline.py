"""Baseline population: a full, deterministic synthetic broker/dealer world.

Truncates and repopulates every Phase A table on each call so `make seed` is a
clean, reproducible reset. Scenario-owned entities (HEDGE_FUND_101 / ACC-88213 /
CP-017's *current instructions and trade history*) get their identity here but no
SSI/trade data — the planter owns those facts entirely, per scenario.

Deterministic: a fixed RNG seed plus `RESTART IDENTITY` on every serial-keyed
table make two successive `make seed` runs produce identical ids and timestamps.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import Connection, text

from simulator.ids import business_days_ending
from simulator.tables import (
    ALL_TABLES,
    accounts,
    app_logs,
    borrow_availability,
    clients,
    counterparties,
    counterparty_ssi,
    market_calendar,
    positions,
    prices,
    restrictions,
    screening_results,
    securities,
    ssi_versions,
    trades,
)

SEED = 20260101
CALENDAR_END = date(2026, 9, 4)
PRICE_DAYS = 30
TRADE_WINDOW_DAYS = 10
N_CLIENTS = 50
N_ACCOUNTS = 80
N_SECURITIES = 200
N_COUNTERPARTIES = 20
N_BASELINE_TRADES = 500
N_LOG_LINES = 20_000
N_HF101_HEALTHY_TRADES = 8

HF101 = "HEDGE_FUND_101"
HF101_ACCOUNT = "ACC-88213"
CP_SCENARIO = "CP-017"

# Securities referenced by planted scenarios (must exist as ordinary, healthy
# baseline securities so scenario trades book against something real). XYZQ is
# deliberately excluded — it is planted by Sc. 3 with an inconsistent cusip.
SCENARIO_SECURITIES = ["AAPL", "NVDA", "AMZN", "GOOGL", "META"]

FAILURE_CODE_POOL = [
    "COUNTERPARTY_SSI_MISMATCH",
    "INSUFFICIENT_POSITION",
    "SECURITY_ID_MISMATCH",
    "ACCOUNT_RESTRICTED",
    "UNKNOWN",
    "DUPLICATE_SUSPECT",
]

LOG_SERVICES = [
    "settlement-engine",
    "booking-service",
    "reference-service",
    "position-service",
    "affirmation-gateway",
]
LOG_LEVELS_WEIGHTED = ["INFO"] * 8 + ["DEBUG"] * 3 + ["WARN"] * 2 + ["ERROR"] * 1
LOG_TEMPLATES = [
    "heartbeat ok",
    "batch cycle complete in {ms}ms",
    "processed {n} records",
    "cache refresh for {svc} completed",
    "connection pool at {n}% utilization",
    "retry succeeded after {n} attempt(s)",
    "reconciliation pass complete, {n} items checked",
    "queue depth {n}",
    "trade {trade_id} status check ok",
    "trade {trade_id} booked",
    "trade {trade_id} settlement attempt recorded",
]


@dataclass
class BaselineIds:
    client_ids: list[str]
    account_ids: list[str]
    account_client: dict[str, str]
    security_ids: list[str]
    cpty_ids: list[str]


def _client_id(i: int) -> str:
    return HF101 if i == 0 else f"CLIENT_{i:03d}"


def _account_id(i: int) -> str:
    return HF101_ACCOUNT if i == 0 else f"ACC-{10000 + i}"


def _cpty_id(i: int) -> str:
    return CP_SCENARIO if i == 0 else f"CP-{100 + i:03d}"


def _random_ticker(rng: random.Random, taken: set[str]) -> str:
    while True:
        n = rng.randint(3, 5)
        t = "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(n))
        if t not in taken and t != "XYZQ":
            taken.add(t)
            return t


def _isin_cusip(rng: random.Random, ticker: str) -> tuple[str, str]:
    digits = "".join(str(rng.randint(0, 9)) for _ in range(9))
    isin = f"US{digits}{rng.randint(0, 9)}"
    cusip = f"{digits}{ticker[0] if ticker else 'X'}"[:9]
    return isin, cusip


def populate(conn: Connection) -> BaselineIds:
    rng = random.Random(SEED)

    for table in ALL_TABLES:
        conn.execute(text(f'TRUNCATE TABLE "{table.name}" RESTART IDENTITY CASCADE'))

    client_ids = [_client_id(i) for i in range(N_CLIENTS)]
    conn.execute(
        clients.insert(),
        [
            {
                "client_id": cid,
                "name": "Hedge Fund 101" if cid == HF101 else f"Client {cid.split('_')[-1]}",
                "type": "HEDGE_FUND"
                if cid == HF101
                else rng.choice(["HEDGE_FUND", "ASSET_MANAGER", "PENSION_FUND", "INSURER", "BANK"]),
                "status": "ACTIVE",
            }
            for cid in client_ids
        ],
    )

    # Every client gets >=1 account; remaining accounts distributed round-robin.
    account_ids = [_account_id(0)]
    account_client = {account_ids[0]: HF101}
    remaining_clients = client_ids[1:]
    for i, cid in enumerate(remaining_clients, start=1):
        aid = _account_id(i)
        account_ids.append(aid)
        account_client[aid] = cid
    extra_needed = N_ACCOUNTS - len(account_ids)
    for _j in range(extra_needed):
        aid = _account_id(len(account_ids))
        account_ids.append(aid)
        account_client[aid] = rng.choice(remaining_clients)

    conn.execute(
        accounts.insert(),
        [
            {
                "account_id": aid,
                "client_id": account_client[aid],
                "custodian": "DTC",
                "status": "ACTIVE",
            }
            for aid in account_ids
        ],
    )

    # SSI history for every account except the scenario-owned one (the planter
    # supplies ACC-88213's full history per scenario).
    window_start = CALENDAR_END - timedelta(days=400)
    for aid in account_ids:
        if aid == HF101_ACCOUNT:
            continue
        n_versions = rng.choices([1, 2, 3], weights=[6, 3, 1])[0]
        cursor = window_start
        for v in range(1, n_versions + 1):
            valid_from = cursor
            is_last = v == n_versions
            valid_to = None if is_last else valid_from + timedelta(days=rng.randint(60, 150))
            conn.execute(
                ssi_versions.insert().values(
                    account_id=aid,
                    version=v,
                    dtc_participant=str(rng.randint(1000, 9999)),
                    agent_bic=None,
                    valid_from=valid_from,
                    valid_to=valid_to,
                    updated_at=datetime.combine(valid_from, time(9, 0)),
                    updated_by=rng.choice(["ops.mchen", "ops.jsmith", "ops.klee", "ops.rpatel"]),
                )
            )
            cursor = valid_to if valid_to else cursor

    # Securities: pinned scenario tickers (healthy, consistent reference data)
    # plus randomly generated fill.
    taken = set(SCENARIO_SECURITIES)
    security_ids = list(SCENARIO_SECURITIES)
    while len(security_ids) < N_SECURITIES:
        security_ids.append(_random_ticker(rng, taken))

    sec_rows = []
    for sid in security_ids:
        isin, cusip = _isin_cusip(rng, sid)
        sec_rows.append(
            {
                "security_id": sid,
                "isin": isin,
                "cusip": cusip,
                "description": f"{sid} Common Stock",
                "settle_cycle": "T+1",
                "status": "ACTIVE",
            }
        )
    conn.execute(securities.insert(), sec_rows)

    # Market calendar + 30 business days of prices per security.
    price_days = business_days_ending(CALENDAR_END, PRICE_DAYS)
    calendar_start = price_days[0]
    calendar_end = CALENDAR_END + timedelta(days=10)
    cal_rows = []
    d = calendar_start
    while d <= calendar_end:
        is_holiday = d == date(2026, 9, 7)  # Labor Day (fictional-calendar realism)
        cal_rows.append(
            {
                "market": "US",
                "calendar_date": d,
                "is_business_day": d.weekday() < 5 and not is_holiday,
                "holiday_name": "Labor Day" if is_holiday else None,
            }
        )
        d += timedelta(days=1)
    conn.execute(market_calendar.insert(), cal_rows)

    price_rows = []
    for sid in security_ids:
        p = rng.uniform(20, 450)
        for d2 in price_days:
            p = max(1.0, p * (1 + rng.uniform(-0.02, 0.02)))
            price_rows.append({"security_id": sid, "price_date": d2, "close_price": round(p, 4)})
    conn.execute(prices.insert(), price_rows)

    # Counterparties: CP-017 is scenario-owned (no baseline SSI row); the rest
    # get one current, valid instruction.
    cpty_ids = [_cpty_id(i) for i in range(N_COUNTERPARTIES)]
    conn.execute(
        counterparties.insert(),
        [
            {
                "cpty_id": cid,
                "name": f"Counterparty {cid}",
                "status": "ACTIVE",
            }
            for cid in cpty_ids
        ],
    )
    for cid in cpty_ids:
        if cid == CP_SCENARIO:
            continue
        conn.execute(
            counterparty_ssi.insert().values(
                cpty_id=cid,
                dtc_participant=str(rng.randint(1000, 9999)),
                valid_to=CALENDAR_END + timedelta(days=365),
            )
        )

    # Trades: ~500 over the last 10 business days, ~95% SETTLED, the rest
    # FAILED for a spread of reasons unrelated to the planted scenarios.
    trade_days = business_days_ending(CALENDAR_END - timedelta(days=1), TRADE_WINDOW_DAYS)
    non_hf101_accounts = [a for a in account_ids if a != HF101_ACCOUNT]
    trade_rows: list[dict[str, Any]] = []
    trade_positions: dict[tuple[str, str], list[dict[str, Any]]] = {}
    n_failed_target = max(8, round(N_BASELINE_TRADES * 0.05))

    def make_trade(idx: int, account_id: str, forced_status: str | None = None) -> dict[str, Any]:
        aid = account_id
        cid = account_client[aid]
        sid = rng.choice(security_ids)
        td = rng.choice(trade_days)
        sd = td + timedelta(days=1)
        while sd.weekday() >= 5:
            sd += timedelta(days=1)
        qty = rng.randint(100, 20000)
        side = rng.choice(["BUY", "SELL"])
        price = round(rng.uniform(10, 400), 2)
        status = forced_status or ("FAILED" if idx < n_failed_target else "SETTLED")
        failure_code = (
            FAILURE_CODE_POOL[idx % len(FAILURE_CODE_POOL)] if status == "FAILED" else None
        )
        trade_id = f"T200{idx:03d}"
        trade_positions.setdefault((aid, sid), []).append({"qty": qty, "side": side})
        return {
            "trade_id": trade_id,
            "client_id": cid,
            "account_id": aid,
            "security_id": sid,
            "qty": qty,
            "side": side,
            "price": price,
            "trade_date": td,
            "settle_date": sd,
            "status": status,
            "failure_code": failure_code,
            "cpty_id": rng.choice([c for c in cpty_ids if c != CP_SCENARIO]),
            "booked_at": datetime.combine(td, time(rng.randint(8, 17), rng.randint(0, 59))),
        }

    # Shuffle failed-vs-settled assignment order but keep it seed-deterministic.
    order = list(range(N_BASELINE_TRADES))
    rng.shuffle(order)
    for idx in order:
        trade_rows.append(make_trade(idx, rng.choice(non_hf101_accounts)))

    # HF101 healthy settled trades, dedicated and separate from the scenario's
    # own T100xxx trades — proves "no shortcuts" for the agent.
    hf101_start = N_BASELINE_TRADES
    for j in range(N_HF101_HEALTHY_TRADES):
        row = make_trade(hf101_start + j, HF101_ACCOUNT, forced_status="SETTLED")
        row["trade_id"] = f"T2009{j:02d}"
        trade_rows.append(row)

    conn.execute(trades.insert(), trade_rows)

    # Positions for every (account, security) pair that traded in baseline.
    position_rows = []
    for (aid, sid), fills in trade_positions.items():
        net = sum(f["qty"] if f["side"] == "BUY" else -f["qty"] for f in fills)
        qty = max(net, rng.randint(100, 5000))
        available = max(0, qty - rng.randint(0, min(qty, 500)))
        position_rows.append(
            {
                "account_id": aid,
                "security_id": sid,
                "as_of": CALENDAR_END,
                "qty": qty,
                "available": available,
                "pending_deliver": max(0, qty - available),
                "pending_receive": 0,
            }
        )
    # Guarantee: ACC-88213 x AAPL has ample position (Sc. 1/9/12 assume "position sufficient").
    position_rows.append(
        {
            "account_id": HF101_ACCOUNT,
            "security_id": "AAPL",
            "as_of": CALENDAR_END,
            "qty": 50_000,
            "available": 50_000,
            "pending_deliver": 0,
            "pending_receive": 0,
        }
    )
    conn.execute(positions.insert(), position_rows)

    # Borrow availability for a subset of securities (incl. NVDA — Sc. 5's
    # planter overwrites it with the scenario-specific shortfall numbers).
    borrow_pool = rng.sample(security_ids, k=min(60, len(security_ids)))
    if "NVDA" not in borrow_pool:
        borrow_pool.append("NVDA")
    conn.execute(
        borrow_availability.insert(),
        [
            {
                "security_id": sid,
                "available_qty": rng.randint(1000, 200_000),
                "rate": round(rng.uniform(0.1, 3.5), 4),
                "recalls": [],
            }
            for sid in borrow_pool
        ],
    )

    # A few realistic, inactive/active restrictions elsewhere (never on ACC-88213).
    restriction_accounts = rng.sample(
        [a for a in non_hf101_accounts], k=min(10, len(non_hf101_accounts))
    )
    conn.execute(
        restrictions.insert(),
        [
            {
                "account_id": aid,
                "type": rng.choice(["SETTLEMENT_HOLD", "KYC_REVIEW", "MARGIN_CALL"]),
                "reason": "periodic review",
                "set_by": "compliance.rlee",
                "set_at": datetime.combine(
                    CALENDAR_END - timedelta(days=rng.randint(1, 30)), time(10, 0)
                ),
                "active": rng.random() < 0.4,
            }
            for aid in restriction_accounts
        ],
    )

    # Screening: Phase A is always CLEAR.
    conn.execute(
        screening_results.insert(),
        [
            {
                "client_id": cid,
                "status": "CLEAR",
                "checked_at": datetime.combine(CALENDAR_END, time(6, 0)),
            }
            for cid in client_ids
        ],
    )

    _populate_logs(conn, rng, trade_rows)

    return BaselineIds(
        client_ids=client_ids,
        account_ids=account_ids,
        account_client=account_client,
        security_ids=security_ids,
        cpty_ids=cpty_ids,
    )


def _populate_logs(conn: Connection, rng: random.Random, trade_rows: list[dict[str, Any]]) -> None:
    window_start = datetime.combine(CALENDAR_END - timedelta(days=14), time(0, 0))
    window_seconds = int(
        (datetime.combine(CALENDAR_END, time(23, 59)) - window_start).total_seconds()
    )
    trade_ids = [t["trade_id"] for t in trade_rows]
    batch: list[dict[str, Any]] = []
    for _ in range(N_LOG_LINES):
        svc = rng.choice(LOG_SERVICES)
        template = rng.choice(LOG_TEMPLATES)
        msg = template.format(
            ms=rng.randint(5, 4000),
            n=rng.randint(1, 500),
            svc=svc,
            trade_id=rng.choice(trade_ids),
        )
        ts = window_start + timedelta(seconds=rng.randint(0, window_seconds))
        batch.append(
            {
                "ts": ts,
                "svc": svc,
                "level": rng.choice(LOG_LEVELS_WEIGHTED),
                "msg": msg,
                "trade_id": None,
            }
        )
    conn.execute(app_logs.insert(), batch)
