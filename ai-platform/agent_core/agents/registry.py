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

# Phase F (core slice) — the StockLoan specialist. Scope: its own book + `market` +
# read-only `position` (to see the delivery it must cover) + `ops`. The recall-window
# rule (recall vs buy-in) is code, in `agent_core/stockloan.py`.
STOCKLOAN = SpecialistSpec(
    name="stockloan",
    planner_prompt="planner/stockloan",
    synthesis_prompt="synthesis/stockloan",
    tool_servers=frozenset({"stockloan", "market", "position", "ops"}),
    allowlist_key="stockloan",
    subject_type="loan",
    required_tools=frozenset({("stockloan", "get_loan")}),
)

# Phase F — the Margin specialist. Scope: its own book + `market` + read-only `position`
# + `ops`. The call-window rule (meet vs close-out) is code, in `agent_core/margin.py`.
MARGIN = SpecialistSpec(
    name="margin",
    planner_prompt="planner/margin",
    synthesis_prompt="synthesis/margin",
    tool_servers=frozenset({"margin", "market", "position", "ops"}),
    allowlist_key="margin",
    subject_type="margin_call",
    required_tools=frozenset({("margin", "get_margin_call")}),
)

# Phase F — the CorpActions specialist. Scope: its own book + read-only `stockloan` (to
# see the lent slice) + `position` + `ops`. The record-date / election-deadline rule is
# code, in `agent_core/corpactions.py`.
CORPACTIONS = SpecialistSpec(
    name="corpactions",
    planner_prompt="planner/corpactions",
    synthesis_prompt="synthesis/corpactions",
    tool_servers=frozenset({"corpactions", "stockloan", "position", "ops"}),
    allowlist_key="corpactions",
    subject_type="ca_event",
    required_tools=frozenset({("corpactions", "get_ca_event")}),
)

# Phase F — the Cash specialist. Scope: its own book + `market` (FX) + `ops`. The
# funding-cutoff rule (fund vs escalate) is code, in `agent_core/cash.py`.
CASH = SpecialistSpec(
    name="cash",
    planner_prompt="planner/cash",
    synthesis_prompt="synthesis/cash",
    tool_servers=frozenset({"cash", "market", "ops"}),
    allowlist_key="cash",
    subject_type="cash_break",
    required_tools=frozenset({("cash", "get_cash_break")}),
)

_BY_NAME = {
    s.name: s
    for s in (
        SETTLEMENT,
        RISK_CLIENT,
        KNOWLEDGE,
        DEVELOPER,
        STOCKLOAN,
        MARGIN,
        CORPACTIONS,
        CASH,
    )
}


def spec_for(name: str) -> SpecialistSpec:
    return _BY_NAME[name]
