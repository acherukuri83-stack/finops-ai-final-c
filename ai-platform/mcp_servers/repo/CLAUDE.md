# mcp_servers/repo — conventions (Phase E — review mode)

- Wraps a **simulated code host** — in-process, fixture-backed (`store.py`), like
  `platform` / `stockloan` / `ci`. No `client.py`, no `_enterprise`.
- Reads: `get_pull_request`, `get_diff`. Writes (approval-gated via `check_approval`):
  `open_pull_request` (**draft only**), `post_review` (**comments only**).
- **There is no `approve_pr` / `merge_pr` / `land` tool** — `tests/test_review.py` asserts
  the whole tool surface is disjoint from that set. The agent reviews; a human merges.
- Seeded PRs: PR-19 (write tool w/o approval_id → BLOCKER), PR-20 (touches a planted
  scenario → eval re-run), PR-21 (clean → APPROVE), PR-25 (`authored_by: agent` → needs a
  human reviewer).
- The review logic and its hard rules live in `agent_core/review.py`, not here.
