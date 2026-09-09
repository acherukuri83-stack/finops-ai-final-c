"""Agents: the specialist runner and the per-agent registry.

Phase C splits the monolithic Investigator into specialists that share one runner
(`base.run_specialist`), each parameterised by a `SpecialistSpec` (tool scope, prompts,
policy allowlist, budget). `agent_core/loop.py` keeps the single-trade entry point;
`agent_core/supervisor.py` (Phase C PR 2) fans out across specialists.
"""

from agent_core.agents.base import SpecialistSpec, run_specialist
from agent_core.agents.registry import KNOWLEDGE, RISK_CLIENT, SETTLEMENT, spec_for

__all__ = [
    "SpecialistSpec",
    "run_specialist",
    "SETTLEMENT",
    "RISK_CLIENT",
    "KNOWLEDGE",
    "spec_for",
]
