# Autonomous run — status

Unattended session, 2026-09-09. Task: finish the FinOps AI mainline, then pick up deferred
phase depth. **No blockers.** `main` @ `f2f130c`.

## Merged this run (all CI `verify` green before merge)

| PR | Phase | What landed |
|---|---|---|
| #14 / #16 / #17 | C | Specialist runner + per-agent policy; Supervisor fan-out + client Scenario 11; phase-complete docs |
| #18 | D | Event-driven: `platform_api/events/` outbox bus + in-process consumer + dedup + urgency; `make emit` |
| #19 | E core | Developer Agent **incident mode**: `platform` MCP server, `investigate_incident`, revert/fix-forward hard rule, `POST /diagnose`, Engineering tab |
| #20 | F core | **StockLoan** specialist: `stockloan` MCP server, `investigate_loan`, recall-vs-buy-in hard rule, `POST /investigate {loan_id}`, Supervisor `stockloan` sub-task |
| #21 | G item | Real `trace_store.scrub()` (emails / ids / person-keys) + `finops.pii.redactions` on the span |
| #22 | E depth | Developer Agent **verification mode**: `verify_change(ticket_id)` — apply, re-check job/lag, residual → Settlement (`sub_finding`), write retrievable `INC-3xxx`; failed fix reports + no second fix. `POST /verify`, `platform.get_incident`, Engineering verify input |
| #23 | F depth | **Scenario 30** — Supervisor correlates a `settlement` + `stockloan` sub-finding into one mixed-domain client answer (unit-tested; scored YAML waits on loan seeding) |

Local `pytest -m "not eval and not contract"` = **93 passed** at the last merge; `ruff`/`mypy` clean (ai-platform + simulator); portal `lint`/`tsc`/`build` clean.

## Deferred per phase (also in `docs/backlog.md`)

**E — Developer Agent**
- PR-review mode: `repo` + `ci` MCP servers, `Review` schema, BLOCKER rules (`open_pull_request` / `post_review` are already on the `developer` allowlist; servers unbuilt)
- eval-authoring mode
- Supervisor → `developer.investigate_incident` hand-off when every business sub-finding is `INSUFFICIENT_EVIDENCE` — **left as a product-design open item**: no clean way to derive the incident subject (job/service) from client-level sub-findings without more design. Today the developer path is reachable via `POST /diagnose` and `verify_change`'s residual hand-off goes the other way (developer → Settlement).
- standards corpus indexed for review retrieval

**F — Prime finance**
- Margin & collateral, corporate actions, cash domains (one server + specialist + allowlist + hard rules each)
- seeded table + `simulator` planter for stock loan, replacing `mcp_servers/stockloan/store.py` fixtures — unlocks a **scored** Scenario 30 (`investigate_client` could then discover the loan; today `supervisor._failed_trades` only queries `find_trades`)
- portal Stock Loan tab (`investigate_loan` is API-only)

**G — Hardening**
- `schema_validation` guardrail span — needs `complete_structured_traced` to return an attempt count so callers (not `model_client.py`) emit the span
- `finops.tool.retries` — thread the retry count out of `_enterprise._request`
- trace replay/diff polish, Bedrock swap, memory loop (untouched)

**Project-wide**
- Full `workflow_dispatch` eval sweep + refreshed `evals/SCORECARD.md` — paused for C+ by owner decision; the record stays the Phase A 8/9. Accepted risk: a model-behaviour regression in any specialist / the Supervisor won't surface until that sweep.
- Phase B (Wires) — optional module, unbuilt.

## Notes / deviations

- `ScheduleWakeup` (the `/loop` self-pacing tool) is blocked by the environment's classifier, so this ran as one continuous in-session loop rather than scheduled wake-ups. No functional impact.
- E/F `platform` and `stockloan` servers are **in-process Python fixtures** (`store.py`), following the `case`-server precedent — no Java, no Flyway, no simulator planter. Fine for a reviewable slice; a fuller phase moves them to seeded tables (noted above).
- PII scrub is a span **attribute** (`finops.pii.redactions`), not a separate `guardrail` span, because the scrub runs inside `PostgresSpanProcessor.on_end` and emitting a span there would recurse. `docs/standards/observability.md` documents this.
- Hard rules added as code (not prompt), matching ADR-0002's pattern: `developer._enforce_fix_strategy` (revert vs fix-forward on `release_note`), `stockloan._enforce_recall_window` (recall vs buy-in on the notice window).

## Exact next step

Nothing is blocked. To continue, pick one deferred item above, read its `docs/phase-breakdown.md` section + the relevant nested `CLAUDE.md`, bump the root `CLAUDE.md` "Current phase" line, and implement it as its own PR following the established patterns. Remaining high-leverage items:
- **E PR-review mode** — the `repo` + `ci` in-process fixture servers + `Review` schema + the code BLOCKER rules (write tool w/o `approval_id`, action not in an allowlist, model call on an unscrubbed field). Self-contained; follows the `platform`/`stockloan` server pattern.
- **F — one more prime-finance domain** (Margin is the natural next), same shape as StockLoan.
- **G — `schema_validation` guardrail span + `finops.tool.retries`** — both need small `model_client` / `_enterprise` plumbing changes (return an attempt count; thread the retry count out).
