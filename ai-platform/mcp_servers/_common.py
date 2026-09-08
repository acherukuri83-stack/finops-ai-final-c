"""Shared helpers for the servers: shape an enterprise payload against a contract model,
and (for write tools) validate an ``approval_id`` against the case store — the check that
lives *in the tool* (docs/standards/security.md §2–§4, ADR-0001).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from mcp_servers.errors import ErrorEnvelope, is_error


def shape[M: BaseModel](model: type[M], payload: Any) -> dict[str, Any]:
    """One object → the contract shape. An error payload passes through untouched."""
    if is_error(payload):
        return payload  # type: ignore[no-any-return]
    return model.model_validate(payload).model_dump(mode="json")


def shape_list[M: BaseModel](model: type[M], payload: Any) -> Any:
    """A list payload → list of contract shapes. An error payload passes through."""
    if is_error(payload):
        return payload
    return [model.model_validate(row).model_dump(mode="json") for row in payload]


def check_approval(action_type: str, subject_id: str, approval_id: str) -> dict[str, Any] | None:
    """None if `approval_id` is an APPROVED approval for exactly this action + subject;
    otherwise the `ErrorEnvelope` the write tool must return instead of executing.
    """
    from platform_api import cases

    def deny(message: str) -> dict[str, Any]:
        return ErrorEnvelope(
            code="ApprovalError", message=message, retryable=False, tool=action_type
        ).as_dict

    approval = cases.get_approval(approval_id)
    if approval is None:
        return deny(f"no approval {approval_id}")
    if approval["status"] != cases.APPROVED:
        return deny(f"approval {approval_id} is {approval['status']}, not APPROVED")
    if approval["action_type"] != action_type:
        return deny(f"approval {approval_id} is for {approval['action_type']}, not {action_type}")
    covered = {s.get("id") for s in approval.get("impact", [])} | set(
        (approval.get("params") or {}).values()
    )
    if subject_id not in covered:
        return deny(f"approval {approval_id} does not cover {subject_id}")
    return None
