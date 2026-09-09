"""stockloan-server (Phase F core slice) — reads over the simulated securities-lending
book plus three approval-gated writes. In-process, fixture-backed."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_servers.stockloan.tools import (
    book_buy_in,
    get_lending_availability,
    get_loan,
    get_recall,
    get_rerate_history,
    initiate_recall,
    list_loans,
    rerate_loan,
)

mcp = FastMCP("stockloan")

for _fn in (
    get_loan,
    list_loans,
    get_recall,
    get_rerate_history,
    get_lending_availability,
    initiate_recall,
    rerate_loan,
    book_buy_in,
):
    mcp.tool()(_fn)
