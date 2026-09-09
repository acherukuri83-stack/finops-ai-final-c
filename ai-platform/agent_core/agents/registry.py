"""The specialist registry. Each spec pins a tool scope, a policy allowlist key, and the
prompts the shared runner (`base.run_specialist`) uses.

Phase C ships three: **Settlement** (the former single Investigator, tool-scoped and
without the SSI write), **Risk/Client** (SSI current-vs-history, restrictions, screening;
owns `update_ssi`), and **Knowledge** (retrieval-only, no allowlist). The Wire specialist
arrives with the optional Wires module.
"""

from __future__ import annotations

from agent_core.agents.base import SpecialistSpec

_TRADE_REQUIRED = frozenset({("trade", "get_trade"), ("trade", "get_settlement_status")})

SETTLEMENT = SpecialistSpec(
    name="settlement",
    planner_prompt="planner/trade",
    synthesis_prompt="synthesis/finding",
    # reads client/SSI to establish "our instruction is current"; cannot write SSI
    tool_servers=frozenset({"trade", "counterparty", "position", "client", "ops"}),
    allowlist_key="settlement",
    subject_type="trade",
    required_tools=_TRADE_REQUIRED,
)

RISK_CLIENT = SpecialistSpec(
    name="risk_client",
    planner_prompt="planner/risk_client",
    synthesis_prompt="synthesis/risk_client",
    tool_servers=frozenset({"client", "compliance", "counterparty", "ops"}),
    allowlist_key="risk_client",
    subject_type="account",
    required_tools=frozenset(),  # no fixed required tool — outcome comes from synthesis
)

# Knowledge is retrieval-only; its runner (a fixed search_knowledge + find_incidents
# call) and its caller arrive with the Supervisor in Phase C PR 2.
KNOWLEDGE = SpecialistSpec(
    name="knowledge",
    planner_prompt="planner/trade",  # unused — Knowledge does not plan
    synthesis_prompt="synthesis/finding",
    tool_servers=frozenset({"ops"}),
    allowlist_key="knowledge",
    subject_type="trade",
    required_tools=frozenset(),
)

# Phase E — the Developer Agent, incident mode. Reasons about the *system*, not a client:
# scope is `platform` + `ops` (logs) + read-only `trade` (blast radius). No client / account
# / wire scope. Allowlist has NO deploy / merge / approve / config-write (a test asserts).
DEVELOPER = SpecialistSpec(
    name="developer",
    planner_prompt="planner/incident",
    synthesis_prompt="synthesis/incident",
    tool_servers=frozenset({"platform", "ops", "trade"}),
    allowlist_key="developer",
    subject_type="job",
    required_tools=frozenset({("platform", "get_job_runs"), ("platform", "get_deployments")}),
)

_BY_NAME = {s.name: s for s in (SETTLEMENT, RISK_CLIENT, KNOWLEDGE, DEVELOPER)}


def spec_for(name: str) -> SpecialistSpec:
    return _BY_NAME[name]
