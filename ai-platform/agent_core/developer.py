"""The Developer Agent — incident mode (Phase E core slice).

`investigate_incident(subject_id)` runs the `developer` specialist over the shared runner:
service health → job runs → deployments in the window → config diff → topic lag →
platform logs → source → blast radius (`find_trades` by state). It proposes a **change
ticket** (revert or fix-forward) and a **rerun** for a human to approve — it has no
deploy / merge / approve tool.

`fix_strategy` is a **hard rule in code**, not a prompt decision: a causing deployment
with a `release_note` that explains the change → `fix_forward`; otherwise → `revert`.

Verification / PR-review / eval-authoring modes and the Supervisor hand-off are deferred
(see `docs/backlog.md`).
"""

from __future__ import annotations

from agent_core.agents import DEVELOPER, run_specialist
from agent_core.reasoning.model_client import ModelClient
from agent_core.schemas.finding import Finding, SubjectRef
from agent_core.spans import set_attrs, span
from platform_api.settings import settings


def _default_client() -> ModelClient:
    from agent_core.reasoning.model_client import AnthropicModelClient

    return AnthropicModelClient(settings.anthropic_api_key)


async def investigate_incident(
    subject_id: str,
    *,
    request: str | None = None,
    client: ModelClient | None = None,
    scenario_id: str | None = None,
) -> Finding:
    client = client or _default_client()
    ask = request or (
        f"A platform fault took down {subject_id}. Find the change that caused it, its "
        f"blast radius, and whether to revert or fix forward."
    )

    with span(
        "investigate_incident", "agent", agent="developer", **{"scenario.id": scenario_id}
    ) as root:
        finding = await run_specialist(
            DEVELOPER,
            subject=SubjectRef(type="job", id=subject_id),
            request=ask,
            client=client,
            scenario_id=scenario_id,
        )
        _enforce_fix_strategy(finding)
        set_attrs(
            root,
            {
                "outcome": finding.outcome,
                "case.id": finding.case_id,
                "fix.strategy": finding.fix_strategy,
                "blast_radius": len(finding.blast_radius),
            },
        )
    return finding


def _enforce_fix_strategy(finding: Finding) -> None:
    """Code decides revert vs fix-forward from the deployment record; the prompt only
    describes the rule. A synthesis that got it wrong is corrected here, with a note."""
    from mcp_servers.platform import store

    deployments = {d["deployment_id"]: d for d in store.deployments(None)}
    targets = [
        a.params.get("target", "")
        for a in finding.proposed_actions
        if a.action_type == "open_change_ticket"
    ]
    for target in targets:
        dep = deployments.get(target)
        if not dep:
            continue
        want = "fix_forward" if dep.get("release_note") else "revert"
        if finding.fix_strategy != want:
            finding.open_questions.append(
                f"fix_strategy set to {want} in code — deployment {target} "
                f"{'has' if dep.get('release_note') else 'has no'} release note"
            )
            finding.fix_strategy = want
        for action in finding.proposed_actions:
            if action.action_type == "open_change_ticket" and action.params.get("target") == target:
                action.params["kind"] = want
    if not targets and not finding.fix_strategy:
        finding.fix_strategy = ""
