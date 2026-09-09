"""The `Review` contract — the Developer Agent's PR-review output (Phase E)."""

from __future__ import annotations

from pydantic import BaseModel, Field

SEVERITIES = ("BLOCKER", "MAJOR", "MINOR", "NIT")
RECOMMENDATIONS = ("REQUEST_CHANGES", "APPROVE", "COMMENT")


class ReviewFinding(BaseModel):
    severity: str  # BLOCKER | MAJOR | MINOR | NIT
    file: str
    line: int = 0
    message: str
    evidence: str = ""  # a standard § ref, a scan rule id, a coverage delta
    suggested_patch: str = ""


class Review(BaseModel):
    pr_id: str
    surfaces: list[str] = Field(default_factory=list)  # mcp_contract | agent_policy | prompt | …
    findings: list[ReviewFinding] = Field(default_factory=list)
    recommendation: str = "COMMENT"
    summary: str = ""
