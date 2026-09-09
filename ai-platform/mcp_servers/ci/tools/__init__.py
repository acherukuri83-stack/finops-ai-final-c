"""ci-server tools (Phase E — review mode). Docstrings are the exposed descriptions.

Deterministic checks the Developer Agent runs over a PR: static analysis, security scan,
coverage, tests, and `run_eval` for a touched scenario. All read-only — the model
*interprets* these results, it never decides pass/fail on them. Fixture-backed
(`mcp_servers.ci.store`).
"""

from __future__ import annotations

from typing import Any

from mcp_servers.ci import store


async def run_static_analysis(pr_id: str) -> Any:
    """ruff / mypy findings for a PR: [{tool, file, line, code, message}]. Empty == clean."""
    return store.static_analysis(pr_id)


async def run_security_scan(pr_id: str) -> Any:
    """Security scan hits for a PR: [{rule, file, line, severity, message}]. Rule ids are stable."""
    return store.security_scan(pr_id)


async def get_test_coverage(pr_id: str) -> Any:
    """Coverage before/after the PR: {before_pct, after_pct, delta_pct, uncovered_new_lines}."""
    return store.coverage(pr_id)


async def run_tests(pr_id: str) -> Any:
    """Test outcome for a PR: {passed, failed, failing: [names]}."""
    return store.tests(pr_id)


async def run_eval(scenario: str) -> Any:
    """Baseline eval for one scenario id: {scenario, runs, passed, notes}. Costs real model calls when live; fixture-backed here."""
    return store.eval_run(scenario)
