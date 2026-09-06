"""Per-step model routing. Never hard-code a model name in agent code."""

from enum import StrEnum

from platform_api.settings import settings


class Step(StrEnum):
    CLASSIFY = "classify"
    PLAN = "plan"
    SYNTHESIZE = "synthesize"
    REPLAN = "replan"


def model_for(step: Step) -> str:
    if step is Step.CLASSIFY:
        return settings.finops_cheap_model
    return settings.finops_strong_model
