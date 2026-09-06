"""ModelClient — the only way agent code talks to a model.

- Provider-agnostic protocol; Anthropic implementation with prompt caching on the
  system prompt and tool definitions (they dominate input tokens).
- FakeModelClient replays canned responses for unit tests. Scenario tests use the
  real client and are marked `eval`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from anthropic import AsyncAnthropic
from pydantic import BaseModel


@dataclass
class ModelResponse:
    text: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    model: str = ""


class ModelClient(Protocol):
    async def complete(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 2048,
    ) -> ModelResponse: ...


async def complete_structured[T: BaseModel](
    client: ModelClient,
    *,
    model: str,
    system: str,
    messages: list[dict[str, Any]],
    schema: type[T],
    max_tokens: int = 2048,
) -> T:
    """Ask for JSON matching `schema`; validate; retry once on failure; then raise."""
    instruction = (
        f"{system}\n\nRespond ONLY with a JSON object matching this schema, no prose:\n"
        f"{json.dumps(schema.model_json_schema())}"
    )
    last_err: Exception | None = None
    for _ in range(2):
        resp = await client.complete(
            model=model, system=instruction, messages=messages, max_tokens=max_tokens
        )
        raw = resp.text.strip().removeprefix("```json").removesuffix("```").strip()
        try:
            return schema.model_validate_json(raw)
        except Exception as e:  # noqa: BLE001
            last_err = e
            messages = [
                *messages,
                {"role": "assistant", "content": resp.text},
                {"role": "user", "content": f"Invalid: {e}. Return only valid JSON."},
            ]
    raise ValueError(f"structured output failed validation twice: {last_err}")


class AnthropicModelClient:
    def __init__(self, api_key: str) -> None:
        self._client = AsyncAnthropic(api_key=api_key)

    async def complete(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 2048,
    ) -> ModelResponse:
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "messages": messages,
        }
        if tools:
            cached_tools = [dict(t) for t in tools]
            cached_tools[-1]["cache_control"] = {"type": "ephemeral"}
            kwargs["tools"] = cached_tools
        msg = await self._client.messages.create(**kwargs)
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        tool_calls = [
            {"id": b.id, "name": b.name, "input": b.input}
            for b in msg.content
            if getattr(b, "type", "") == "tool_use"
        ]
        usage = msg.usage
        return ModelResponse(
            text=text,
            tool_calls=tool_calls,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            model=model,
        )


class FakeModelClient:
    """Replays queued responses in order. For unit tests only."""

    def __init__(self, responses: list[ModelResponse] | None = None) -> None:
        self._queue = list(responses or [])
        self.calls: list[dict[str, Any]] = []

    async def complete(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 2048,
    ) -> ModelResponse:
        self.calls.append({"model": model, "system": system, "messages": messages, "tools": tools})
        if not self._queue:
            raise RuntimeError("FakeModelClient: no queued response")
        return self._queue.pop(0)
