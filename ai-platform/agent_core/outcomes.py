"""Outcome classification is code, not prompt (docs/standards + agent-plan.md).

Two outcomes are decided here regardless of what synthesis said:

- `TOOL_DEGRADED` — a required step (`get_trade` / `get_settlement_status`) still returned
  an `ErrorEnvelope` after the tool's own one retry. Keep whatever partial evidence there
  is; name the degraded tools.
- `INSUFFICIENT_EVIDENCE` — settlement has no `failure_code` (or `UNKNOWN`) and nothing
  else looks anomalous (no errors, no corroborating logs). Record what was checked; drop
  any guessed root cause.

Otherwise: `RESOLVED_CAUSE` if synthesis produced a root cause, else `INSUFFICIENT_EVIDENCE`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent_core.schemas.finding import Finding, Outcome
from agent_core.schemas.plan import PlanStep
from mcp_servers.errors import is_error

_REQUIRED: set[tuple[str, str]] = {("trade", "get_trade"), ("trade", "get_settlement_status")}
_NO_CODE = {None, "", "UNKNOWN"}


@dataclass
class Observation:
    step: PlanStep
    result: Any  # a success dict/list, or an ErrorEnvelope dict


def classify(finding: Finding, observations: list[Observation]) -> Finding:
    degraded = sorted(
        {
            f"{o.step.server}.{o.step.tool}"
            for o in observations
            if (o.step.server, o.step.tool) in _REQUIRED and is_error(o.result)
        }
    )
    if degraded:
        finding.outcome = Outcome.TOOL_DEGRADED
        finding.degraded_tools = degraded
        return finding

    if _no_failure_code(observations) and not _anomalous(observations):
        finding.outcome = Outcome.INSUFFICIENT_EVIDENCE
        finding.root_cause = None
        finding.checked = [
            f"{o.step.server}.{o.step.tool}" for o in observations if not is_error(o.result)
        ]
        return finding

    if finding.outcome is Outcome.OUT_OF_SCOPE:
        return finding
    finding.outcome = (
        Outcome.RESOLVED_CAUSE if finding.root_cause else Outcome.INSUFFICIENT_EVIDENCE
    )
    return finding


def _find(observations: list[Observation], server: str, tool: str) -> Any:
    for o in observations:
        if o.step.server == server and o.step.tool == tool:
            return o.result
    return None


def _no_failure_code(observations: list[Observation]) -> bool:
    settlement = _find(observations, "trade", "get_settlement_status")
    if not isinstance(settlement, dict) or is_error(settlement):
        return False
    return settlement.get("failure_code") in _NO_CODE


def _anomalous(observations: list[Observation]) -> bool:
    for o in observations:
        if (o.step.server, o.step.tool) in _REQUIRED:
            continue
        if is_error(o.result):
            return True
        if o.step.tool == "search_logs" and isinstance(o.result, list) and o.result:
            return True
    return False
