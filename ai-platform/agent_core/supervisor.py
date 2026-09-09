"""The Supervisor: the client-level entry point (Phase C).

`investigate_client(client_id)` classifies the ask, pulls the client's FAILED trades,
**decomposes** the work into specialist sub-tasks, **dispatches** them in parallel (each
under a `delegation` span), **correlates** the sub-findings by shared cause into grouped
actions, **synthesizes** one client-level `Finding`, and opens **one** case.

The Supervisor investigates nothing itself and proposes nothing in a domain — its
allowlist is `create_case` / `update_case`. Each grouped action carries the *proposing
specialist's* name and is re-checked against that specialist's allowlist here.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from agent_core import policy, prompts
from agent_core.agents import run_specialist, spec_for
from agent_core.agents.base import _clip, _record_usage
from agent_core.guardrails.input_classification import classify_request
from agent_core.reasoning.model_client import ModelClient, complete_structured_traced
from agent_core.reasoning.model_router import Step, model_for
from agent_core.schemas.finding import Finding, Outcome, ProposedAction, SubjectRef
from agent_core.schemas.subtask import DecomposePlan, SubTask
from agent_core.spans import set_attrs, span
from mcp_servers.hub import open_session
from platform_api import cases, trace_store
from platform_api.settings import settings

_WEAKEST = {Outcome.TOOL_DEGRADED: 0, Outcome.INSUFFICIENT_EVIDENCE: 1, Outcome.OUT_OF_SCOPE: 1}


def _default_client() -> ModelClient:
    from agent_core.reasoning.model_client import AnthropicModelClient

    return AnthropicModelClient(settings.anthropic_api_key)


async def investigate_client(
    client_id: str,
    *,
    request: str | None = None,
    client: ModelClient | None = None,
    scenario_id: str | None = None,
) -> Finding:
    client = client or _default_client()
    ask = request or f"Investigate every settlement problem affecting client {client_id} today."

    with span(
        "investigate_client", "agent", agent="supervisor", **{"scenario.id": scenario_id}
    ) as root:
        trace_id = format(root.get_span_context().trace_id, "032x")

        if request is not None:
            verdict = await classify_request(client, request)
            if not verdict.on_topic:
                set_attrs(root, {"outcome": "OUT_OF_SCOPE"})
                finding = Finding(
                    subject=SubjectRef(type="request", id=client_id),
                    outcome=Outcome.OUT_OF_SCOPE,
                    confidence_basis=verdict.reason or "not an operations request",
                    trace_id=trace_id,
                )
                _persist_trace(finding, trace_id, ask, client_id, scenario_id, case_id="")
                return finding

        failed = await _failed_trades(client_id)
        subtasks = await _decompose(client, ask, client_id, failed)
        if not subtasks:
            finding = Finding(
                subject=SubjectRef(type="client", id=client_id),
                outcome=Outcome.INSUFFICIENT_EVIDENCE,
                confidence_basis=f"no FAILED trades found for {client_id}",
                trace_id=trace_id,
            )
            set_attrs(root, {"outcome": finding.outcome})
            _persist_trace(finding, trace_id, ask, client_id, scenario_id, case_id="")
            return finding

        sub_findings = await _dispatch(client, subtasks, scenario_id)
        finding = await _synthesize(client, ask, client_id, subtasks, sub_findings)
        finding.trace_id = trace_id
        finding.sub_findings = sub_findings
        _reconcile_outcome(finding, sub_findings)
        _carry_open_questions(finding, sub_findings)
        _recommend_incident_review(finding, sub_findings)
        _enforce_known_actions(finding, sub_findings)
        _repolicy_grouped_actions(finding, sub_findings)
        case_id = _open_case(finding, client_id)
        set_attrs(
            root,
            {
                "outcome": finding.outcome,
                "case.id": finding.case_id,
                "subtasks": len(subtasks),
                "sub_findings": len(sub_findings),
            },
        )

    _persist_trace(finding, trace_id, ask, client_id, scenario_id, case_id=case_id)
    return finding


# --- steps ---------------------------------------------------------------------


async def _failed_trades(client_id: str) -> list[dict[str, Any]]:
    """The client's currently FAILED trades — the decomposition input."""
    with span(
        "trade.find_trades",
        "tool",
        agent="supervisor",
        **{
            "tool.server": "trade",
            "tool.name": "find_trades",
            "tool.access": "read",
        },
    ) as current:
        async with open_session(servers={"trade"}) as tools:
            rows = await tools.call("trade", "find_trades", client_id=client_id, status="FAILED")
        ok = isinstance(rows, list)
        set_attrs(current, {"tool.ok": ok, "payload.out": _clip(rows)})
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


