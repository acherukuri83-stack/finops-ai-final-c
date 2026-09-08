"""The Investigator orchestrator: guardrail -> plan -> tool loop (budget 12, re-plan) ->
synthesize -> outcome rules -> policy -> open a case + register the proposed actions ->
Finding. Every step is a span (docs/standards/observability.md).

W3: trade mode; proposals go through the policy engine and the case/approval gate. The
write itself waits for a human decision (portal / `POST /approvals/{id}/decide`).
"""

from __future__ import annotations

import json
from typing import Any

from agent_core import policy, prompts
from agent_core.guardrails.input_classification import classify_request
from agent_core.outcomes import Observation, classify
from agent_core.reasoning.model_client import ModelClient, ModelResponse, complete_structured_traced
from agent_core.reasoning.model_router import Step, model_for
from agent_core.schemas.finding import Finding, Outcome, SubjectRef
from agent_core.schemas.plan import Plan, PlanStep
from agent_core.spans import set_attrs, span
from mcp_servers.errors import is_error
from mcp_servers.hub import Tools, open_session, tool_access
from platform_api import cases, trace_store
from platform_api.settings import settings

_PAYLOAD_CLIP = 16_000

_BUDGET = 12
_MAX_PLANNING_TURNS = 4
_RETRIEVAL_TOOLS = {("ops", "search_knowledge"), ("ops", "find_incidents")}
_AGENT = "investigator"


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
    framing = prompts.load("system/domain_framing")

    with span("investigate", "agent", agent=_AGENT, **{"scenario.id": scenario_id}) as root:
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
                _persist_trace(finding, trace_id, ask, trade_id, scenario_id)
                return finding

        async with open_session() as tools:
            catalog = await tools.list()
            observations: list[Observation] = []
            budget = _BUDGET
            turns = 0

            for turn in range(_MAX_PLANNING_TURNS):
                plan = await _plan(client, framing, ask, catalog, observations, turn)
                turns = turn + 1
                if not plan.steps:
                    break
                for step in plan.steps:
                    if budget <= 0:
                        break
                    budget -= 1
                    observations.append(Observation(step, await _run_step(tools, step)))
                if budget <= 0:
                    break

            finding = await _synthesize(client, framing, ask, trade_id, observations)
            finding = classify(finding, observations)
            finding = policy.apply(finding, _AGENT)
            finding.trace_id = trace_id
            finding.planning_turns = turns
            _open_case(finding, trade_id)
            set_attrs(
                root,
                {
                    "outcome": finding.outcome,
                    "tool.calls": _BUDGET - budget,
                    "case.id": finding.case_id,
                },
            )
    _persist_trace(finding, trace_id, ask, trade_id, scenario_id)
    return finding


def _persist_trace(
    finding: Finding, trace_id: str, request: str, trade_id: str, scenario_id: str | None
) -> None:
    """Stamp the trace-level row once the investigation is done (best-effort; a no-op
    when TRACES_ENABLED is false)."""
    trace_store.finalize_trace(
        trace_id,
        request=request,
        subject_type=finding.subject.type or "trade",
        subject_id=finding.subject.id or trade_id,
        scenario_id=scenario_id,
        case_id=finding.case_id,
        agent=_AGENT,
        outcome=finding.outcome.value,
        root_cause=finding.root_cause,
        status="COMPLETE",
        finding=finding.model_dump(mode="json"),
    )


def _clip(obj: Any) -> Any:
    """A payload small enough to store on a span. Big results are truncated to a string."""
    try:
        text = json.dumps(obj, default=str)
    except (TypeError, ValueError):
        text = str(obj)
    return obj if len(text) <= _PAYLOAD_CLIP else text[:_PAYLOAD_CLIP] + "…[clipped]"


def _open_case(finding: Finding, trade_id: str) -> None:
    """Open a case and register each surviving proposed action for approval."""
    if not finding.proposed_actions:
        return
    case = cases.create_case(
        "trade", trade_id, finding.root_cause or finding.outcome.value, trace_id=finding.trace_id
    )
    finding.case_id = case["case_id"]
    for action in finding.proposed_actions:
        approval = cases.propose_action(
            case["case_id"],
            action.action_type,
            action.params,
            action.rationale,
            [s.model_dump() for s in action.impact] or [{"type": "trade", "id": trade_id}],
            action.reversible,
        )
        action.approval_id = approval["approval_id"]


def _record_usage(current: Any, resp: ModelResponse) -> None:
    set_attrs(
        current,
        {
            "model": resp.model,
            "tokens.in": resp.input_tokens,
            "tokens.out": resp.output_tokens,
            "cache.read": resp.cache_read_tokens,
        },
    )


