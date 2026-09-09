"""In-process fixture store for the `ci` server (Phase E — review mode).

Deterministic-check results keyed by PR id. Facts only — the review decides what they
mean.
"""

from __future__ import annotations

from typing import Any

_STATIC: dict[str, list[dict[str, Any]]] = {
    "PR-19": [],
    "PR-20": [],
    "PR-21": [],
    "PR-25": [],
}

_SECURITY: dict[str, list[dict[str, Any]]] = {
    "PR-19": [
        {
            "rule": "FINOPS-SEC-002",
            "file": "ai-platform/mcp_servers/trade/tools/__init__.py",
            "line": 42,
            "severity": "HIGH",
            "message": "write-shaped tool with no approval_id parameter",
        }
    ],
    "PR-20": [],
    "PR-21": [],
    "PR-25": [],
}

_COVERAGE: dict[str, dict[str, Any]] = {
    "PR-19": {"before_pct": 87.4, "after_pct": 86.1, "delta_pct": -1.3, "uncovered_new_lines": 6},
    "PR-20": {"before_pct": 87.4, "after_pct": 87.4, "delta_pct": 0.0, "uncovered_new_lines": 0},
    "PR-21": {"before_pct": 87.4, "after_pct": 87.6, "delta_pct": 0.2, "uncovered_new_lines": 0},
    "PR-25": {"before_pct": 87.4, "after_pct": 87.4, "delta_pct": 0.0, "uncovered_new_lines": 0},
}

_TESTS: dict[str, dict[str, Any]] = {
    "PR-19": {"passed": 90, "failed": 0, "failing": []},
    "PR-20": {
        "passed": 89,
        "failed": 1,
        "failing": ["simulator/tests/test_scenarios.py::test_scenario_1_shape"],
    },
    "PR-21": {"passed": 91, "failed": 0, "failing": []},
    "PR-25": {"passed": 91, "failed": 0, "failing": []},
}

_EVAL: dict[str, dict[str, Any]] = {
    "1": {"scenario": "1", "runs": 3, "passed": 3, "notes": "baseline green"},
    "31": {
        "scenario": "31",
        "runs": 3,
        "passed": 0,
        "notes": "authored_by: agent — baseline correctly fails on first run",
    },
}


def static_analysis(pr_id: str) -> list[dict[str, Any]]:
    return [dict(x) for x in _STATIC.get(pr_id, [])]


def security_scan(pr_id: str) -> list[dict[str, Any]]:
    return [dict(x) for x in _SECURITY.get(pr_id, [])]


def coverage(pr_id: str) -> dict[str, Any]:
    return dict(
        _COVERAGE.get(
            pr_id, {"before_pct": 0.0, "after_pct": 0.0, "delta_pct": 0.0, "uncovered_new_lines": 0}
        )
    )


def tests(pr_id: str) -> dict[str, Any]:
    return dict(_TESTS.get(pr_id, {"passed": 0, "failed": 0, "failing": []}))


def eval_run(scenario: str) -> dict[str, Any]:
    return dict(
        _EVAL.get(
            str(scenario), {"scenario": str(scenario), "runs": 0, "passed": 0, "notes": "not run"}
        )
    )
