"""Shared helpers for the read servers: validate an enterprise payload against a
contract model and return it as a plain dict, or pass an ``ErrorEnvelope`` straight
through.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from mcp_servers.errors import is_error


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