async def _decompose(
    client: ModelClient, request: str, client_id: str, failed: list[dict[str, Any]]
) -> list[SubTask]:
    system = "\n\n".join(
        [prompts.load("system/domain_framing"), prompts.load("supervisor/decompose")]
    )
    catalog = _format_failed(client_id, failed)
    with span("decompose", "agent", agent="supervisor", step="decompose") as current:
        plan, resp = await complete_structured_traced(
            client,
            model=model_for(Step.SYNTHESIZE),
            system=system,
            messages=[{"role": "user", "content": f"{request}\n\n{catalog}"}],
            schema=DecomposePlan,
            max_tokens=2048,
        )
        _record_usage(current, resp)
        set_attrs(current, {"payload.out": _clip([s.model_dump() for s in plan.subtasks])})
    # keep only sub-tasks we can actually route
    routable = {"settlement", "risk_client", "stockloan", "margin", "corpactions", "cash"}
    return [s for s in plan.subtasks if s.subject_ids and s.agent in routable]


async def _dispatch(
    client: ModelClient, subtasks: list[SubTask], scenario_id: str | None
) -> list[Finding]:
    async def one(st: SubTask) -> Finding:
        spec = spec_for(st.agent)
        subj_type = {
            "risk_client": "account",
            "stockloan": "loan",
            "margin": "margin_call",
            "corpactions": "ca_event",
            "cash": "cash_break",
        }.get(st.agent, "trade")
        subject = SubjectRef(type=subj_type, id=st.subject_ids[0])
        scoped = st.question
        if len(st.subject_ids) > 1:
            scoped += f"\n\n{subj_type.capitalize()}s in scope: {', '.join(st.subject_ids)}."
        with span(
            f"delegate:{st.agent}",
            "delegation",
            agent="supervisor",
            **{
                "subtask.agent": st.agent,
                "subtask.subjects": st.subject_ids,
                "subtask.budget": st.budget,
            },
        ):
            return await run_specialist(
                spec,
                subject=subject,
                request=scoped,
                client=client,
                scenario_id=scenario_id,
                open_case=False,
            )

    return list(await asyncio.gather(*(one(st) for st in subtasks)))


async def _synthesize(
    client: ModelClient,
    request: str,
    client_id: str,
    subtasks: list[SubTask],
    sub_findings: list[Finding],
) -> Finding:
    system = "\n\n".join(
        [prompts.load("system/domain_framing"), prompts.load("synthesis/supervisor")]
    )
    messages = [
        {"role": "user", "content": request},
        {
            "role": "user",
            "content": f"client_id: {client_id}\n\nSub-tasks dispatched:\n"
            + json.dumps([s.model_dump() for s in subtasks], indent=2)
            + "\n\nSub-findings:\n"
            + json.dumps([_sub_view(f) for f in sub_findings], indent=2),
        },
    ]
    with span("synthesize", "agent", agent="supervisor", step="synthesize") as current:
        finding, resp = await complete_structured_traced(
            client,
            model=model_for(Step.SYNTHESIZE),
            system=system,
            messages=messages,
            schema=Finding,
            max_tokens=8192,
        )
        _record_usage(current, resp)
        set_attrs(current, {"payload.out": _clip(finding.model_dump(mode="json"))})
    if not finding.subject.id or finding.subject.type != "client":
        finding.subject = SubjectRef(type="client", id=client_id)
    if finding.outcome not in set(Outcome):
        finding.outcome = Outcome.INSUFFICIENT_EVIDENCE
    finding.sub_findings = []  # attached by the caller from the real objects
    return finding


# --- correlation / guards (code, not prompt) ----------------------------------


def _reconcile_outcome(finding: Finding, sub_findings: list[Finding]) -> None:
    """RESOLVED only if a sub-finding resolved; otherwise the weakest sub-outcome."""
    outs = [f.outcome for f in sub_findings]
    if Outcome.RESOLVED_CAUSE in outs:
        if finding.outcome not in (Outcome.RESOLVED_CAUSE, Outcome.TOOL_DEGRADED):
            finding.outcome = Outcome.RESOLVED_CAUSE
        return
    worst = min(outs, key=lambda o: _WEAKEST.get(o, 2)) if outs else Outcome.INSUFFICIENT_EVIDENCE
    finding.outcome = worst


def _carry_open_questions(finding: Finding, sub_findings: list[Finding]) -> None:
    """Every gap a sub-finding recorded is surfaced verbatim — never smoothed."""
    have = set(finding.open_questions)
    for f in sub_findings:
        label = f"{f.subject.type} {f.subject.id}"
        if f.outcome in (Outcome.INSUFFICIENT_EVIDENCE, Outcome.TOOL_DEGRADED):
            note = f"[{label}] {f.outcome.value}: {f.confidence_basis or 'see sub-finding'}"
            if note not in have:
                finding.open_questions.append(note)
                have.add(note)
        for q in f.open_questions:
            tagged = f"[{label}] {q}"
            if tagged not in have:
                finding.open_questions.append(tagged)
                have.add(tagged)


