"""The specialist runner — one plan → tool loop → synthesize → outcome rules → policy →
Finding, parameterised by a `SpecialistSpec`. Lifted out of `agent_core/loop.py` so
every specialist (Settlement, Risk/Client, …) and the single-trade entry point share it.

Every step is a span (docs/standards/observability.md). Proposals go through the policy
engine keyed on the spec's `allowlist_key`; the write itself still waits for a human
decision.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from agent_core import policy, prompts
from agent_core.outcomes import Observation, classify
from agent_core.reasoning.model_client import ModelClient, ModelResponse, complete_structured_traced
from agent_core.reasoning.model_router import Step, model_for
from agent_core.schemas.finding import Finding, Outcome, SubjectRef
from agent_core.schemas.plan import Plan, PlanStep
from agent_core.spans import set_attrs, span
from mcp_servers import _enterprise
from mcp_servers.errors import is_error
from mcp_servers.hub import Tools, open_session, tool_access
from platform_api import cases, trace_store

_PAYLOAD_CLIP = 16_000
_TRADE_REQUIRED = frozenset({("trade", "get_trade"), ("trade", "get_settlement_status")})
_RETRIEVAL_TOOLS = {("ops", "search_knowledge"), ("ops", "find_incidents")}


@dataclass(frozen=True)
class SpecialistSpec:
    """What makes one specialist different from another."""

    name: str
    planner_prompt: str  # e.g. "planner/trade"
    synthesis_prompt: str  # e.g. "synthesis/finding"
    tool_servers: frozenset[str]  # MCP servers this agent may see
    allowlist_key: str  # key in agent_core/policy/allowlists.yaml
    subject_type: str = "trade"
    budget: int = 12
    max_planning_turns: int = 4
    required_tools: frozenset[tuple[str, str]] = _TRADE_REQUIRED
    knowledge_query_hint: str = ""  # appended to the planner system prompt


async def run_specialist(
    spec: SpecialistSpec,
    *,
    subject: SubjectRef,
    request: str,
    client: ModelClient,
    scenario_id: str | None = None,
    open_case: bool = True,
) -> Finding:
    """Run one specialist end to end. `open_case=False` when a Supervisor owns the case."""
    framing = prompts.load("system/domain_framing")

    with span(spec.name, "agent", agent=spec.name, **{"scenario.id": scenario_id}) as root:
        trace_id = format(root.get_span_context().trace_id, "032x")

        async with open_session(servers=set(spec.tool_servers)) as tools:
            catalog = await tools.list()
            observations: list[Observation] = []
            budget = spec.budget
            turns = 0

            for turn in range(spec.max_planning_turns):
                plan = await _plan(client, spec, framing, request, catalog, observations, turn)
                turns = turn + 1
                if not plan.steps:
                    break
                for step in plan.steps:
                    if budget <= 0:
                        break
                    budget -= 1
                    observations.append(Observation(step, await _run_step(spec, tools, step)))
                if budget <= 0:
                    break

            finding = await _synthesize(client, spec, framing, request, subject, observations)
            finding = classify(finding, observations, required=spec.required_tools)
            finding = policy.apply(finding, spec.allowlist_key)
            finding.trace_id = trace_id
            finding.planning_turns = turns
            for action in finding.proposed_actions:
                action.proposed_by = action.proposed_by or spec.name
            if open_case:
                _open_case(finding, subject, spec)
            set_attrs(
                root,
                {
                    "outcome": finding.outcome,
                    "tool.calls": spec.budget - budget,
                    "case.id": finding.case_id,
                },
            )

    if open_case:
        _persist_trace(finding, spec, trace_id, request, subject, scenario_id)
    return finding


# --- case + trace bookkeeping ------------------------------------------------


def _open_case(finding: Finding, subject: SubjectRef, spec: SpecialistSpec) -> None:
    if not finding.proposed_actions:
        return
    case = cases.create_case(
        subject.type or spec.subject_type,
        subject.id,
        finding.root_cause or finding.outcome.value,
        trace_id=finding.trace_id,
    )
    finding.case_id = case["case_id"]
    for action in finding.proposed_actions:
        approval = cases.propose_action(
            case["case_id"],
            action.action_type,
            action.params,
            action.rationale,
            [s.model_dump() for s in action.impact]
            or [{"type": subject.type or spec.subject_type, "id": subject.id}],
            action.reversible,
        )
        action.approval_id = approval["approval_id"]


def _persist_trace(
    finding: Finding,
    spec: SpecialistSpec,
    trace_id: str,
    request: str,
    subject: SubjectRef,
    scenario_id: str | None,
) -> None:
    trace_store.finalize_trace(
        trace_id,
        request=request,
        subject_type=finding.subject.type or subject.type or spec.subject_type,
        subject_id=finding.subject.id or subject.id,
        scenario_id=scenario_id,
        case_id=finding.case_id,
        agent=spec.name,
        outcome=finding.outcome.value,
        root_cause=finding.root_cause,
        status="COMPLETE",
        finding=finding.model_dump(mode="json"),
    )


# --- the loop steps -------------------------------------------------------


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
    spec: SpecialistSpec,
    framing: str,
    request: str,
    catalog: list[dict[str, Any]],
    observations: list[Observation],
    turn: int,
) -> Plan:
    parts = [framing, prompts.load(spec.planner_prompt), "Tools:\n" + _format_catalog(catalog)]
    if spec.knowledge_query_hint:
        parts.append(spec.knowledge_query_hint)
    system = "\n\n".join(parts)
    messages: list[dict[str, Any]] = [{"role": "user", "content": request}]
    if observations:
        messages.append(
            {"role": "user", "content": "Observations so far:\n" + _format_obs(observations)}
        )

    step_name = "replan" if turn else "plan"
    with span(step_name, "agent", agent=spec.name, step=step_name) as current:
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


async def _run_step(spec: SpecialistSpec, tools: Tools, step: PlanStep) -> Any:
    is_retrieval = (step.server, step.tool) in _RETRIEVAL_TOOLS
    name = f"{step.server}.{step.tool}"
    kind = "retrieval" if is_retrieval else "tool"
    attrs: dict[str, Any] = (
        {
            "retrieval.query": step.args.get("query", ""),
            "retrieval.k": _as_int(step.args.get("k"), 5),
        }
        if is_retrieval
        else {
            "tool.server": step.server,
            "tool.name": step.tool,
            "tool.access": tool_access(step.tool),
        }
    )
    with span(name, kind, agent=spec.name, **attrs) as current:
        result = await tools.call(step.server, step.tool, **step.args)
        set_attrs(current, {"payload.in": _clip(step.args), "payload.out": _clip(result)})
        if is_retrieval:
            set_attrs(current, {"retrieval.results": _summarise_retrieval(result)})
        else:
            set_attrs(
                current,
                {"tool.ok": not is_error(result), "tool.retries": _enterprise.last_retries()},
            )
            if is_error(result):
                set_attrs(current, {"tool.retryable": bool(result.get("retryable"))})
        if is_error(result):
            print(f"[tool-error] {name}: {result.get('code')} — {str(result.get('message'))[:200]}")
    return result


async def _synthesize(
    client: ModelClient,
    spec: SpecialistSpec,
    framing: str,
    request: str,
    subject: SubjectRef,
    observations: list[Observation],
) -> Finding:
    system = "\n\n".join([framing, prompts.load(spec.synthesis_prompt)])
    messages = [
        {"role": "user", "content": request},
        {
            "role": "user",
            "content": f"subject: {subject.type} {subject.id}\n\nObservations:\n"
            + _format_obs(observations),
        },
    ]
    with span("synthesize", "agent", agent=spec.name, step="synthesize") as current:
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
        finding.subject = SubjectRef(type=subject.type, id=subject.id)
    if finding.outcome not in set(Outcome):
        finding.outcome = Outcome.INSUFFICIENT_EVIDENCE
    return finding


# --- helpers ---------------------------------------------------------------


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _clip(obj: Any) -> Any:
    try:
        text = json.dumps(obj, default=str)
    except (TypeError, ValueError):
        return str(obj)[:_PAYLOAD_CLIP]
    if len(text) <= _PAYLOAD_CLIP:
        return json.loads(text)
    return text[:_PAYLOAD_CLIP] + "…[clipped]"


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
