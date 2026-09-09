# Autonomous run — status

Unattended session, 2026-09-09. Task: finish the FinOps AI mainline (phases E, F, G)
without user interaction. **Stop reason: all core slices merged.** No blockers.

## Merged this run (all CI `verify` green before merge)

| PR | Phase | What landed |
|---|---|---|
| #14 | C · PR 1 | Specialist runner + per-agent policy (Settlement can't write SSI) |
| #16 | C · PR 2 | Supervisor fan-out + client Scenario 11 (`groups` scorer) |
| #17 | C docs | Phase C complete; eval sweeps paused for C+ |
| #18 | D | Event-driven: `platform_api/events/` outbox bus + in-process consumer + dedup + urgency; `make emit` |
| #19 | E core | Developer Agent **incident mode**: `platform` MCP server, `investigate_incident`, revert/fix-forward hard rule, `POST /diagnose`, Engineering tab |
| #20 | F core | **StockLoan** specialist: `stockloan` MCP server, `investigate_loan`, recall-vs-buy-in hard rule, `POST /investigate {loan_id}`, Supervisor `stockloan` sub-task |
| #21 | G item | Real `trace_store.scrub()` (emails / ids / person-keys) + `finops.pii.redactions` on the span |

Plus this commit: root `CLAUDE.md` + `docs/project-status.md` flipped to "no active phase"; this file.

`main` @ `b6f7cf4` + the final docs commit. Local `pytest -m "not eval and not contract"` = **87 passed** at each merge; `ruff`/`mypy` clean for ai-platform + simulator; portal `lint`/`tsc`/`build` clean.

## Deferred per phase (also in `docs/backlog.md`)

**E — Developer Agent**
- verification mode (`Expectation[]` → re-check → delta → hand-off → write `INC-3xxx`)
- PR-review mode: `repo` + `ci` MCP servers, `Review` schema, BLOCKER rules (`open_pull_request` / `post_review` are already on the `developer` allowlist; servers unbuilt)
- eval-authoring mode
- Supervisor → `developer.investigate_incident` hand-off when every business sub-finding is `INSUFFICIENT_EVIDENCE` (today only reachable via `POST /diagnose`)
- standards corpus indexed for review retrieval

**F — Prime finance**
- Margin & collateral, corporate actions, cash domains (one server + specialist + allowlist + hard rules each)
- seeded table + `simulator` planter for stock loan, replacing `mcp_servers/stockloan/store.py` fixtures
- Scenario 30 (mixed client: settlement fail + held wire + recall → one synthesized answer) + a client-run test
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

Nothing is blocked. To continue, pick one deferred item above, read its `docs/phase-breakdown.md` section + the relevant nested `CLAUDE.md`, bump the root `CLAUDE.md` "Current phase" line, and implement it as its own PR following the established patterns. The highest-leverage next items: **E verification mode** (completes the incident→verify→hand-off loop the demo script wants) and **F Scenario 30** (the mixed-client synthesis demo).