def _recommend_incident_review(finding: Finding, sub_findings: list[Finding]) -> None:
    """Bounded Supervisor -> Developer Agent hand-off.

    When *every* dispatched specialist came back with `INSUFFICIENT_EVIDENCE`, the client's
    trades share no domain cause the specialists can see — a platform fault (a bad job run,
    a degraded enterprise API) is a live hypothesis. Surface that as a recommendation only:
    the Supervisor does not auto-dispatch the Developer Agent, because "what platform
    subject" (which job / which service) is an unresolved product question. A human runs
    `POST /diagnose` with the subject they suspect.
    """
    if not sub_findings:
        return
    if not all(f.outcome is Outcome.INSUFFICIENT_EVIDENCE for f in sub_findings):
        return
    note = (
        "every specialist returned INSUFFICIENT_EVIDENCE — no shared domain cause found; "
        "consider a platform incident review (POST /diagnose with the suspected job / "
        "service). Not auto-dispatched: the platform subject is not known here."
    )
    if note not in set(finding.open_questions):
        finding.open_questions.append(note)


def _enforce_known_actions(finding: Finding, sub_findings: list[Finding]) -> None:
    """Every action any sub-finding proposed must appear in the client Finding or be
    explained in `open_questions`. A synthesis that silently drops one is corrected here."""
    proposed = {a.action_type for a in finding.proposed_actions}
    blob = " ".join(finding.open_questions).lower()
    for f in sub_findings:
        for a in f.proposed_actions:
            if a.action_type in proposed or a.action_type.lower() in blob:
                continue
            finding.open_questions.append(
                f"[{f.subject.type} {f.subject.id}] specialist proposed "
                f"'{a.action_type}' — not carried into the client actions"
            )


def _repolicy_grouped_actions(finding: Finding, sub_findings: list[Finding]) -> None:
    """Re-check each grouped action against the *proposing* specialist's allowlist."""
    owner: dict[str, str] = {}
    for f in sub_findings:
        for a in f.proposed_actions:
            owner.setdefault(a.action_type, a.proposed_by or "")
    kept: list[ProposedAction] = []
    for a in finding.proposed_actions:
        agent = a.proposed_by or owner.get(a.action_type, "supervisor")
        a.proposed_by = agent
        ok = policy.allowed(agent, a.action_type)
        with span("policy", "policy", agent=agent, action=a.action_type) as current:
            current.set_attribute("finops.policy.decision", "ALLOWED" if ok else "REJECTED")
            current.set_attribute("finops.policy.rule", f"{agent}.allowlist")
        if ok:
            kept.append(a)
        else:
            finding.open_questions.append(
                f"grouped action '{a.action_type}' dropped — not on the {agent} allowlist"
            )
    finding.proposed_actions = kept


def _open_case(finding: Finding, client_id: str) -> str:
    if not finding.proposed_actions:
        return ""
    case = cases.create_case(
        "client",
        client_id,
        finding.confidence_basis or "client investigation",
        trace_id=finding.trace_id,
    )
    finding.case_id = case["case_id"]
    for action in finding.proposed_actions:
        impact = [s.model_dump() for s in action.impact] or [{"type": "client", "id": client_id}]
        approval = cases.propose_action(
            case["case_id"],
            action.action_type,
            action.params,
            action.rationale,
            impact,
            action.reversible,
        )
        action.approval_id = approval["approval_id"]
    return str(case["case_id"])


def _persist_trace(
    finding: Finding,
    trace_id: str,
    request: str,
    client_id: str,
    scenario_id: str | None,
    *,
    case_id: str,
) -> None:
    trace_store.finalize_trace(
        trace_id,
        request=request,
        subject_type=finding.subject.type or "client",
        subject_id=finding.subject.id or client_id,
        scenario_id=scenario_id,
        case_id=case_id or finding.case_id,
        agent="supervisor",
        outcome=finding.outcome.value,
        root_cause=finding.root_cause,
        status="COMPLETE",
        finding=finding.model_dump(mode="json"),
    )


# --- formatting --------------------------------------------------------------


def _format_failed(client_id: str, failed: list[dict[str, Any]]) -> str:
    if not failed:
        return f"client {client_id} has no FAILED trades."
    lines = [f"FAILED trades for {client_id}:"]
    for t in failed:
        lines.append(
            f"- {t.get('trade_id')}: {t.get('side')} {t.get('qty')} {t.get('security_id')} "
            f"failure_code={t.get('failure_code')} cpty={t.get('cpty_id')} "
            f"account={t.get('account_id')} settle={t.get('settle_date')}"
        )
    return "\n".join(lines)


def _sub_view(f: Finding) -> dict[str, Any]:
    return {
        "subject": f.subject.model_dump(),
        "outcome": f.outcome.value,
        "root_cause": f.root_cause,
        "proposed_actions": [
            {
                "action_type": a.action_type,
                "rationale": a.rationale,
                "proposed_by": a.proposed_by,
                "impact": [s.model_dump() for s in a.impact],
            }
            for a in f.proposed_actions
        ],
        "rejected_alternatives": [r.model_dump() for r in f.rejected_alternatives],
        "evidence": [e.model_dump() for e in f.evidence if e.cited],
        "open_questions": f.open_questions,
        "confidence_basis": f.confidence_basis,
    }
