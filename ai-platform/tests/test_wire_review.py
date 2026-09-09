"""Phase B — the WIRE_REVIEWER release flow (`GET /wire/queue`, `GET /wire/exceptions`,
`POST /wire/release`).

The endpoints in `platform_api/main.py` are thin role-gated wrappers over these
`mcp_servers.wire.store` functions; the logic under test is here (MEM mode via the autouse
conftest fixture). `release_wire` is a human-only action — there is still no `release_wire`
agent tool (`tests/test_wire.py` asserts that).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from mcp_servers.wire import store as wire_store


@pytest.fixture(autouse=True)
def _reset_wire() -> Iterator[None]:
    wire_store.reset()
    yield
    wire_store.reset()


def test_exceptions_lists_every_held_wire_by_reason() -> None:
    rows = wire_store.exceptions()
    assert {w["wire_id"] for w in rows} == {"W300915", "W300917", "W300918", "W300920", "W300921"}
    assert all(w["status"] == "HELD" for w in rows)
    reasons = [w["hold_reason"] for w in rows]
    assert reasons == sorted(reasons)  # grouped/ordered by hold reason


def test_queue_reflects_a_routed_wire_then_clears_on_release() -> None:
    assert wire_store.get_approval_queue() == []
    wire_store.record_action(
        "route_to_reviewer", "W300917", {"reason": "new beneficiary", "packet": "p"}, "ap1"
    )
    q = wire_store.get_approval_queue()
    assert [i["wire_id"] for i in q] == ["W300917"]
    assert q[0]["packet"] == "p"

    released = wire_store.release_wire("W300917", "reviewer.demo")
    assert released is not None and released["status"] == "RELEASED"
    assert wire_store.get_approval_queue() == []  # the OPEN route action was closed
    assert any(a["kind"] == "release" for a in wire_store.actions())


def test_release_of_an_unknown_or_non_held_wire_returns_none() -> None:
    assert wire_store.release_wire("W-NOPE", "reviewer.demo") is None
    wire_store.release_wire("W300918", "reviewer.demo")
    assert wire_store.release_wire("W300918", "reviewer.demo") is None  # already released
    assert (wire_store.get_wire("W300918") or {})["status"] == "RELEASED"
