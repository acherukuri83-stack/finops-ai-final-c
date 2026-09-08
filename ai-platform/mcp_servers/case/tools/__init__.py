"""case-server tools. Docstrings are the exposed descriptions (docs/tool-contracts.md).

Backed by `platform_api.cases` (same process). These are `write*` — agent-allowed with no
`approval_id`; they are bookkeeping, not enterprise mutations.
"""

from __future__ import annotations

from typing import Any

from mcp_servers.case.client import cases, guard


@guard
async def create_case(
    subject_type: str, subject_id: str, summary: str, evidence: list[str] | None = None
) -> dict[str, Any]:
    """Open a case for a subject. *Agent-allowed without approval — it is bookkeeping."""
    case = cases.create_case(subject_type, subject_id, summary)
    if evidence:
        cases.log_audit(case["case_id"], f"evidence: {', '.join(evidence)}")
    return case


@guard
async def update_case(case_id: str, notes: str, status: str | None = None) -> dict[str, Any]:
    """Append notes / change status."""
    return cases.update_case(case_id, notes, status)


@guard
async def propose_action(
    case_id: str,
    action_type: str,
    params: dict[str, str],
    rationale: str,
    impact: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Register a proposed action; returns approval_id with status PENDING. The only way an agent can request a write."""
    return cases.propose_action(case_id, action_type, params, rationale, impact or [])


@guard
async def get_approval(approval_id: str) -> dict[str, Any]:
    """status PENDING/APPROVED/REJECTED, decided_by, role, decided_at. Write tools call this."""
    approval = cases.get_approval(approval_id)
    if approval is None:
        return {
            "code": "NOT_FOUND",
            "message": f"no approval {approval_id}",
            "retryable": False,
            "tool": "get_approval",
        }
    return approval


@guard
async def log_audit(case_id: str, event: str) -> dict[str, Any]:
    """Append an audit event."""
    cases.log_audit(case_id, event)
    return {"case_id": case_id, "logged": event}
