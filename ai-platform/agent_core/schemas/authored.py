"""The Developer Agent's eval-authoring output (Phase E)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AuthoredScenario(BaseModel):
    failure_code: str
    scenario_id: int
    name: str
    authored_by: str = "agent"  # review mode blocks merge without a human reviewer
    sop_section: str
    scenario_yaml: str  # the planted-chain YAML, ready to drop in simulator/scenarios/
    eval_expect: dict[str, Any] = Field(default_factory=dict)
    corpus_fixtures: list[str] = Field(default_factory=list)
    baseline: dict[str, Any] = Field(default_factory=dict)  # ci.run_eval result
    pr_title: str = ""
    pr_body: str = ""
