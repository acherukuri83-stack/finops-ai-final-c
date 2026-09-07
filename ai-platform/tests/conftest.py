"""Shared fixtures for MCP server tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from mcp_servers import _enterprise
from mcp_servers._fake_enterprise import FakeEnterpriseClient


@pytest.fixture
def fake_enterprise() -> Iterator[FakeEnterpriseClient]:
    """Install the in-process enterprise stand-in; reset afterwards."""
    fake = FakeEnterpriseClient()
    _enterprise.set_enterprise_client(fake)
    try:
        yield fake
    finally:
        _enterprise.set_enterprise_client(None)
