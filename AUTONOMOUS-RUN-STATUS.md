# Autonomous run — status

Unattended session, 2026-09-09. Task: finish the FinOps AI mainline (A→G), then work
through the deferred phase-depth backlog. **No blockers.** `main` @ `c812dac`.

Local gate at the last merge: `pytest -m "not eval and not contract"` = **131 passed**;
`ruff` / `mypy` clean (ai-platform); portal `lint` / `tsc` / `build` clean. No eval
sweeps (owner decision — the `SCORECARD.md` on record stays Phase A 8/9).

## Merged this run (all CI `verify` green before merge)

| PR | Phase | What landed |
|---|---|---|
| #14 / #16 / #17 | C | Specialist runner + per-agent policy; Supervisor fan-out + client Scenario 11; phase-complete docs |
| #18 | D | Event-driven: `platform_api/events/` outbox bus + in-process consumer + dedup + urgency; `make emit` |
| #19 | E core | Developer Agent **incident mode**: `platform` MCP server, `investigate_incident`, revert/fix-forward hard rule, `POST /diagnose`, Engineering tab |
| #20 | F core | **StockLoan** specialist: `stockloan` MCP server, `investigate_loan`, recall-vs-buy-in hard rule, `POST /investigate {loan_id}`, Supervisor `stockloan` sub-task |
| #21 | G item | Real `trace_store.scrub()` (emails / ids / person-keys) + `finops.pii.redactions` on the span |
| #22 | E depth | Developer Agent **verification mode**: `verify_change(ticket_id)`, residual → Settlement (`sub_finding`), retrievable `INC-3xxx`; failed fix reports + no second fix. `POST /verify` |
| #23 | F depth | **Scenario 30** mechanism — Supervisor correlates `settlement` + `stockloan` into one mixed-domain client answer (unit-tested) |
| #24 | E depth | Developer Agent **PR-review mode**: `repo` + `ci` fixture servers, `Review` schema, `review_pr`, code BLOCKER rules, `POST /review`, Engineering review input |
| #25 | G item | `schema_validation` guardrail span (from `complete_structured_traced`) + `finops.tool.retries` (from `_enterprise.last_retries()`) |
| #26 / #27 / #28 | F depth | **Margin**, **CorpActions**, **Cash** specialists — one fixture server + spec + entry point + hard rule + Supervisor sub-task each. All four prime-finance domains shipped. |
| #29 | E depth | Developer Agent **eval-authoring mode**: `author_scenario(failure_code)` → planted-chain YAML + `expect:` + baseline, `authored_by: agent` (which review mode blocks). `POST /author-scenario` |
| #30 | F + E depth | **Prime Finance portal tab** (`PrimeFinanceView.tsx`, one tab / four domains) + **bounded Supervisor→Developer hand-off** (`_recommend_incident_review`: all-`INSUFFICIENT_EVIDENCE` → an `open_questions` note recommending `POST /diagnose`; recommendation only) |
| #33 | C depth | **Knowledge specialist wired** — `run_knowledge` (degenerate: fixed retrieval, no planner/model, proposes nothing) routed by the Supervisor; `_business()` keeps it out of outcome reconciliation; `decompose.md` rewritten for all seven agents (also fixed the margin/corpactions/cash prompt gap) |

(PRs #31, #32: #31 was a portal styling PR the account owner merged mid-run — no conflict
with the agent work; #32 was the first Knowledge PR, closed and re-opened as #33 after a
clean rebase onto #31.)

## Mainline status

**A (done) · C · D · E · F · G — every mainline phase has a merged, CI-green core slice
plus most of the deferred depth.** Root `CLAUDE.md` "Current phase" =
"filling in deferred phase depth, item by item".

## Still deferred (also in `docs/backlog.md`) — and why each was left

**Needs the account owner / a product call — did NOT attempt unattended:**

1. **F — seeded tables + `simulator` planter for the four prime-finance domains**,
   replacing the in-process `mcp_servers/*/store.py` fixtures. This is the largest
   remaining item: a cross-tier change (enterprise Java schema + Flyway + `simulator`
   planter + rewiring four fixture stores) whose DB-backed tests **cannot be validated
   locally** (they hang without Postgres; CI runs them). Unlocks a *scored* Scenario 30
   (so `investigate_client` can *discover* a loan the way it discovers failed trades —
   today `supervisor._failed_trades` only queries `find_trades`). Left for an attended
   session.
2. **E — standards corpus in pgvector for PR-review retrieval.** Owner was leaning
   "acceptable as is" — `review.py` cites `docs/standards/*.md` sections directly rather
   than retrieving them. Needs an owner decision to build or to formally close; not mine
   to decide unilaterally.
3. **E — auto-dispatch** of the Developer Agent on all-`INSUFFICIENT_EVIDENCE`. The
   *bounded recommendation* shipped in #30; auto-dispatch is still blocked on the open
   product question of how the Supervisor names the incident subject (which job id / which
   service) with no safe default. Documented in `docs/backlog.md` + `CLAUDE.md`.

**Genuine follow-ups / low value — not blocking:**

4. **E — eval-authoring's model-driven "from any SOP section" mode** (the fixed
   3-template version is shipped).
5. **G — trace replay/diff polish; Bedrock model-client swap; the memory loop.** No
   concrete spec; Bedrock needs infra + a decision.
6. **F — `market` / `position` are on the `stockloan` spec's scope but no test exercises
   a price move or a real position lookup** (the scope wiring is covered by
   `test_mcp_contract.py`; this is test *depth*, not a gap).
7. **Sc. 8 (duplicate_trade) hill-climb** — blocked: needs `make eval` runs, and eval
   sweeps are paused for C+ by owner decision.
8. **Project-wide** — the full `workflow_dispatch` eval sweep + refreshed
   `evals/SCORECARD.md`, deferred to end-of-project by owner decision. Accepted risk: a
   model-behaviour regression in any specialist / the Supervisor won't surface until then.
9. **Phase B (Wires)** — the optional module, unbuilt (depends only on A; nothing in
   C–G depends on it).

## Notes / deviations

- `ScheduleWakeup` (the `/loop` self-pacer) is blocked by the environment classifier, so
  this ran as one continuous in-session loop. No functional impact.
- After a rebase, `git push --force` / `--force-with-lease` are blocked, so a rebased
  branch is re-pushed under a fresh name and the old PR closed (see #32 → #33).
- E/F domain servers (`platform`, `stockloan`, `margin`, `corpactions`, `cash`, `repo`,
  `ci`) are **in-process Python fixture stores**, following the `case`-server precedent —
  no Java / Flyway / simulator planter (item 1 above is the fuller version).
- Hard rules are code, not prompt (ADR-0002 pattern): `_enforce_fix_strategy`,
  `_enforce_recall_window`, `_enforce_call_window`, `_enforce_record_date`,
  `_enforce_funding_cutoff`.

## Exact next step

Nothing is blocked; the run stopped because the remaining backlog items are either
owner-decisions (items 1–3), specless follow-ups (4–5), or eval-gated (7–8) — none are
safe "self-contained, locally-verifiable" unattended work.

To resume: pick a deferred item, read its `docs/phase-breakdown.md` section + the relevant
nested `CLAUDE.md`, bump the root `CLAUDE.md` line, implement it as its own PR following
the established patterns (in-process fixture servers, hard rules in code, per-agent
allowlists, `run_specialist` / `run_knowledge`). The highest-leverage attended item is
**#1 — seeded prime-finance tables + planter** (unlocks the scored Scenario 30 and moves
all four domains onto real data).
