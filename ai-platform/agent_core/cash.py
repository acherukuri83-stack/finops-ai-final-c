"""The Cash Agent (Phase F).

`investigate_cash_break(break_id)` runs the `cash` specialist: break → funding ladder →
facility → FX → procedure. It proposes an `arrange_funding`, a `move_cash`, or an
`escalate_cash`.

**Fund vs escalate is a hard rule in code** (`_enforce_funding_cutoff`): a projected
shortfall with the currency's `funding_cutoff` still ahead → `arrange_funding` /
`move_cash`; once `store.NOW` is past the cutoff, those are converted to `escalate_cash`
and the root cause set to `FUNDING_CUTOFF_MISSED`.
"""

from __future__ import annotations

from datetime import datetime

from agent_core.agents import CASH, run_specialist
from agent_core.reasoning.model_client import ModelClient
from agent_core.schemas.finding import Finding, SubjectRef
from agent_core.spans import set_attrs, span
from platform_api.settings import settings


def _default_client() -> ModelClient:
    from agent_core.reasoning.model_client import AnthropicModelClient

    return AnthropicModelClient(settings.anthropic_api_key)


async def investigate_cash_break(
    break_id: str,
    *,
    request: str | None = None,
    client: ModelClient | None = None,
    scenario_id: str | None = None,
) -> Finding:
    client = client or _default_client()
    ask = request or (
        f"Investigate cash break {break_id}: the size and driver of the shortfall, and "
        f"whether it can still be funded before the cutoff."
    )

    with span(
        "investigate_cash_break", "agent", agent="cash", **{"scenario.id": scenario_id}
    ) as root:
        finding = await run_specialist(
            CASH,
            subject=SubjectRef(type="cash_break", id=break_id),
            request=ask,
            client=client,
            scenario_id=scenario_id,
        )
        _enforce_funding_cutoff(finding, break_id)
        set_attrs(root, {"outcome": finding.outcome, "case.id": finding.case_id})
    return finding


def _enforce_funding_cutoff(finding: Finding, break_id: str) -> None:
    from mcp_servers.cash import store

    brk = store.get_cash_break(break_id)
    if not brk or not brk.get("funding_cutoff"):
        return
    cutoff_passed = store.NOW > datetime.fromisoformat(str(brk["funding_cutoff"]))
    if not cutoff_passed:
        return

    for action in finding.proposed_actions:
        if action.action_type in ("arrange_funding", "move_cash"):
            action.action_type = "escalate_cash"
            action.params = {"break_id": break_id, "reason": "funding cutoff passed"}
            action.rationale = (
                f"the {brk['currency']} funding cutoff ({brk['funding_cutoff']}) has "
                f"passed — this is an overdraft / next-day matter for treasury"
            )
            finding.open_questions.append(
                f"action changed to escalate_cash in code — funding cutoff "
                f"{brk['funding_cutoff']} passed for {break_id}"
            )
    if finding.root_cause in (None, "INTRADAY_SHORTFALL"):
        finding.root_cause = "FUNDING_CUTOFF_MISSED"
