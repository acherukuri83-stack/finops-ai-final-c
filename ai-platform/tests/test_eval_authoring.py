"""Phase E — Developer Agent, eval-authoring mode.

Deterministic. `author_scenario` drafts a planted-chain YAML + `expect:` block for a
failure code, labelled `authored_by: agent`. The produced YAML must parse, use only known
`plant:` keys, contain no interpretive ("leak") language, and carry the label that
PR-review mode blocks on.
"""

from __future__ import annotations

from typing import Any

import pytest
import yaml

from agent_core.eval_authoring import author_scenario

# mirrors simulator/simulator/scenario.py (not importable from the ai-platform venv)
_PLANT_KEYS = {
    "accounts.ssi",
    "counterparties.ssi",
    "trades",
    "settlement_attempts",
    "affirmations",
    "positions",
    "borrow",
    "restrictions",
    "securities",
    "loans",
    "lending",
    "margin_calls",
    "ca_events",
    "ca_entitlements",
    "cash_breaks",
    "logs",
    "incidents",
    "corpus_fixtures",
}
_LEAK_WORDS = ("stale", "wrong side", "never picked up", "root cause", "because", "should have")


def _walk_strings(v: object) -> list[str]:
    if isinstance(v, str):
        return [v]
    if isinstance(v, dict):
        return [s for x in v.values() for s in _walk_strings(x)]
    if isinstance(v, list):
        return [s for x in v for s in _walk_strings(x)]
    return []


def _assert_valid_scenario(doc: dict[str, Any]) -> None:
    plant: dict[str, Any] = doc.get("plant", {})
    expect: dict[str, Any] = doc.get("expect", {})
    assert set(plant) <= _PLANT_KEYS, set(plant) - _PLANT_KEYS
    leaks = [s for s in _walk_strings(plant) if any(w in s.lower() for w in _LEAK_WORDS)]
    assert not leaks, leaks
    assert "root_cause" in expect or "outcome" in expect


async def test_authors_a_valid_scenario_with_the_agent_label() -> None:
    out = await author_scenario("COUNTERPARTY_INSTRUCTION_EXPIRED")

    assert out.authored_by == "agent"
    assert out.sop_section == "Settlement Handbook §8.4"
    assert out.eval_expect["root_cause"] == "COUNTERPARTY_INSTRUCTION_EXPIRED"
    assert out.eval_expect["action_class"] == "escalate"
    assert "update_ssi" in out.eval_expect["unsafe_actions"]

    doc = yaml.safe_load(out.scenario_yaml)
    assert doc["authored_by"] == "agent"
    _assert_valid_scenario(doc)
    assert doc["expect"]["root_cause"] == "COUNTERPARTY_INSTRUCTION_EXPIRED"


async def test_baseline_is_reported_for_the_human_reviewer() -> None:
    out = await author_scenario("INSUFFICIENT_POSITION")
    assert out.eval_expect["root_cause"] == "DELIVERY_SHORTFALL"
    assert "runs" in out.baseline and "passed" in out.baseline
    assert "human reviewer" in out.pr_body


async def test_unknown_failure_code_is_out_of_scope() -> None:
    out = await author_scenario("NOT_A_REAL_CODE")
    assert out.scenario_yaml == ""
    assert "no authoring template" in out.pr_body


async def test_the_drafted_scenario_would_be_blocked_by_review() -> None:
    # PR-review mode forces REQUEST_CHANGES on any `authored_by: agent` scenario.
    from agent_core.review import _code_rules

    out = await author_scenario("SECURITY_ID_MISMATCH")
    path = f"simulator/scenarios/0{out.scenario_id}_x.yaml"
    diff = f"--- /dev/null\n+++ b/{path}\n" + "\n".join(
        "+" + line for line in out.scenario_yaml.splitlines()
    )
    findings = _code_rules([path], diff)
    assert any("human reviewer" in f.message for f in findings)


@pytest.mark.parametrize(
    "code", ["COUNTERPARTY_INSTRUCTION_EXPIRED", "INSUFFICIENT_POSITION", "SECURITY_ID_MISMATCH"]
)
async def test_every_template_renders_loadable_yaml(code: str) -> None:
    out = await author_scenario(code)
    _assert_valid_scenario(yaml.safe_load(out.scenario_yaml))
