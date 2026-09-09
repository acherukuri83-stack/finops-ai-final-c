"""The StockLoan Agent (Phase F core slice).

`investigate_loan(loan_id)` runs the `stockloan` specialist over the shared runner:
loan → recall → position shortfall → lending availability → procedure. It proposes a
**recall**, a **buy-in**, or a **rerate** for a human to approve.

`recall` vs `buy-in` is a **hard rule in code** (`_enforce_recall_window`): a recall must
be initiated at least `RECALL_NOTICE_DAYS` before the shares are needed back; past that,
a buy-in is the only cover and any proposed `initiate_recall` is converted.

Margin / CorpActions / Cash domains and the mixed-client Scenario 30 are deferred
(`docs/backlog.md`).
"""

from __future__ import annotations

from datetime import date, timedelta

from agent_core.agents import STOCKLOAN, run_specialist
from agent_core.reasoning.model_client import ModelClient
from agent_core.schemas.finding import Finding, SubjectRef
from agent_core.spans import set_attrs, span
from platform_api.settings import settings


def _default_client() -> ModelClient:
    from agent_core.reasoning.model_client import AnthropicModelClient

    return AnthropicModelClient(settings.anthropic_api_key)


async def investigate_loan(
    loan_id: str,
    *,
    request: str | None = None,
    client: ModelClient | None = None,
    scenario_id: str | None = None,
) -> Finding:
    client = client or _default_client()
    ask = request or (
        f"Investigate loan {loan_id}: does the account need these shares back to settle, "
        f"and is a recall still possible or is a buy-in forced?"
    )

    with span(
        "investigate_loan", "agent", agent="stockloan", **{"scenario.id": scenario_id}
    ) as root:
        finding = await run_specialist(
            STOCKLOAN,
            subject=SubjectRef(type="loan", id=loan_id),
            request=ask,
            client=client,
            scenario_id=scenario_id,
        )
        _enforce_recall_window(finding, loan_id)
        set_attrs(root, {"outcome": finding.outcome, "case.id": finding.case_id})
    return finding


def _enforce_recall_window(finding: Finding, loan_id: str) -> None:
    """Recall vs buy-in is decided here from the loan's `return_needed_by`, not the prompt.
    Calendar days for the slice; a fuller version uses the settlement calendar."""
    from mcp_servers.stockloan import store

    loan = store.get_loan(loan_id)
    if not loan or not loan.get("return_needed_by"):
        return  # a rate-only question has no return date — nothing to enforce

    needed_by = date.fromisoformat(str(loan["return_needed_by"]))
    deadline = needed_by - timedelta(days=store.RECALL_NOTICE_DAYS)
    window_missed = store.TODAY > deadline

    for action in finding.proposed_actions:
        if window_missed and action.action_type == "initiate_recall":
            action.action_type = "book_buy_in"
            action.rationale = (
                f"recall notice window closed on {deadline.isoformat()} "
                f"(shares needed {needed_by.isoformat()}) — buy-in is the only cover"
            )
            finding.open_questions.append(
                f"action changed to book_buy_in in code — recall window for {loan_id} "
                f"closed {deadline.isoformat()}"
            )
            if finding.root_cause == "RECALL_REQUIRED":
                finding.root_cause = "RECALL_WINDOW_MISSED"
        elif not window_missed and action.action_type == "book_buy_in":
            action.action_type = "initiate_recall"
            action.rationale = (
                f"recall window still open until {deadline.isoformat()} — recall first, "
                f"buy-in only as a fallback"
            )
            finding.open_questions.append(
                f"action changed to initiate_recall in code — recall window for {loan_id} "
                f"open until {deadline.isoformat()}"
            )
            if finding.root_cause == "RECALL_WINDOW_MISSED":
                finding.root_cause = "RECALL_REQUIRED"
