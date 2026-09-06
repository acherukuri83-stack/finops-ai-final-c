import os

import pytest
from pydantic import BaseModel

from agent_core.reasoning.model_client import (
    AnthropicModelClient,
    FakeModelClient,
    ModelResponse,
    complete_structured,
)
from agent_core.reasoning.model_router import Step, model_for


class Hello(BaseModel):
    greeting: str
    n: int


async def test_structured_output_with_fake() -> None:
    fake = FakeModelClient([ModelResponse(text='{"greeting": "hi", "n": 1}')])
    out = await complete_structured(
        fake, model="x", system="s", messages=[{"role": "user", "content": "go"}], schema=Hello
    )
    assert out == Hello(greeting="hi", n=1)


async def test_structured_output_retries_once_then_succeeds() -> None:
    fake = FakeModelClient(
        [ModelResponse(text="not json"), ModelResponse(text='{"greeting": "hi", "n": 2}')]
    )
    out = await complete_structured(
        fake, model="x", system="s", messages=[{"role": "user", "content": "go"}], schema=Hello
    )
    assert out.n == 2
    assert len(fake.calls) == 2


async def test_structured_output_fails_after_two_bad() -> None:
    fake = FakeModelClient([ModelResponse(text="nope"), ModelResponse(text="still nope")])
    with pytest.raises(ValueError):
        await complete_structured(
            fake, model="x", system="s", messages=[{"role": "user", "content": "go"}], schema=Hello
        )


def test_router_routes_classify_to_cheap() -> None:
    assert model_for(Step.CLASSIFY) != model_for(Step.SYNTHESIZE)


@pytest.mark.eval
async def test_real_model_hello() -> None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        pytest.skip("no ANTHROPIC_API_KEY")
    client = AnthropicModelClient(key)
    out = await complete_structured(
        client,
        model=model_for(Step.CLASSIFY),
        system="You are a test.",
        messages=[{"role": "user", "content": "Return greeting 'hello' and n 3."}],
        schema=Hello,
    )
    assert out.greeting.lower().startswith("hello") and out.n == 3
