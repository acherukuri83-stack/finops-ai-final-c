"""The single-trade entry point. Runs the **Settlement** specialist over the shared
runner (`agent_core.agents.run_specialist`). Phase C's Supervisor
(`agent_core.supervisor`) fans out across specialists for client-level questions.

An off-topic free-text request is declined by the input guardrail before any tool call.
"""

from __future__ import annotations

from agent_core.agents import SETTLEMENT, run_specialist
from agent_core.agents.base import _as_int, _clip  # re-exported: single-trade helpers moved here
from agent_core.guardrails.input_classification import classify_request
from agent_core.reasoning.model_client import ModelClient
from agent_core.schemas.finding import Finding, Outcome, SubjectRef
from agent_core.spans import set_attrs, span
from platform_api import trace_store
from platform_api.settings import settings

# the single-trade tool budget — now carried on the Settlement spec; kept here for callers
# (and tests) that read `loop._BUDGET`.
_BUDGET = SETTLEMENT.budget

__all__ = ["investigate", "_BUDGET", "_as_int", "_clip"]


def _default_client() -> ModelClient:
    from agent_core.reasoning.model_client import AnthropicModelClient

    return AnthropicModelClient(settings.anthropic_api_key)


async def investigate(
    trade_id: str,
    *,
    request: str | None = None,
    client: ModelClient | None = None,
    scenario_id: str | None = None,
) -> Finding:
    client = client or _default_client()
    ask = request or f"Investigate why trade {trade_id} failed settlement."

    with span("investigate", "agent", agent="settlement", **{"scenario.id": scenario_id}) as root:
        trace_id = format(root.get_span_context().trace_id, "032x")

        if request is not None:
            verdict = await classify_request(client, request)
            if not verdict.on_topic:
                set_attrs(root, {"outcome": "OUT_OF_SCOPE"})
                finding = Finding(
                    subject=SubjectRef(type="request", id=trade_id),
                    outcome=Outcome.OUT_OF_SCOPE,
                    confidence_basis=verdict.reason or "not an operations request",
                    trace_id=trace_id,
                )
                _persist_out_of_scope(finding, trace_id, ask, trade_id, scenario_id)
                return finding

        # nests under the `investigate` span → one trace for guardrail + specialist
        finding = await run_specialist(
            SETTLEMENT,
            subject=SubjectRef(type="trade", id=trade_id),
            request=ask,
            client=client,
            scenario_id=scenario_id,
        )
        set_attrs(root, {"outcome": finding.outcome, "case.id": finding.case_id})
    return finding


def _persist_out_of_scope(
    finding: Finding, trace_id: str, request: str, trade_id: str, scenario_id: str | None
) -> None:
    trace_store.finalize_trace(
        trace_id,
        request=request,
        subject_type="request",
        subject_id=trade_id,
        scenario_id=scenario_id,
        case_id="",
        agent="settlement",
        outcome=finding.outcome.value,
        root_cause=None,
        status="COMPLETE",
        finding=finding.model_dump(mode="json"),
    )
