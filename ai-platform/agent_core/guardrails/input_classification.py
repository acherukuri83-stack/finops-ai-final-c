"""Input-classification guardrail. One cheap-model call before any tool runs: is this an
operations request at all? Off-topic input is declined with no tool calls.
"""

from __future__ import annotations

from pydantic import BaseModel

from agent_core import prompts
from agent_core.reasoning.model_client import ModelClient, complete_structured_traced
from agent_core.reasoning.model_router import Step, model_for
from agent_core.spans import set_attrs, span


class SubjectClass(BaseModel):
    on_topic: bool
    reason: str = ""


async def classify_request(client: ModelClient, request: str) -> SubjectClass:
    system = "\n\n".join([prompts.load("system/domain_framing"), prompts.load("classify/subject")])
    with span("guardrail", "guardrail", **{"guardrail.name": "input_classification"}) as current:
        result, resp = await complete_structured_traced(
            client,
            model=model_for(Step.CLASSIFY),
            system=system,
            messages=[{"role": "user", "content": request}],
            schema=SubjectClass,
            max_tokens=256,
        )
        set_attrs(
            current,
            {
                "guardrail.result": "on_topic" if result.on_topic else "off_topic",
                "model": resp.model,
                "tokens.in": resp.input_tokens,
                "tokens.out": resp.output_tokens,
            },
        )
    return result
