"""repo-server tools (Phase E — review mode). Docstrings are the exposed descriptions.

Reads over the simulated code host (`mcp_servers.repo.store`). `open_pull_request` (draft
only) and `post_review` validate an APPROVED `approval_id`. **There is no `approve_pr` or
`merge_pr` tool** — the agent reviews, a human merges (`tests/test_review.py` asserts).
"""

from __future__ import annotations

import json
from typing import Any

from mcp_servers._common import check_approval
from mcp_servers.repo import store


def _nf(what: str, tool: str) -> dict[str, Any]:
    return {"code": "NOT_FOUND", "message": what, "retryable": False, "tool": tool}


async def get_pull_request(pr_id: str) -> Any:
    """PR metadata: title, author, touched files, linked issue."""
    row = store.get_pull_request(pr_id)
    return row or _nf(f"no PR {pr_id}", "get_pull_request")


async def get_diff(pr_id: str) -> Any:
    """The unified diff for a PR as text. Classify the touched surfaces from the file paths."""
    diff = store.get_diff(pr_id)
    return {"pr_id": pr_id, "diff": diff} if diff is not None else _nf(f"no PR {pr_id}", "get_diff")


async def open_pull_request(title: str, body: str, files: str, approval_id: str) -> Any:
    """Open a **draft** PR (`files` = comma-separated paths). Requires an APPROVED approval_id. Does not merge — a human does."""
    denied = check_approval("open_pull_request", title, approval_id)
    if denied:
        return denied
    draft = store.add_draft(
        title, body, [f.strip() for f in files.split(",") if f.strip()], approval_id
    )
    _audit(approval_id, f"opened draft {draft['pr_id']}")
    return draft


async def post_review(pr_id: str, review: str, approval_id: str) -> Any:
    """Post a structured `Review` (JSON string) as comments on a PR. Requires an APPROVED approval_id. Comments only — never approves or merges."""
    denied = check_approval("post_review", pr_id, approval_id)
    if denied:
        return denied
    try:
        parsed = json.loads(review)
    except json.JSONDecodeError:
        return {
            "code": "TOOL_ERROR",
            "message": "review is not valid JSON",
            "retryable": False,
            "tool": "post_review",
        }
    row = store.add_review(pr_id, parsed, approval_id)
    _audit(approval_id, f"posted review on {pr_id}")
    return row


def _audit(approval_id: str, event: str) -> None:
    from platform_api import cases

    approval = cases.get_approval(approval_id)
    if approval:
        cases.log_audit(approval["case_id"], f"executed {event} via {approval_id}")
