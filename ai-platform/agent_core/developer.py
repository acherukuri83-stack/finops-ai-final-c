"""The Developer Agent (Phase E).

**incident mode** — `investigate_incident(subject_id)` runs the `developer` specialist
over the shared runner: service health → job runs → deployments → config diff → topic
lag → platform logs → source → blast radius. It proposes a **change ticket** (revert or
fix-forward) and a **rerun** for a human — no deploy / merge / approve tool. `fix_strategy`
is a hard rule in code keyed on the deployment's `release_note`.

**verification mode** — `verify_change(ticket_id)` takes an *applied* change ticket,
re-checks the signals the diagnosis used (the failed job, topic lag), computes the
delta, hands any residual trades to the Settlement specialist, and writes an incident
back on a clean fix. On failure it reports and says to re-enter incident mode with the
failed hypothesis excluded — **it never proposes or executes a second fix**.

PR-review / eval-authoring modes and the Supervisor→Developer hand-off are deferred
(see `docs/backlog.md`).
"""

from __future__ import annotations

from agent_core.agents import DEVELOPER, SETTLEMENT, run_specialist
from agent_core.reasoning.model_client import ModelClient
from agent_core.schemas.finding import EvidenceRef, Finding, Outcome, SubjectRef
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


# --- verification mode ----------------------------------------------------------


async def verify_change(
    ticket_id: str,
    *,
    job_name: str = "settlement-batch",
    topic: str = "settlement.events",
    root_cause: str = "CONFIG_REGRESSION",
    client: ModelClient | None = None,
    scenario_id: str | None = None,
) -> Finding:
    """Verify an applied change ticket. Deterministic re-check, no LLM call for the core;
    a residual hand-off to the Settlement specialist uses `client` when one is given."""
    from mcp_servers.platform import store

    with span(
        "verify_change", "agent", agent="developer", step="verify", **{"scenario.id": scenario_id}
    ) as root:
        applied = store.apply_change_ticket(ticket_id)
        finding = Finding(
            subject=SubjectRef(type="change", id=ticket_id),
            outcome=Outcome.INSUFFICIENT_EVIDENCE,
            evidence=[
                EvidenceRef(kind="tool", ref="get_job_runs", cited=True),
                EvidenceRef(kind="tool", ref="get_topic_lag", cited=True),
            ],
        )
        if applied is None:
            finding.confidence_basis = f"no change ticket {ticket_id}"
            set_attrs(root, {"outcome": finding.outcome})
            return finding

        runs = store.job_runs(job_name)
        job_ok = bool(runs) and runs[0]["result"] == "SUCCEEDED"
        lag = (store.topic_lag(topic) or {}).get("lag", -1)
        lag_ok = lag == 0
        residual = store.residual_trades()

        finding.checked = [
            f"latest {job_name} run: {runs[0]['result'] if runs else 'none'}",
            f"{topic} lag: {lag}",
            f"residual trades: {residual or 'none'}",
        ]

        if not (job_ok and lag_ok):
            # the fix did not work — report, do NOT propose or execute a second fix.
            finding.outcome = Outcome.INSUFFICIENT_EVIDENCE
            finding.open_questions = [
                f"verification FAILED: job_ok={job_ok}, lag={lag}",
                f"re-enter incident mode excluding the failed hypothesis "
                f"({applied['kind']} {applied['target']}) — no autonomous second fix",
            ]
            finding.confidence_basis = "the applied change did not clear the signals"
            set_attrs(root, {"outcome": finding.outcome, "verify.ok": False})
            return finding

        finding.outcome = Outcome.RESOLVED_CAUSE
        finding.root_cause = root_cause
        if residual:
            finding.open_questions = [
                f"residual: {t} still failing after the fix — handed to the Settlement specialist"
                for t in residual
            ]
            if client is not None:
                ask = f"Trade is still failing after platform change {ticket_id} was applied."
                finding.sub_findings = [
                    await run_specialist(
                        SETTLEMENT,
                        subject=SubjectRef(type="trade", id=t),
                        request=ask,
                        client=client,
                        scenario_id=scenario_id,
                        open_case=False,
                    )
                    for t in residual
                ]
            finding.confidence_basis = (
                f"signals cleared ({len(residual)} residual trade(s) handed off)"
            )
        else:
            inc = store.create_incident(
                symptom=f"{job_name} FAILED with a 47-record backlog",
                cause=root_cause,
                fix=f"{applied['kind']} {applied['target']} (ticket {ticket_id})",
                verification=f"{job_name} SUCCEEDED, {topic} lag 0, blast radius cleared",
            )
            finding.evidence.append(
                EvidenceRef(kind="incident", ref=inc["incident_id"], cited=True)
            )
            finding.confidence_basis = (
                f"job SUCCEEDED, lag 0, no residual; incident {inc['incident_id']} written"
            )
        set_attrs(root, {"outcome": finding.outcome, "verify.ok": True, "residual": len(residual)})
    return finding
