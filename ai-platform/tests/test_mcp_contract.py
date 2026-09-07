"""MCP contract tests against the real enterprise + seeded Postgres.

Marked ``contract``: run only where a live enterprise is reachable (CI's ``-m contract``
step, or locally with the stack up). Asserts the specific planted values from
docs/eval-scenarios.md — not shapes, not mocks.

    ENTERPRISE_BASE_URL=http://localhost:8080 uv run pytest -m contract -q
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from mcp_servers import _enterprise
from mcp_servers._enterprise import HttpEnterpriseClient
from mcp_servers.errors import is_error
from mcp_servers.hub import SERVERS, open_session

pytestmark = pytest.mark.contract

_BASE_URL = os.environ.get("ENTERPRISE_BASE_URL", "")

EXPECTED_TOOLS = {
    "trade": {
        "get_trade",
        "get_settlement_status",
        "find_trades",
        "resubmit_settlement",
        "cancel_trade",
    },
    "client": {"get_client", "get_account", "get_ssi", "get_ssi_history", "update_ssi"},
    "counterparty": {"get_counterparty", "get_counterparty_ssi", "get_affirmation"},
    "position": {"get_position", "get_borrow_availability"},
    "reference": {"get_security", "get_market_calendar"},
    "market": {"get_price"},
    "compliance": {"get_restrictions", "get_screening_result"},
    "ops": {"search_logs", "search_knowledge", "find_incidents"},
    "case": {"create_case", "update_case", "propose_action", "get_approval", "log_audit"},
}
EXPECTED_ACCESS = {
    "resubmit_settlement": "write",
    "cancel_trade": "write",
    "update_ssi": "write",
    "create_case": "write*",
    "update_case": "write*",
    "propose_action": "write*",
    "log_audit": "write*",
}


@pytest.fixture(autouse=True)
def _live_enterprise() -> Iterator[None]:
    if not _BASE_URL:
        pytest.skip("ENTERPRISE_BASE_URL not set — needs the running stack")
    _enterprise.set_enterprise_client(HttpEnterpriseClient(_BASE_URL))
    try:
        yield
    finally:
        _enterprise.set_enterprise_client(None)


async def test_every_tool_is_discoverable_with_a_schema() -> None:
    async with open_session() as tools:
        listed = await tools.list()
    by_server: dict[str, set[str]] = {}
    for row in listed:
        by_server.setdefault(row["server"], set()).add(row["tool"])
        assert row["access"] == EXPECTED_ACCESS.get(row["tool"], "read")
        assert row["description"], f"{row['server']}.{row['tool']} has no description"
    assert by_server == EXPECTED_TOOLS
    assert set(by_server) == set(SERVERS)


async def test_scenario_1_counterparty_ssi_stale() -> None:
    async with open_session() as tools:
        trade = await tools.call("trade", "get_trade", trade_id="T100245")
        assert trade["status"] == "FAILED"
        assert trade["account_id"] == "ACC-88213"

        settlement = await tools.call("trade", "get_settlement_status", trade_id="T100245")
        assert settlement["failure_code"] == "COUNTERPARTY_SSI_MISMATCH"
        assert settlement["attempts"]

        ssi = await tools.call("client", "get_ssi", account_id="ACC-88213")
        assert ssi["dtc_participant"] == "1234"
        assert ssi["version"] == 3

        history = await tools.call("client", "get_ssi_history", account_id="ACC-88213")
        assert len(history) >= 3
        assert {v["dtc_participant"] for v in history} >= {"5678", "1234"}

        aff = await tools.call("counterparty", "get_affirmation", trade_id="T100245")
        assert aff["cpty_dtc"] == "5678"

        cpty_ssi = await tools.call("counterparty", "get_counterparty_ssi", cpty_id="CP-017")
        assert cpty_ssi["dtc_participant"] == "5678"

        logs = await tools.call("ops", "search_logs", query="mismatch", trade_id="T100245")
        assert any("5678" in entry["msg"] for entry in logs)


async def test_scenario_3_security_reference_error() -> None:
    async with open_session() as tools:
        sec = await tools.call("reference", "get_security", security_id="XYZQ")
        assert sec["isin"] == "US98765XYZQ1"
        assert sec["cusip"] == "98765XYZ1"

        settlement = await tools.call("trade", "get_settlement_status", trade_id="T100250")
        assert settlement["failure_code"] == "SECURITY_ID_MISMATCH"


async def test_scenario_5_insufficient_position() -> None:
    async with open_session() as tools:
        pos = await tools.call(
            "position", "get_position", account_id="ACC-88213", security_id="NVDA"
        )
        assert pos["qty"] == 40000
        assert pos["available"] == 15000
        assert pos["pending_deliver"] == 25000

        borrow = await tools.call("position", "get_borrow_availability", security_id="NVDA")
        assert borrow["available_qty"] == 100000


async def test_scenario_8_duplicate_trade() -> None:
    async with open_session() as tools:
        settled = await tools.call("trade", "get_trade", trade_id="T100290")
        assert settled["status"] == "SETTLED"
        dupe = await tools.call("trade", "get_settlement_status", trade_id="T100291")
        assert dupe["failure_code"] == "DUPLICATE_SUSPECT"

        related = await tools.call(
            "trade", "find_trades", account_id="ACC-88213", security_id="GOOGL"
        )
        assert {t["trade_id"] for t in related} >= {"T100290", "T100291"}


async def test_scenario_10_no_evidence() -> None:
    async with open_session() as tools:
        settlement = await tools.call("trade", "get_settlement_status", trade_id="T100299")
        assert settlement["failure_code"] == "UNKNOWN"
        assert settlement.get("failure_detail") is None

        logs = await tools.call("ops", "search_logs", query="", trade_id="T100299")
        assert logs == []


async def test_knowledge_tools_return_real_results_through_the_ops_server() -> None:
    # CI ingests the corpus before `-m contract`; retrieval quality is covered in detail
    # by tests/test_knowledge_contract.py — here we just prove the MCP path is wired.
    async with open_session() as tools:
        chunks = await tools.call(
            "ops", "search_knowledge", query="counterparty SSI mismatch settlement failure"
        )
        assert isinstance(chunks, list) and chunks
        assert any(c["doc"] == "Settlement Handbook" for c in chunks)

        incidents = await tools.call(
            "ops",
            "find_incidents",
            query="counterparty affirmed against a superseded DTC participant",
        )
        assert isinstance(incidents, list) and incidents
        assert incidents[0]["incident_id"] == "INC-1001"


async def test_missing_ids_return_not_found_envelopes() -> None:
    async with open_session() as tools:
        result = await tools.call("trade", "get_trade", trade_id="T000000")
        assert is_error(result)
        assert result["code"] == "NOT_FOUND"
        assert result["retryable"] is False
