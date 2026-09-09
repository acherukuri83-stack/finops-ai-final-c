"""Shared fixtures for MCP server tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from mcp_servers import _enterprise, _finance_store
from mcp_servers._fake_enterprise import FakeEnterpriseClient
from platform_api import cases
from platform_api.settings import settings


@pytest.fixture(autouse=True)
def _mem_cases() -> Iterator[None]:
    """Every unit test uses the in-memory case store and no trace DB — no Postgres.

    The four prime-finance stores (stockloan / margin / corpactions / cash) share the
    same seam: `_finance_store.set_memory(True)` keeps them on their dict fixtures.
    """
    cases.set_backend(cases.MemBackend())
    _finance_store.set_memory(True)
    was_traces = settings.traces_enabled
    settings.traces_enabled = False
    try:
        yield
    finally:
        cases.set_backend(None)
        settings.traces_enabled = was_traces


@pytest.fixture
def fake_enterprise() -> Iterator[FakeEnterpriseClient]:
    """Install the in-process enterprise stand-in; reset afterwards."""
    fake = FakeEnterpriseClient()
    _enterprise.set_enterprise_client(fake)
    try:
        yield fake
    finally:
        _enterprise.set_enterprise_client(None)
