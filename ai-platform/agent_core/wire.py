"""The Wire Agent (Phase B — Wires, optional module).

`investigate_wire(wire_id)` runs the `wire` specialist over the shared runner: wire → hold
reason → standing instructions → reviewer queue → screening → cutoff → SOP → incidents. It
proposes a `route_to_reviewer`, an `add_standing_instruction`, a `reschedule_value_date`,
or an `open_compliance_referral` for a human. **It is the maker, never the checker — there
is no `release_wire` tool.**

Four **hard rules in code** (`_enforce_wire_controls`), applied in this order:
1. screening `HIT` → freeze: the only action is `open_compliance_referral`;
2. available balance < wire amount → no wire action, funding question in `open_questions`;
3. same-day cutoff passed → `route_to_reviewer` becomes `reschedule_value_date`;
4. beneficiary not on the client's standing instructions → `route_to_reviewer` is required.
"""

from __future__ import annotations

from datetime import datetime

from agent_core.agents import WIRE, run_specialist
from agent_core.reasoning.model_client import ModelClient
from agent_core.schemas.finding import Finding, ProposedAction, SubjectRef
from agent_core.spans import set_attrs, span
from platform_api.settings import settings


def _default_client() -> ModelClient:
    from agent_core.reasoning.model_client import AnthropicModelClient

    return AnthropicModelClient(settings.anthropic_api_key)


async def investigate_wire(
    wire_id: str,
    *,
    request: str | None = None,
    client: ModelClient | None = None,
    scenario_id: str | None = None,
) -> Finding:
    client = client or _default_client()
    ask = request or (
        f"Investigate wire {wire_id}: why is it held, and what does a human need to do — "
        f"route it to a reviewer, move its value date, or refer it to compliance?"
    )

    with span("investigate_wire", "agent", agent="wire", **{"scenario.id": scenario_id}) as root:
        finding = await run_specialist(
            WIRE,
            subject=SubjectRef(type="wire", id=wire_id),
            request=ask,
            client=client,
            scenario_id=scenario_id,
        )
        _enforce_wire_controls(finding, wire_id)
        set_attrs(root, {"outcome": finding.outcome, "case.id": finding.case_id})
    return finding


_WIRE_ACTIONS = {"route_to_reviewer", "reschedule_value_date", "add_standing_instruction"}


def _enforce_wire_controls(finding: Finding, wire_id: str) -> None:
    """Maker/checker, cutoff, and screening are decided here from the wire's facts, never
    the prompt. The model reasons *around* these; it does not get to override them."""
    from mcp_servers.wire import store

    wire = store.get_wire(wire_id)
    if not wire:
        return
    client_id = str(wire.get("client_id", ""))
    currency = str(wire.get("currency", ""))
    amount = int(wire.get("amount", 0) or 0)

    # 1. screening HIT -> freeze. The only action is a compliance referral.
    screening = store.get_wire_screening(client_id)
    if screening.get("status") == "HIT":
        referral = next(
            (a for a in finding.proposed_actions if a.action_type == "open_compliance_referral"),
            None,
        )
        if referral is None:
            referral = ProposedAction(
                action_type="open_compliance_referral",
                params={
                    "wire_id": wire_id,
                    "reason": f"screening hit ({screening.get('matched_list')})",
                },
                rationale=(
                    "sanctions screening returned a hit — all wire remediation is frozen "
                    "pending compliance"
                ),
                proposed_by="wire",
            )
        finding.proposed_actions = [referral]
        finding.open_questions.append(
            f"screening hit on {client_id} — {wire_id} frozen in code; a compliance "
            f"referral is the only action"
        )
        finding.root_cause = "SCREENING_HIT"
        return

    # 2. insufficient available balance -> no wire action, a funding question.
    balance = store.get_available_balance(str(wire.get("account_id", "")), currency)
    if balance is not None and amount and int(balance["available"]) < amount:
        finding.proposed_actions = [
            a for a in finding.proposed_actions if a.action_type not in _WIRE_ACTIONS
        ]
        finding.open_questions.append(
            f"available balance {balance['available']} {currency} is below the wire amount "
            f"{amount} — funding must be arranged before {wire_id} can be released"
        )
        if not finding.root_cause:
            finding.root_cause = "INSUFFICIENT_BALANCE"

    # 3. cutoff computation.
    cutoff = store.get_cutoff(currency)
    cutoff_passed = False
    if cutoff:
        cutoff_dt = datetime.fromisoformat(f"{store.TODAY}T{cutoff['cutoff']}")
        cutoff_passed = store.NOW > cutoff_dt
        mins_left = int((cutoff_dt - store.NOW).total_seconds() // 60)
        if not cutoff_passed and 0 <= mins_left <= 60:
            finding.open_questions.append(
                f"{currency} {cutoff['network']} cutoff {cutoff['cutoff']} is close "
                f"({mins_left} min) — a reviewer must act before then for a same-day release"
            )

    if cutoff_passed:
        for action in finding.proposed_actions:
            if action.action_type == "route_to_reviewer":
                action.action_type = "reschedule_value_date"
                action.params = {"wire_id": wire_id, "reason": "same-day cutoff missed"}
                action.rationale = (
                    f"the {currency} cutoff {cutoff['cutoff'] if cutoff else ''} has passed — "
                    f"the value date must move; this is not a same-day release"
                )
                finding.open_questions.append(
                    f"action changed to reschedule_value_date in code — {currency} cutoff passed"
                )
        if finding.root_cause in (None, "NEW_BENEFICIARY_REVIEW"):
            finding.root_cause = "CUTOFF_MISSED"
        return

    # 4. new beneficiary -> reviewer required (cutoff still open, not frozen).
    known = {s.get("beneficiary_account") for s in store.get_standing_instructions(client_id)}
    if wire.get("beneficiary_account") and wire["beneficiary_account"] not in known:
        if not any(a.action_type == "route_to_reviewer" for a in finding.proposed_actions):
            finding.proposed_actions.insert(
                0,
                ProposedAction(
                    action_type="route_to_reviewer",
                    params={
                        "wire_id": wire_id,
                        "reason": "beneficiary not on standing instructions — reviewer sign-off",
                    },
                    rationale=(
                        f"beneficiary account {wire['beneficiary_account']} is not on "
                        f"{client_id}'s standing instructions"
                    ),
                    proposed_by="wire",
                ),
            )
            finding.open_questions.append(
                f"route_to_reviewer added in code — new beneficiary on {wire_id}"
            )
        if not finding.root_cause:
            finding.root_cause = "NEW_BENEFICIARY_REVIEW"
