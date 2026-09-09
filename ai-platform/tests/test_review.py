"""Phase E — Developer Agent, PR-review mode.

Deterministic. Seeded PRs in `mcp_servers/repo/store.py`, deterministic-check fixtures in
`mcp_servers/ci/store.py`. Covers the platform hard rules: a write tool with no
`approval_id` → BLOCKER + REQUEST_CHANGES; an agent-authored scenario → needs a human; a
clean change → APPROVE; a touched planted scenario → its eval must re-run. And: no
approve/merge tool exists anywhere.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from agent_core import policy
from agent_core.review import review_pr
from mcp_servers.hub import SERVERS
from mcp_servers.repo import store as repo_store
from mcp_servers.repo.tools import post_review
from platform_api import cases

_FORBIDDEN = {"approve_pr", "merge_pr", "approve", "merge", "force_merge", "land"}


@pytest.fixture(autouse=True)
def _reset() -> Iterator[None]:
    repo_store.reset()
    yield
    repo_store.reset()


def test_no_approve_or_merge_tool_anywhere() -> None:
    all_tools = {fn.__name__ for spec in SERVERS.values() for fn in spec.tools}
    assert all_tools.isdisjoint(_FORBIDDEN), all_tools & _FORBIDDEN
    assert "repo" in SERVERS and "ci" in SERVERS
    assert policy.allowed("developer", "post_review") is True
    assert policy.allowed("developer", "approve_pr") is False


async def test_write_tool_without_approval_id_is_a_blocker() -> None:
    review = await review_pr("PR-19")

    assert "mcp_contract" in review.surfaces
    blockers = [f for f in review.findings if f.severity == "BLOCKER"]
    assert any("approval_id" in f.message for f in blockers)
    assert any("§4.1" in f.evidence for f in blockers)
    assert review.recommendation == "REQUEST_CHANGES"


async def test_clean_change_is_approved() -> None:
    review = await review_pr("PR-21")
    assert not any(f.severity in ("BLOCKER", "MAJOR") for f in review.findings)
    assert review.recommendation == "APPROVE"


async def test_touched_planted_scenario_flags_an_eval_rerun() -> None:
    review = await review_pr("PR-20")
    assert "simulator" in review.surfaces
    assert any("scenario 1" in f.message and "re-run" in f.message for f in review.findings)
    # PR-20 also has a failing scenario test in the fixtures -> not APPROVE
    assert review.recommendation == "REQUEST_CHANGES"


async def test_agent_authored_scenario_needs_a_human_reviewer() -> None:
    review = await review_pr("PR-25")
    assert any("human reviewer" in f.message for f in review.findings)
    assert review.recommendation == "REQUEST_CHANGES"


async def test_post_review_honours_the_approval_gate(fake_enterprise: object) -> None:
    forged = await post_review("PR-21", "{}", approval_id="ap_forged2")
    assert forged["code"] == "ApprovalError"
    assert repo_store.reviews() == []

    case = cases.create_case("pr", "PR-21", "review")
    approval = cases.propose_action(
        case["case_id"],
        "post_review",
        {"pr_id": "PR-21"},
        "review",
        [{"type": "pr", "id": "PR-21"}],
        True,
    )
    cases.decide(approval["approval_id"], "APPROVED", "d.patel", "OPS_ANALYST")
    ok = await post_review(
        "PR-21", '{"recommendation": "APPROVE"}', approval_id=approval["approval_id"]
    )
    assert ok["posted"] is True
    assert len(repo_store.reviews()) == 1
