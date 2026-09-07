"""End-to-end scenario checks — real Claude calls + real retrieval. Costs money.

Marked `eval`: not in CI. The Weekend-3 harness adds n=3 scoring and `SCORECARD.md`; this
is the developer smoke that the loop reaches the right outcome. Run with the stack up and
the corpus ingested:

    make up && make ingest --fixtures CN-2026-081
    make seed SCENARIO=1
    ENTERPRISE_BASE_URL=http://localhost:8080 ANTHROPIC_API_KEY=... \
      uv run pytest -m eval -q evals/test_scenarios.py -k scenario_1
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterator

import pytest

from agent_core.loop import investigate
from agent_core.reasoning.model_client import AnthropicModelClient
from agent_core.schemas.finding import Finding, Outcome
from mcp_servers import _enterprise
from mcp_servers._enterprise import HttpEnterpriseClient

pytestmark = [pytest.mark.eval, pytest.mark.asyncio(loop_scope="module")]

_BASE_URL = os.environ.get("ENTERPRISE_BASE_URL", "")
_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
_client: AnthropicModelClient | None = None


def _model() -> AnthropicModelClient:
    global _client
    if _client is None:
        _client = AnthropicModelClient(_KEY)
    return _client


@pytest.fixture(autouse=True)
def _live() -> Iterator[None]:
    if not (_BASE_URL and _KEY):
        pytest.skip("needs ENTERPRISE_BASE_URL + ANTHROPIC_API_KEY + a seeded, ingested stack")
    _enterprise.set_enterprise_client(HttpEnterpriseClient(_BASE_URL))
    try:
        yield
    finally:
        _enterprise.set_enterprise_client(None)


def _seed(scenario: str, fixtures: list[str]) -> None:
    # simulator is its own uv project — run it through `uv run`, not this venv's python.
    subprocess.run(
        ["uv", "run", "python", "-m", "simulator.cli", "seed", "--scenario", scenario],
        cwd="../simulator",
        check=True,
    )
    subprocess.run([sys.executable, "-m", "knowledge.ingest", "--fixtures", *fixtures], check=True)


async def _run(scenario: str, *, fixtures: list[str], trade_id: str) -> Finding:
    _seed(scenario, fixtures)
    finding = await investigate(trade_id, client=_model(), scenario_id=scenario)
    print(f"\n=== scenario {scenario} Finding ===\n{finding.model_dump_json(indent=2)}\n")
    return finding


def _refs(finding: Finding) -> set[str]:
    return {e.ref for e in finding.evidence}


async def test_scenario_1_counterparty_stale() -> None:
    f = await _run("1", fixtures=[], trade_id="T100245")
    assert f.outcome is Outcome.RESOLVED_CAUSE
    assert f.root_cause == "COUNTERPARTY_INSTRUCTION_STALE"
    assert "Settlement Handbook §8.4" in _refs(f)
    assert "INC-1001" in _refs(f)
    assert "update_ssi" in {r.action_type for r in f.rejected_alternatives}
    assert "resubmit_settlement" in {a.action_type for a in f.proposed_actions}


async def test_scenario_2_flips_with_the_fixture() -> None:
    f = await _run("2", fixtures=["CN-2026-081"], trade_id="T100245")
    assert f.root_cause == "CLIENT_SSI_STALE"
    assert "update_ssi" in {a.action_type for a in f.proposed_actions}


async def test_scenario_2_without_fixture_blames_the_counterparty() -> None:
    f = await _run("2", fixtures=[], trade_id="T100245")
    assert f.root_cause == "COUNTERPARTY_INSTRUCTION_STALE"


async def test_scenario_3_reference_data() -> None:
    f = await _run("3", fixtures=[], trade_id="T100250")
    assert "escalate" in {a.action_type for a in f.proposed_actions}
    assert "resubmit_settlement" not in {a.action_type for a in f.proposed_actions}


async def test_scenario_10_insufficient_evidence() -> None:
    f = await _run("10", fixtures=[], trade_id="T100299")
    assert f.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert len(f.checked) >= 5


async def test_scenario_12_tool_degraded() -> None:
    # requires FAULT_INJECT=trade.settlement_status:503 on the enterprise process
    f = await _run("12", fixtures=[], trade_id="T100245")
    assert f.outcome is Outcome.TOOL_DEGRADED
