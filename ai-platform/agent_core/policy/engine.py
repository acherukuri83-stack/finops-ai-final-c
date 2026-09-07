"""The policy engine. An action an agent proposes must be on that agent's allowlist
(`agent_core/policy/allowlists.yaml`); anything else is dropped from the Finding with a
POLICY span and a note. Enforced here in code — never in a prompt.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

import yaml

from agent_core.schemas.finding import Finding, ProposedAction
from agent_core.spans import span

_ALLOWLISTS = Path(__file__).parent / "allowlists.yaml"


@cache
def _allowlists() -> dict[str, set[str]]:
    raw: dict[str, list[str]] = yaml.safe_load(_ALLOWLISTS.read_text(encoding="utf-8")) or {}
    return {agent: set(actions) for agent, actions in raw.items()}


def allowed(agent: str, action_type: str) -> bool:
    return action_type in _allowlists().get(agent, set())


def apply(finding: Finding, agent: str) -> Finding:
    """Drop proposed actions the agent may not take; emit a POLICY span per action."""
    kept: list[ProposedAction] = []
    for action in finding.proposed_actions:
        ok = allowed(agent, action.action_type)
        with span("policy", "policy", agent=agent, action=action.action_type) as current:
            current.set_attribute("finops.policy.decision", "ALLOWED" if ok else "REJECTED")
            current.set_attribute("finops.policy.rule", f"{agent}.allowlist")
        if ok:
            kept.append(action)
        else:
            finding.open_questions.append(
                f"proposed action '{action.action_type}' dropped — not on the {agent} allowlist"
            )
    finding.proposed_actions = kept
    return finding
