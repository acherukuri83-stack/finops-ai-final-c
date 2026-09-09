"""The CorpActions Agent (Phase F).

`investigate_ca_event(event_id, account_id)` runs the `corpactions` specialist: event →
entitlement → held/lent split → loan → election → procedure. It proposes a `raise_claim`
(manufactured payment from the borrower), a `submit_election`, or an `escalate_ca`.

Two **hard rules in code** (`_enforce_record_date`):
- a cash dividend on a slice that was out on loan over the record date is **claimed from
  the borrower** — any `submit_election` on that slice is dropped and a `raise_claim` is
  ensured;
- an elective event past its `election_deadline` → `submit_election` is converted to
  `escalate_ca`.
"""

from __future__ import annotations

from datetime import date

from agent_core.agents import CORPACTIONS, run_specialist
from agent_core.reasoning.model_client import ModelClient
from agent_core.schemas.finding import Finding, ProposedAction, SubjectRef
from agent_core.spans import set_attrs, span
from platform_api.settings import settings


def _default_client() -> ModelClient:
    from agent_core.reasoning.model_client import AnthropicModelClient

    return AnthropicModelClient(settings.anthropic_api_key)


async def investigate_ca_event(
    event_id: str,
    account_id: str,
    *,
    request: str | None = None,
    client: ModelClient | None = None,
    scenario_id: str | None = None,
) -> Finding:
    client = client or _default_client()
    ask = request or (
        f"Investigate corporate action {event_id} for account {account_id}: the "
        f"entitlement, whether any of the position was lent over the record date, and "
        f"whether an election is still open."
    )

    with span(
        "investigate_ca_event", "agent", agent="corpactions", **{"scenario.id": scenario_id}
    ) as root:
        finding = await run_specialist(
            CORPACTIONS,
            subject=SubjectRef(type="ca_event", id=f"{event_id}@{account_id}"),
            request=ask,
            client=client,
            scenario_id=scenario_id,
        )
        _enforce_record_date(finding, event_id, account_id)
        set_attrs(root, {"outcome": finding.outcome, "case.id": finding.case_id})
    return finding


def _enforce_record_date(finding: Finding, event_id: str, account_id: str) -> None:
    from mcp_servers.corpactions import store

    event = store.get_ca_event(event_id)
    ent = store.get_entitlement(account_id, event_id)
    if not event:
        return

    lent = int((ent or {}).get("lent_qty", 0) or 0)
    if event.get("type") == "CASH_DIVIDEND" and lent > 0:
        # the lent slice's income is a claim on the borrower, never a direct book / election
        finding.proposed_actions = [
            a for a in finding.proposed_actions if a.action_type != "submit_election"
        ]
        if not any(a.action_type == "raise_claim" for a in finding.proposed_actions):
            finding.proposed_actions.append(
                ProposedAction(
                    action_type="raise_claim",
                    params={"event_id": event_id, "account_id": account_id, "qty": str(lent)},
                    rationale=(
                        f"{lent} shares were out on loan over the "
                        f"{event['record_date']} record date — the dividend is a "
                        f"manufactured-payment claim on the borrower"
                    ),
                    proposed_by="corpactions",
                )
            )
            finding.open_questions.append(
                f"raise_claim added in code — {lent} shares lent over the record "
                f"date for {event_id}"
            )
        if not finding.root_cause:
            finding.root_cause = "MANUFACTURED_PAYMENT_DUE"

    deadline = event.get("election_deadline")
    if event.get("elective") and deadline and store.TODAY > date.fromisoformat(str(deadline)):
        for a in finding.proposed_actions:
            if a.action_type == "submit_election":
                a.action_type = "escalate_ca"
                a.params = {"event_id": event_id, "reason": "election deadline passed"}
                a.rationale = f"election deadline {deadline} has passed — routed to asset servicing"
                finding.open_questions.append(
                    f"action changed to escalate_ca in code — election deadline {deadline} passed"
                )
        if finding.root_cause in (None, "ELECTION_DUE"):
            finding.root_cause = "ELECTION_DEADLINE_MISSED"
