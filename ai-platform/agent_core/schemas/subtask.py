"""The Supervisor's decomposition output (Phase C). One `SubTask` per specialist
dispatch; `DecomposePlan` is the structured-output wrapper the planner returns.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SubTask(BaseModel):
    agent: str  # "settlement" | "risk_client" | "knowledge"
    subject_ids: list[str] = Field(
        default_factory=list
    )  # trade ids, or account ids for risk_client
    question: str  # the specific question this specialist should answer
    budget: int = 8  # tool-call budget for this dispatch


class DecomposePlan(BaseModel):
    subtasks: list[SubTask] = Field(default_factory=list)
