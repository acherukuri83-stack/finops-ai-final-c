"""Shared fixtures for MCP server tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from mcp_servers import _enterprise
from mcp_servers._fake_enterprise import FakeEnterpriseClient
from platform_api import cases


@pytest.fixture(autouse=True)
def _mem_cases() -> Iterator[None]:
    """Every unit test uses the in-memory case store — no Postgres."""
    cases.set_backend(cases.MemBackend())
    try:
        yield
    finally:
        cases.set_backend(None)


@pytest.fixture
def fake_enterprise() -> Iterator[FakeEnterpriseClient]:
    """Install the in-process enterprise stand-in; reset afterwards."""
    fake = FakeEnterpriseClient()
    _enterprise.set_enterprise_client(fake)
    try:
        yield fake
    finally:
        _enterprise.set_enterprise_client(None)
