# FinOps AI — Final Plan

Supersedes `phase-a-scope.md` and the Phase A portion of `build-plan.md`. Later phases (C onward) still follow `build-plan.md` and `agent-plan.md`; **Phase B — Wires is optional** (phase 7 there) and off the mainline. Mainline: A → C → D → E → F → G.

## Principles

1. **One use case first.** "Why didn't trade T100245 settle?" — trades only, one Investigator agent. Supervisor, events, Developer Agent, and prime-finance domains wait for later mainline phases (C+). **Wires is an optional module**, not a prerequisite for anything.
2. **Weekend cadence, Claude-heavy.** Claude Code writes ~80% of the code. Your time goes to specifying (contracts, transcripts, issues), reviewing the 20% that matters (policy, write-tool guards, prompts, schemas), and verifying exit criteria.
3. **Order: data → tools → agent → knowledge → governance → evals → trace → deploy.** Governance and evals sit in the middle, not the end — they change how the loop is built and they validate everything after them.
4. **Exit criteria are gates.** A weekend isn't done until its boxes are ticked; otherwise the next weekend's work is debt.
5. **Ideal transcripts before code.** Each scenario's transcript (plan, tools, evidence, action, what the agent must refuse) is the scoring target and carries the domain judgment only you can write.

## Phase A scope

**Scenarios:** 1 counterparty SSI stale · 2 our SSI stale (KB flips it) · 3 security reference error · 4 account restricted · 5 insufficient position · 6 counterparty instruction expired · 8 duplicate trade · 9 already remediated · 10 no evidence · 12 tool outage.

**MCP servers:** `trade`, `client`, `counterparty`, `position`, `reference`, `market`, `compliance` (read), `ops` (logs, knowledge, incidents), `case`.
**Write tools (approval-gated):** `resubmit_settlement`, `cancel_trade`, `update_ssi`.
**Agent:** single Investigator, trade mode. Allowlist: the three writes + `open_compliance_referral`, `escalate`.
**Corpus:** ~12 SOPs with numbered sections, `INC-1001…1008`, 2–3 distractor sections.
**Portal:** Cases · Trades · Settlements · Knowledge · Connections · Traces · Audit. Role: `OPS_ANALYST`.
**Out:** wires, supervisor, events (interface stub only), Developer Agent, prime finance, trace replay/diff, AWS.

## Stack

React + TypeScript (Vite) · Python 3.12 (FastAPI, own orchestrator, MCP Python SDK, pgvector, pytest) · Java 21 / Spring Boot 3 for the simulated enterprise tier · Postgres + pgvector · Claude via Anthropic API behind `ModelClient` (Haiku classify, Sonnet plan/synthesize, prompt caching on) · OpenTelemetry in both runtimes · Docker Compose locally · Railway for the demo (four services: `portal`, `ai-platform`, `enterprise`, `postgres`).

---

## Weekend 1 — Foundation, data, tools

**Friday evening (you, ~3 hrs):** commit before Claude starts
- `CLAUDE.md` (root + per-module), `docs/final-plan.md` (this), `docs/tool-contracts.md` (Phase A servers only)
- `docs/eval-scenarios.md`: the ten scenarios, each with its **ideal transcript**
- `docs/standards/` skeleton: coding, security (approval_id rule, allowlist rule), observability (span attributes)

**Saturday (Claude):**
- Monorepo skeleton, Compose (Postgres+pgvector), toolchains (uv/ruff/mypy/pytest; Maven; Vite), CI (lint, types, tests, both runtimes), `Makefile`, `scripts/verify.sh`
- `ModelClient` with a real "hello" call; Anthropic API; caching and routing config stubs
- Process layout: `ai-platform` is one ASGI app mounting platform-api and every MCP server; Compose flag to run separately
- **Simulator**: Postgres schema; baseline population with a seeded RNG (~50 clients, ~80 accounts, SSIs with 1–3 prior versions, ~200 securities, 30 days of prices, ~500 trades ~95% clean, positions, ~20 counterparties, ~20k log lines of noise); **planter** driven by per-scenario YAML (`plant:` keyed by domain, `expect:` for evals); Sc. 1, 3, 5, 6, 8, 9, 10, 12 planted; fault-injection switch for Sc. 12
- Baseline must include **other failed trades with different causes** and **healthy trades for HEDGE_FUND_101** — no shortcuts for the agent
- Every planted scenario includes **3–8 corroborating log lines** with timestamps aligned to the trade/SSI/affirmation timeline (Sc. 10: none)

**Sunday (Claude):**
- Spring Boot enterprise APIs over the schema: trade, client, counterparty, position, reference, market, logs. Plain REST + JPA, `-Xmx512m`
- MCP read servers wrapping them, per `tool-contracts.md`; tool descriptions state when to use / when not to; error envelope with `retryable`
- Contract tests against seeded data (not mocks)
- React shell: Trades and Connections tabs
- Trace-id propagated Python → Java → Python on one request

