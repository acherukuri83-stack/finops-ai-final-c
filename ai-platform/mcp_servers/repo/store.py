"""In-process fixture store for the `repo` server (Phase E — review mode).

Seeded pull requests the Developer Agent reviews. Facts only: the diff text and the
touched files. Whether a diff is safe is the review's job (hard rules in
`agent_core/review.py`, not here).

`open_pull_request` appends to `_DRAFTS`; `post_review` appends to `_REVIEWS` — both after
an APPROVED approval, mirroring the enterprise write tools.
"""

from __future__ import annotations

from typing import Any

# --- seeded pull requests -------------------------------------------------------

_PR_19_DIFF = """\
--- a/ai-platform/mcp_servers/trade/tools/__init__.py
+++ b/ai-platform/mcp_servers/trade/tools/__init__.py
@@ -40,0 +41,6 @@
+@guard
+async def force_settle(trade_id: str) -> Any:
+    \"\"\"Force a failed trade to settled.\"\"\"
+    result = await get_enterprise_client().post_json("force_settle", f"/trades/{trade_id}/force")
+    return result
"""

_PR_20_DIFF = """\
--- a/simulator/scenarios/001_counterparty_ssi_stale.yaml
+++ b/simulator/scenarios/001_counterparty_ssi_stale.yaml
@@ -6,1 +6,1 @@
-    - {cpty: CP-017, dtc: "5678", valid_to: 2027-01-01}
+    - {cpty: CP-017, dtc: "9999", valid_to: 2027-01-01}
"""

_PR_21_DIFF = """\
--- a/ai-platform/agent_core/outcomes.py
+++ b/ai-platform/agent_core/outcomes.py
@@ -24,1 +24,2 @@
-_NO_CODE = {None, "", "UNKNOWN"}
+_NO_CODE = {None, "", "UNKNOWN", "PENDING"}
+# PENDING settlement has no failure_code yet — treat it like UNKNOWN for classification
"""

_PR_25_DIFF = """\
--- /dev/null
+++ b/simulator/scenarios/031_borrow_recall_late.yaml
@@ -0,0 +1,9 @@
+id: 31
+name: borrow_recall_late
+authored_by: agent
+plant:
+  trades:
+    - {id: T100320, client: HEDGE_FUND_101, account: ACC-88213, security: NVDA,
+       qty: 5000, side: SELL, price: 118.4, trade_date: 2026-09-03,
+       settle_date: 2026-09-04, status: FAILED,
+       failure_code: INSUFFICIENT_POSITION, cpty: CP-017}
+expect: {root_cause: RECALL_WINDOW_MISSED, action_class: book_buy_in}
"""

_PULL_REQUESTS: dict[str, dict[str, Any]] = {
    "PR-19": {
        "pr_id": "PR-19",
        "title": "add force_settle tool",
        "author": "dev.contrib",
        "files": ["ai-platform/mcp_servers/trade/tools/__init__.py"],
        "diff": _PR_19_DIFF,
        "linked_issue": "ISSUE-402: settlement backlog",
    },
    "PR-20": {
        "pr_id": "PR-20",
        "title": "tweak Sc.1 counterparty SSI",
        "author": "dev.contrib",
        "files": ["simulator/scenarios/001_counterparty_ssi_stale.yaml"],
        "diff": _PR_20_DIFF,
        "linked_issue": "",
    },
    "PR-21": {
        "pr_id": "PR-21",
        "title": "treat PENDING settlement like UNKNOWN",
        "author": "dev.contrib",
        "files": ["ai-platform/agent_core/outcomes.py"],
        "diff": _PR_21_DIFF,
        "linked_issue": "ISSUE-410",
    },
    "PR-25": {
        "pr_id": "PR-25",
        "title": "[agent] scenario: late borrow recall",
        "author": "developer-agent",
        "files": ["simulator/scenarios/031_borrow_recall_late.yaml"],
        "diff": _PR_25_DIFF,
        "linked_issue": "",
    },
}

_SOURCE: dict[str, str] = {
    "ai-platform/mcp_servers/trade/tools/__init__.py:41": (
        "41  @guard\n42  async def force_settle(trade_id: str) -> Any:\n"
        "43      # no approval_id, no check_approval — mutates enterprise state\n"
    ),
}

# --- mutable ------------------------------------------------------------------

_DRAFTS: list[dict[str, Any]] = []
_REVIEWS: list[dict[str, Any]] = []
_SEQ = 0


def reset() -> None:
    global _SEQ
    _DRAFTS.clear()
    _REVIEWS.clear()
    _SEQ = 0


def get_pull_request(pr_id: str) -> dict[str, Any] | None:
    row = _PULL_REQUESTS.get(pr_id)
    return dict(row) if row else None


def get_diff(pr_id: str) -> str | None:
    row = _PULL_REQUESTS.get(pr_id)
    return row["diff"] if row else None


def get_source(ref: str) -> str | None:
    return _SOURCE.get(ref)


def add_draft(title: str, body: str, files: list[str], approval_id: str) -> dict[str, Any]:
    global _SEQ
    _SEQ += 1
    draft = {
        "pr_id": f"PR-DRAFT-{_SEQ:03d}",
        "title": title,
        "body": body,
        "files": files,
        "status": "DRAFT",
        "approval_id": approval_id,
    }
    _DRAFTS.append(draft)
    return dict(draft)


def add_review(pr_id: str, review: dict[str, Any], approval_id: str) -> dict[str, Any]:
    row = {"pr_id": pr_id, "review": review, "approval_id": approval_id, "posted": True}
    _REVIEWS.append(row)
    return dict(row)


def drafts() -> list[dict[str, Any]]:
    return [dict(d) for d in _DRAFTS]


def reviews() -> list[dict[str, Any]]:
    return [dict(r) for r in _REVIEWS]