async def _plan(
    client: ModelClient,
    framing: str,
    request: str,
    catalog: list[dict[str, Any]],
    observations: list[Observation],
    turn: int,
) -> Plan:
    system = "\n\n".join(
        [framing, prompts.load("planner/trade"), "Tools:\n" + _format_catalog(catalog)]
    )
    messages: list[dict[str, Any]] = [{"role": "user", "content": request}]
    if observations:
        messages.append(
            {"role": "user", "content": "Observations so far:\n" + _format_obs(observations)}
        )

    step_name = "replan" if turn else "plan"
    with span(step_name, "agent", agent="investigator", step=step_name) as current:
        plan, resp = await complete_structured_traced(
            client,
            model=model_for(Step.PLAN),
            system=system,
            messages=messages,
            schema=Plan,
            max_tokens=4096,
        )
        _record_usage(current, resp)
        set_attrs(current, {"payload.out": _clip([s.model_dump() for s in plan.steps])})
    return plan


async def _run_step(tools: Tools, step: PlanStep) -> Any:
    is_retrieval = (step.server, step.tool) in _RETRIEVAL_TOOLS
    name = f"{step.server}.{step.tool}"
    kind = "retrieval" if is_retrieval else "tool"
    attrs: dict[str, Any] = (
        {"retrieval.query": step.args.get("query", ""), "retrieval.k": int(step.args.get("k", 5))}
        if is_retrieval
        else {
            "tool.server": step.server,
            "tool.name": step.tool,
            "tool.access": tool_access(step.tool),
        }
    )
    with span(name, kind, **attrs) as current:
        result = await tools.call(step.server, step.tool, **step.args)
        set_attrs(current, {"payload.in": _clip(step.args), "payload.out": _clip(result)})
        if is_retrieval:
            set_attrs(current, {"retrieval.results": _summarise_retrieval(result)})
        else:
            set_attrs(current, {"tool.ok": not is_error(result)})
            if is_error(result):
                set_attrs(current, {"tool.retryable": bool(result.get("retryable"))})
        if is_error(result):
            print(f"[tool-error] {name}: {result.get('code')} — {str(result.get('message'))[:200]}")
    return result


async def _synthesize(
    client: ModelClient,
    framing: str,
    request: str,
    trade_id: str,
    observations: list[Observation],
) -> Finding:
    system = "\n\n".join([framing, prompts.load("synthesis/finding")])
    messages = [
        {"role": "user", "content": request},
        {
            "role": "user",
            "content": f"trade_id: {trade_id}\n\nObservations:\n" + _format_obs(observations),
        },
    ]
    with span("synthesize", "agent", agent="investigator", step="synthesize") as current:
        finding, resp = await complete_structured_traced(
            client,
            model=model_for(Step.SYNTHESIZE),
            system=system,
            messages=messages,
            schema=Finding,
            max_tokens=8192,
        )
        _record_usage(current, resp)
        set_attrs(
            current,
            {
                "payload.out": _clip(
                    {
                        "root_cause": finding.root_cause,
                        "outcome": finding.outcome.value,
                        "evidence": [e.model_dump() for e in finding.evidence],
                        "proposed_actions": [a.model_dump() for a in finding.proposed_actions],
                        "rejected_alternatives": [
                            r.model_dump() for r in finding.rejected_alternatives
                        ],
                    }
                )
            },
        )
    if not finding.subject.id:
        finding.subject = SubjectRef(type="trade", id=trade_id)
    if finding.outcome not in set(Outcome):
        finding.outcome = Outcome.INSUFFICIENT_EVIDENCE
    return finding


def _format_catalog(catalog: list[dict[str, Any]]) -> str:
    return "\n".join(
        f"- {row['server']}.{row['tool']}({', '.join(row.get('params', []))}): {row['description']}"
        for row in catalog
    )


def _format_obs(observations: list[Observation]) -> str:
    lines: list[str] = []
    for o in observations:
        args = " ".join(f"{k}={v}" for k, v in o.step.args.items())
        lines.append(f"[{o.step.server}.{o.step.tool} {args}] -> {json.dumps(o.result)[:1200]}")
    return "\n".join(lines)


def _summarise_retrieval(result: Any) -> Any:
    if not isinstance(result, list):
        return result
    keys = ("doc", "section", "incident_id", "score", "similarity")
    return [{k: row.get(k) for k in keys} for row in result if isinstance(row, dict)]
