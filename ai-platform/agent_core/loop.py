"""The Investigator orchestrator: plan -> tool loop (budget 12, re-plan) -> synthesize
-> outcome rules -> Finding. Every step is a span (docs/standards/observability.md).

W2: trade mode only, no approvals. Replaces agent_core/skeleton.py.
"""

from __future__ import annotations

import json
from typing import Any

from agent_core import prompts
from agent_core.outcomes import Observation, classify
from agent_core.reasoning.model_client import ModelClient, ModelResponse, complete_structured_traced
from agent_core.reasoning.model_router import Step, model_for
from agent_core.schemas.finding import Finding, Outcome, SubjectRef
from agent_core.schemas.plan import Plan, PlanStep
from agent_core.spans import set_attrs, span
from mcp_servers.errors import is_error
from mcp_servers.hub import Tools, open_session
from platform_api.settings import settings

_BUDGET = 12
_MAX_PLANNING_TURNS = 4
_RETRIEVAL_TOOLS = {("ops", "search_knowledge"), ("ops", "find_incidents")}


def _default_client() -> ModelClient:
    from agent_core.reasoning.model_client import AnthropicModelClient

    return AnthropicModelClient(settings.anthropic_api_key)


async def investigate(
    trade_id: str, *, client: ModelClient | None = None, scenario_id: str | None = None
) -> Finding:
    client = client or _default_client()
    request = f"Investigate why trade {trade_id} failed settlement."
    framing = prompts.load("system/domain_framing")

    with span("investigate", "agent", agent="investigator", **{"scenario.id": scenario_id}) as root:
        trace_id = format(root.get_span_context().trace_id, "032x")
        async with open_session() as tools:
            catalog = await tools.list()
            observations: list[Observation] = []
            budget = _BUDGET

            for turn in range(_MAX_PLANNING_TURNS):
                plan = await _plan(client, framing, request, catalog, observations, turn)
                if not plan.steps:
                    break
                for step in plan.steps:
                    if budget <= 0:
                        break
                    budget -= 1
                    observations.append(Observation(step, await _run_step(tools, step)))
                if budget <= 0:
                    break

            finding = await _synthesize(client, framing, request, trade_id, observations)
            finding = classify(finding, observations)
            finding.trace_id = trace_id
            set_attrs(root, {"outcome": finding.outcome, "tool.calls": _BUDGET - budget})
            return finding


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
    return plan


async def _run_step(tools: Tools, step: PlanStep) -> Any:
    is_retrieval = (step.server, step.tool) in _RETRIEVAL_TOOLS
    name = f"{step.server}.{step.tool}"
    kind = "retrieval" if is_retrieval else "tool"
    attrs: dict[str, Any] = (
        {"retrieval.query": step.args.get("query", "")}
        if is_retrieval
        else {"tool.server": step.server, "tool.name": step.tool, "tool.access": "read"}
    )
    with span(name, kind, **attrs) as current:
        result = await tools.call(step.server, step.tool, **step.args)
        if is_retrieval:
            set_attrs(current, {"retrieval.results": _summarise_retrieval(result)})
        else:
            set_attrs(current, {"tool.ok": not is_error(result)})
            if is_error(result):
                set_attrs(current, {"tool.retryable": bool(result.get("retryable"))})
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