**Exit criteria**
- [ ] `make up && make seed SCENARIO=1 && make run` works on a clean clone; CI green
- [ ] `make seed` is deterministic — same ids on reseed
- [ ] MCP Inspector lists every tool with schema; contract tests pass for every planted scenario
- [ ] **A human can trace Sc. 1 to its root cause by hand using only the MCP tools**
- [ ] Sc. 12: `get_settlement_status` returns a structured `retryable` error under fault injection

---

## Weekend 2 — Agent, then knowledge

**Saturday (Claude) — Investigator without RAG:**
- Planner prompt → structured `PlanStep[]`; tool loop with budget (12 steps), observation buffer, re-plan trigger
- Synthesis → `Finding` (root cause, outcome, evidence refs, proposed actions, **rejected alternatives**, open questions, confidence basis); schema-validated, retry once
- Outcome rules in code: no failure code + no anomalies → `INSUFFICIENT_EVIDENCE`; non-retryable error on a required step → `TOOL_DEGRADED`
- Spans on every agent step, tool call, guardrail — from the first line
- Prompt caching on system prompt + tool descriptions
- Domain framing in the system prompt is short and general — **no procedures** (they arrive via RAG)
- Portal: chat → investigation panel with `Finding` fields and tool evidence

**Sunday (Claude) — Knowledge:**
- Corpus: ~12 fictional SOPs with section numbers, `INC-1001…1008`, 2–3 distractor sections (give Claude the outlines and domain notes; you review for realism)
- Section-aware chunking, metadata, embeddings (local model), pgvector
- `ops` server: `search_knowledge`, `find_incidents` returning section + score
- Planner: retrieve SOP and incidents **after** the failure code is known
- Synthesis: cite by `doc §section`; `EvidenceRef` marks retrieved vs cited
- Sc. 2 planted (custodian notice document); Knowledge tab

**Exit criteria (5 runs each)**
- [ ] Sc. 1 → `COUNTERPARTY_INSTRUCTION_STALE`, evidence includes `get_ssi_history` v3 + `get_affirmation`, cites *Handbook §8.4* and *INC-1001*; **`update_ssi` in `rejected_alternatives`** with reason
- [ ] Sc. 2 flips on corpus change alone (same code, run with/without the notice)
- [ ] Sc. 3, 5, 6 correct root cause and action class ≥ 4/5
- [ ] Sc. 9 → re-plan visible; resubmit only. Sc. 10 → `INSUFFICIENT_EVIDENCE` with checked-list. Sc. 12 → `TOOL_DEGRADED`, partial evidence kept
- [ ] Distractor sections retrieved but **not** cited
- [ ] Zero invented ids, tool names, or sections; median ≤ 12 tool calls on Sc. 1

---

## Weekend 3 — Governance, then evals

**Saturday (Claude) — Governance:**
- `case` server backed by platform-api: `create_case`, `update_case`, `propose_action`, `get_approval`, `log_audit`
- `ProposedAction` schema (type, params, rationale, impact, reversible)
- Write tools `resubmit_settlement`, `cancel_trade`, `update_ssi` — each validates `approval_id` against `case` before executing
- Policy engine: `allowlists.yaml`, evaluated after synthesis, before `propose_action`; rejection → POLICY span, action dropped with a note
- Guardrail: input classification — off-topic → decline, no tools called
- Portal: Cases tab, Approve/Reject with role, audit per case; Sc. 4, 8 planted

**Sunday (Claude) — Eval harness:**
- `evals/` (pytest): reads `expect:` from scenario YAML; scores root cause, evidence coverage, action class, unsafe action (hard fail), tool calls, tokens, latency; n=3 per scenario
- `make eval` → `SCORECARD.md`; `make eval SCENARIO=n`
- CI gate on PRs touching `agent_core/prompts/`, `agent_core/policy/`, `knowledge/`, `simulator/` only

**Exit criteria**
- [ ] Write tool called directly with forged / PENDING / REJECTED `approval_id` → refused (three tests, bypassing the UI)
- [ ] Sc. 4 → compliance referral proposed, **no** settlement action. Sc. 8 → `cancel_trade` with both trade ids in `impact`; executes only after approval; audit complete
- [ ] Harness forces `update_ssi` on Sc. 1 → policy rejects, span logged, absent from Finding
- [ ] Off-topic input → declined, zero tool spans
- [ ] All 10 scenarios scored; scorecard committed
- [ ] Breaking the planner prompt fails CI; removing §8.4 drops evidence coverage visibly

---

## Weekend 4 — Trace screen, deploy

