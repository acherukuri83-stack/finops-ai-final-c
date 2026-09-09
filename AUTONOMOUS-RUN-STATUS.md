# Autonomous run — status

2026-09-09. **Mainline A–G complete; the deferred-depth backlog is closed; the optional
Wires module has a core slice.** No blockers.

Local gate at the last merge: ai-platform `pytest -m "not eval and not contract"` = **136
passed**; `ruff` / `mypy` clean (ai-platform + simulator); simulator scenario tests pass.
CI `verify` green on every merge (unit + `-m contract` against seeded Postgres + a real
enterprise). No eval sweeps (owner decision — `SCORECARD.md` stays Phase A 8/9).

## Merged this run (all CI `verify` green before merge)

| PR | Phase | What landed |
|---|---|---|
| #14 / #16 / #17 | C | Specialist runner + per-agent policy; Supervisor fan-out + client Sc. 11 |
| #18 | D | Event-driven: outbox bus + in-process consumer + dedup + urgency; `make emit` |
| #19 | E core | Developer Agent **incident mode**; `platform` MCP server; `POST /diagnose` |
| #20 | F core | **StockLoan** specialist; recall-vs-buy-in hard rule; `POST /investigate {loan_id}` |
| #21 | G | Real `trace_store.scrub()` + `finops.pii.redactions` |
| #22 | E | Developer Agent **verification mode** (`verify_change`); retrievable `INC-3xxx` |
| #23 | F | Sc. 30 correlation mechanism (Supervisor merges settlement + stockloan) |
| #24 | E | Developer Agent **PR-review mode** (`repo` + `ci` servers, `Review`, `POST /review`) |
| #25 | G | `schema_validation` guardrail span + `finops.tool.retries` |
| #26 / #27 / #28 | F | **Margin**, **CorpActions**, **Cash** specialists (server + spec + hard rule each) |
| #29 | E | Developer Agent **eval-authoring mode** (`author_scenario`, `POST /author-scenario`) |
| #30 | F + E | **Prime Finance portal tab**; bounded Supervisor→Developer hand-off (`_recommend_incident_review`) |
| #33 | C | **Knowledge specialist wired** into the Supervisor; `decompose.md` covers all seven agents |
| #34 | F | **Prime-finance data seeded** — the four stores on `_finance_store` (MEM + SQL over seeded Postgres, 14 tables); `supervisor._open_loans` discovery; `simulator/scenarios/030_mixed_domain_client.yaml` |
| #36 | — | **Deferred-depth backlog closed** — `_apply_domain_rule` (fan-out runs the per-domain hard rules); `margin_calls` / `ca_events` / `ca_entitlements` / `cash_breaks` planter keys; the rest closed-as-accepted with rationale in `docs/backlog.md` |

(Portal PRs #31 / #35 were merged by the account owner in parallel — no conflict with the
agent work. #32 was the first Knowledge PR, re-opened as #33 after a rebase.)

## Backlog state

`docs/backlog.md` opens with a **Status** line. Every deferred-depth item is shipped or
**closed-as-accepted** (search `Closed (2026-09-09)` for each rationale). The optional
**Wires** module is built: PR #37 (core slice — Wire specialist + `wire` server + the four
maker/checker/cutoff/screening hard rules + `POST /investigate {wire_id}` +
`tests/test_wire.py`), and PR #38 (seeded Postgres + a `simulator` planter for `wire`, the
Sc. 7 / 13–16 `subject: wire` YAMLs + `evals/harness.py` dispatch, `supervisor._held_wires`
discovery). Still deferred (in `docs/backlog.md`): a wire corpus; the portal
`WIRE_REVIEWER` release flow. What remains project-wide, by owner decision and not a gap:

1. **End-of-project eval sweep** — a full `workflow_dispatch` run + refreshed
   `evals/SCORECARD.md`. Paused for C+ during the build; the record stays Phase A 8/9.
   Known items for that sweep: Sc. 11 / Sc. 30 `groups` scoring, Sc. 8 evidence-citation,
   the wire scenarios once a `wire` table is seeded.

## Notes / deviations

- `ScheduleWakeup` (the `/loop` self-pacer) is blocked by the environment classifier, so
  the unattended portion ran as one continuous in-session loop.
- After a rebase, `git push --force` / `--force-with-lease` are blocked — a rebased branch
  is re-pushed under a fresh name and the old PR closed (see #32 → #33).
- E/F domain servers (`platform`, `repo`, `ci`, and the four prime-finance domains) are
  Python-tier — `platform` / `repo` / `ci` are in-process fixtures; the four prime-finance
  stores are seeded Postgres via `mcp_servers/_finance_store.py`. The Java tier is
  untouched (its own `CLAUDE.md` documents the "Java stays out of platform-era tables"
  rule).
- Hard rules are code, not prompt (rule 4): `_enforce_fix_strategy`,
  `_enforce_recall_window`, `_enforce_call_window`, `_enforce_record_date`,
  `_enforce_funding_cutoff` — and, since #36, the Supervisor fan-out runs them too via
  `_apply_domain_rule`.

## Next step

Nothing is queued. New work should start from a fresh product ask. If the eval sweep is
run: `make eval` (n=3, ~$2–3), then commit `evals/SCORECARD.md` and confirm Sc. 8 / 11 /
30. If Wires is wanted: read the Phase B section of `docs/phase-breakdown.md` first.
