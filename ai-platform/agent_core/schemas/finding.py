"""The Finding contract. Every agent, every phase, returns this shape."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Outcome(StrEnum):
    RESOLVED_CAUSE = "RESOLVED_CAUSE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    TOOL_DEGRADED = "TOOL_DEGRADED"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    SKELETON = "SKELETON"  # W1 walking skeleton only


class SubjectRef(BaseModel):
    type: str  # trade | account | wire | job | pr
    id: str


class EvidenceRef(BaseModel):
    kind: str  # tool | knowledge | incident | log
    ref: str  # tool result id, or "doc §section", or incident id
    cited: bool = True


class ProposedAction(BaseModel):
    action_type: str
    params: dict[str, str] = Field(default_factory=dict)
    rationale: str
    impact: list[SubjectRef] = Field(default_factory=list)
    reversible: bool = True
    approval_id: str | None = None  # set by the loop after case.propose_action registers it
    proposed_by: str = ""  # which specialist proposed it (Phase C); "" for single-agent runs


class RejectedAlternative(BaseModel):
    action_type: str
    reason: str
    evidence: list[str] = Field(default_factory=list)


class Finding(BaseModel):
    subject: SubjectRef
    outcome: Outcome
    root_cause: str | None = None
    evidence: list[EvidenceRef] = Field(default_factory=list)
    proposed_actions: list[ProposedAction] = Field(default_factory=list)
    rejected_alternatives: list[RejectedAlternative] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    checked: list[str] = Field(default_factory=list)  # for INSUFFICIENT_EVIDENCE
    degraded_tools: list[str] = Field(default_factory=list)  # for TOOL_DEGRADED
    confidence_basis: str = ""
    trace_id: str = ""
    case_id: str = ""  # set once the loop opens a case and registers the proposed actions
    planning_turns: int = 1  # how many planner turns ran — >1 means a re-plan happened
    # Phase C: a Supervisor's per-specialist findings; [] for single-agent runs
    sub_findings: list[Finding] = Field(default_factory=list)
    # Phase E: Developer Agent incident mode — what the platform fault affected, and how to fix
    blast_radius: list[SubjectRef] = Field(default_factory=list)
    fix_strategy: str = ""  # "" | "revert" | "fix_forward"
