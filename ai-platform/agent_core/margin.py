"""The Margin Agent (Phase F).

`investigate_margin_call(call_id)` runs the `margin` specialist over the shared runner:
call → status → collateral → eligibility → price → procedure. It proposes a
`post_collateral`, a `substitute_collateral`, or an `escalate_margin` for a human.

`meet` vs `close-out` is a **hard rule in code** (`_enforce_call_window`): a margin call
must be met by end of `due_by`; past that, `post_collateral` / `substitute_collateral` is
converted to `escalate_margin` and the root cause set to `CALL_WINDOW_MISSED`.
"""

from __future__ import annotations

from datetime import date

from agent_core.agents import MARGIN, run_specialist
from agent_core.reasoning.model_client import ModelClient
from agent_core.schemas.finding import Finding, SubjectRef
from agent_core.spans import set_attrs, span
from platform_api.settings import settings


def _default_client() -> ModelClient:
    from agent_core.reasoning.model_client import AnthropicModelClient

    return AnthropicModelClient(settings.anthropic_api_key)


async def investigate_margin_call(
    call_id: str,
    *,
    request: str | None = None,
    client: ModelClient | None = None,
    scenario_id: str | None = None,
) -> Finding:
    client = client or _default_client()
    ask = request or (
        f"Investigate margin call {call_id}: what opened the shortfall, and can it still "
        f"be met or is it a close-out?"
    )

    with span(
        "investigate_margin_call", "agent", agent="margin", **{"scenario.id": scenario_id}
    ) as root:
        finding = await run_specialist(
            MARGIN,
            subject=SubjectRef(type="margin_call", id=call_id),
            request=ask,
            client=client,
            scenario_id=scenario_id,
        )
        _enforce_call_window(finding, call_id)
        set_attrs(root, {"outcome": finding.outcome, "case.id": finding.case_id})
    return finding


def _enforce_call_window(finding: Finding, call_id: str) -> None:
    """Meet vs close-out is decided here from the call's `due_by`, not the prompt."""
    from mcp_servers.margin import store

    call = store.get_margin_call(call_id)
    if not call or not call.get("due_by"):
        return
    window_missed = store.TODAY > date.fromisoformat(str(call["due_by"]))
    if not window_missed:
        return

    for action in finding.proposed_actions:
        if action.action_type in ("post_collateral", "substitute_collateral"):
            action.action_type = "escalate_margin"
            action.params = {
                "call_id": call_id,
                "reason": "call window closed — routed to close-out",
            }
            action.rationale = (
                f"margin call {call_id} is past its {call['due_by']} window — it is a "
                f"close-out, not a top-up"
            )
            finding.open_questions.append(
                f"action changed to escalate_margin in code — call {call_id} window closed "
                f"{call['due_by']}"
            )
    if finding.root_cause in ("PRICE_MOVE_SHORTFALL", "COLLATERAL_INELIGIBLE"):
        finding.root_cause = "CALL_WINDOW_MISSED"
