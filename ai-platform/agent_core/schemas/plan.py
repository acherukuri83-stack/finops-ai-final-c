"""The planner's structured output. One Plan per (re)planning turn."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PlanStep(BaseModel):
    server: str  # MCP server, e.g. "trade"
    tool: str  # tool on that server, e.g. "get_settlement_status"
    args: dict[str, str] = Field(default_factory=dict)  # string args only (ids, queries)
    why: str  # one line: what this step is meant to establish


class Plan(BaseModel):
    assumptions: list[str] = Field(default_factory=list)  # each is re-checked against observations
    steps: list[PlanStep] = Field(default_factory=list)
