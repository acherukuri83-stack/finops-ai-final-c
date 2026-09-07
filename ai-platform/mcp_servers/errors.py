"""The common error envelope every MCP tool returns on failure (docs/tool-contracts.md).

Tools never raise. On any upstream problem they return ``ErrorEnvelope.as_dict``; the
caller distinguishes success from failure by the presence of ``code`` + ``retryable``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ErrorEnvelope(BaseModel):
    code: str
    message: str
    retryable: bool
    tool: str

    @property
    def as_dict(self) -> dict[str, Any]:
        return self.model_dump()


def from_http(tool: str, status: int, body: str) -> dict[str, Any]:
    """Map an enterprise HTTP status to an envelope. 5xx retryable; 4xx not; 404 distinct."""
    if status == 404:
        return ErrorEnvelope(
            code="NOT_FOUND", message=body or "not found", retryable=False, tool=tool
        ).as_dict
    if 400 <= status < 500:
        return ErrorEnvelope(
            code=f"UPSTREAM_{status}", message=body or "client error", retryable=False, tool=tool
        ).as_dict
    return ErrorEnvelope(
        code=f"UPSTREAM_{status}", message=body or "server error", retryable=True, tool=tool
    ).as_dict


def unavailable(tool: str, detail: str) -> dict[str, Any]:
    """Enterprise unreachable after the in-tool retry."""
    return ErrorEnvelope(
        code="UPSTREAM_UNAVAILABLE", message=detail, retryable=True, tool=tool
    ).as_dict


def not_yet_available(tool: str) -> dict[str, Any]:
    """A tool whose contract is fixed but whose implementation lands in a later slice."""
    return ErrorEnvelope(
        code="NotYetAvailable",
        message=f"{tool} is not implemented until W2 (knowledge slice)",
        retryable=False,
        tool=tool,
    ).as_dict


def is_error(result: object) -> bool:
    """True if a tool result is an ErrorEnvelope payload rather than a success shape."""
    return isinstance(result, dict) and "code" in result and "retryable" in result