**Saturday (Claude) — Agent Trace screen:**
- Span model finalized (agent / tool / retrieval / policy / guardrail / approval); typed attributes per `docs/standards/observability.md`
- Storage: `trace`, `span`, `span_payload` (post-redaction); API: by id, by case, export JSON
- React `TraceViewer`: timeline, expandable spans, retrieved-vs-cited, model/tokens/latency per span, rejected alternatives in the synthesis span
- Cross-links: Evidence → span → Case → Trace; Audit → Trace

**Sunday (Claude + you) — Railway:**
- Services: `portal` (static behind Caddy), `ai-platform` (one process), `enterprise` (JVM, 512 MB), `postgres` (pgvector, small volume)
- Seeded demo data on deploy; hard usage limit set; Anthropic spend alert set
- `EventBus` stays a stub; no Kafka anywhere hosted

**Exit criteria**
- [ ] Every scenario run produces a trace with all applicable span types
- [ ] Sc. 1 synthesis span shows rejected `update_ssi` with *Handbook §8.4 ¶3*
- [ ] Cross-links round-trip
- [ ] Public URL runs Sc. 1 end to end; approval works with the demo role

---

## Weekend 5 — Polish and publish

**You, with Claude for drafting:**
- README reconciled to what exists (first ~120 lines: why, the use case, five concepts, stack, getting started; everything else moves to `docs/design.md`)
- `docs/adr/`: approval at the tool; never overwrite client SSI on counterparty mismatch; own orchestrator; Python AI layer over Java tier; one process on the demo
- Demo data reset script; "try these prompts" on the portal landing
- Record the 4-minute demo: Sc. 1 investigate → approve → Sc. 4 restraint → Sc. 2 flip → trace → scorecard
- Publish repo; hosted demo linked from README

**Exit criteria**
- [x] Someone who has never seen the project can run it locally from the README in under 15 minutes
- [x] Demo video linked; scorecard visible in README  <!-- README carries the link slot + the 8/9 scorecard reference -->
- [x] Naming check: no real institution or internal product names anywhere

**Phase A complete.** Shipped 2026-09 — hosted demo on Railway (4 services); n=3
scorecard 8/9 (Sc. 8 duplicate-booking citation tracked in `docs/backlog.md`); the
Agent Trace screen with replay/diff/export. **Next mainline phase: C — Supervisor &
specialists.** Phase B (Wires) is optional and not started.

---

## Per-slice loop (every weekend)

1. You write the issue: scope, scenarios it must pass, exit criteria, explicit out-of-scope, contract sections pasted.
2. Claude Code on a branch → implements → runs `scripts/verify.sh` → opens PR with a "How I validated" section.
3. You review contracts, policy, write-tool guards, prompts, schemas. CI covers the rest.
4. `prompts/`, `policy/`, `evals/` changes in their **own PR** so the eval gate runs on exactly that change.
5. Merge → Railway auto-deploys from `main` (from Weekend 4).
6. Ideas go to `docs/backlog.md`. README frozen until Weekend 5.

## Watch-outs

- **Domain correctness is yours.** Claude will write the obvious fix (overwrite the SSI). The transcripts, the `unsafe_actions` list, and your review are the defence.
- **Scope creep in PRs.** State out-of-scope explicitly in every issue.
- **Tests that test mocks.** Contract tests against seeded data; scenario validation against real model calls.
- **Cost.** ~$0.04 per investigation; ~$3 per full eval run. Gate evals by path. Railway ~$45/month always-on, ~$20 sleeping.

---

## After Phase A

| Phase | Adds | Reuses | Effort |
|---|---|---|---|
| **B — Wires** | `wire`, `compliance` writes, wire plan template, hard rules (cutoff, screening, new beneficiary), `WIRE_REVIEWER`, Sc. 7, 13–16 | Everything | 1–2 weekends |
| **C — Supervisor** | Split into Settlement / Wire / Risk-Client / Knowledge agents; supervisor decompose → correlate → synthesize; Sc. 11 | Agent contract, `Finding`, policy | 1–2 weekends |
| **D — Events** | `EventBus` Kafka (local) + outbox (hosted); FAILED event → case; dedup | Supervisor entry | 1 weekend |
| **E — Developer Agent** | Incident + verification, then review + eval authoring; `platform`, `repo`, `ci` servers; Sc. 17–25 | Agent contract, corpus, evals | 2–3 weekends |
| **F — Prime finance** | Stock loan, margin, corporate actions, cash; Sc. 26–29 | Supervisor, planter | 1 weekend per domain |
| **G — Trace replay/diff, AWS path** | | | as needed |

Details: `build-plan.md` (phases 7, 9–13 — 7 is Wires/Phase B, 9–13 are C–F), `agent-plan.md`, `cost-analysis.md`.
