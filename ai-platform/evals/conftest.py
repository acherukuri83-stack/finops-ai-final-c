"""Eval runs score the Finding, not the case DB — use the in-memory case store so a
scenario run needs no platform-api schema."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from platform_api import cases


@pytest.fixture(autouse=True)
def _mem_cases() -> Iterator[None]:
    cases.set_backend(cases.MemBackend())
    try:
        yield
    finally:
        cases.set_backend(None)
