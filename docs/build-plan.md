# FinOps AI — Phased Build Plan

Each phase has one goal, a concrete build list, and **exit criteria** that must pass before the next phase starts. Every phase ends demo-able — you can stop after any of them and have something to show.

Effort assumes ~8–10 focused hours/week alongside a full-time job. Adjust to your pace; the ordering matters more than the dates.

> **Superseded, Phases 0–6 and 8:** absorbed into Phase A's weekend-by-weekend plan in `docs/final-plan.md` — read that instead; don't treat the sections below as open work. **Still current:** Phase 7 (Wires → `docs/phase-breakdown.md` Phase B), Phase 9 (Supervisor → Phase C), Phase 10 (Events → Phase D), Phases 11–12 (Developer Agent → Phase E), Phase 13 (Prime finance → Phase F). `docs/phase-breakdown.md` is the up-to-date at-a-glance view across all phases.

**Three milestones**

| Milestone | After phase | What you can show |
|---|---|---|
| **M1 — Investigator works** | 4 | "Why didn't this trade settle?" with real tools and cited evidence |
| **M2 — Demo-ready** | 7 | Both killer scenarios, approval gate, eval scorecard, trace screen. Publish here. |
| **M3 — Platform** | 11 | Supervisor, event-driven, Developer Agent. The full README story. |

Phases 12–13 are extensions. Don't plan them until M2 ships.

---

## Phase 0 — Foundation
**Goal:** a repo that builds, runs, and tests from one command.  **~1 week**

Build
- Monorepo skeleton: `portal/`, `platform-api/`, `agent-core/`, `mcp-servers/`, `knowledge/`, `enterprise/`, `simulator/`, `evals/`, `observability/`, `docs/`
- Docker Compose: Postgres + pgvector, Redpanda (Kafka), placeholder services
- Python workspace (uv or Poetry, Python 3.12, ruff + mypy + pytest); Spring Boot parent POM (Java 21) for `enterprise/`; React + TypeScript + Vite for `portal/`
- CI: build, unit tests, lint on every PR — both runtimes
- `Makefile` targets: `up`, `seed`, `run`, `portal`, `eval` (stubs OK)
- LLM provider wired: one `ModelClient` abstraction (Anthropic API behind it; Bedrock optional), one "hello" call working end to end
- **Process layout decided now**: `ai-platform` is one ASGI app that mounts the FastAPI platform API and every MCP server as sub-apps; locally Compose can still run them separately via a flag. Retrofitting consolidation later is expensive
- `EventBus` interface with two implementations stubbed: Kafka (local) and Postgres outbox (hosted demo)
- Cost guard: eval suite runs in CI **only** on PRs touching `agent-core/prompts/`, `agent-core/policy/`, `knowledge/`, or `simulator/`
- `docs/tool-contracts.md`, `docs/eval-scenarios.md` copied from design

Exit criteria
- [ ] `git clone && make up && make run` works on a clean machine
- [ ] CI green on an empty PR
- [ ] One model call round-trips through `agent-core` with a trace-id logged

---

## Phase 1 — Simulator and data model
**Goal:** a fictional broker/dealer with planted, reproducible failures.  **~2 weeks**

Build
- Postgres schema: clients, accounts, SSIs (with history), securities, market calendar, prices, trades, settlement attempts, affirmations, positions, borrow availability, logs
- Synthetic data generator: baseline population (~50 clients, ~500 trades, ~2,000 positions, ~20k log lines)
- **Scenario planter**: YAML per scenario → mutates baseline to plant the causal chain (scenarios 1, 2, 3, 5, 6, 8, 9, 10, 12)
- Simulated enterprise REST APIs over the schema (Spring Boot, `enterprise/`): trade, client, counterparty, position, reference, market, logs
- Generator and scenario planter in Python (`simulator/`), writing directly to Postgres
- Scenario 12 needs a fault-injection switch on the settlement API (return 503)

Exit criteria
- [ ] `make seed SCENARIO=1` produces exactly the T100245 chain in the README; same for each listed scenario
- [ ] `make seed SCENARIO=all` is deterministic (seeded RNG) — reseeding yields identical ids
- [ ] API integration tests: every endpoint returns the planted data for every scenario
- [ ] A human can trace scenario 1 to its root cause by hand using only the APIs — if you can't, the agent can't

---

## Phase 2 — MCP read tools
**Goal:** agents discover capabilities; nothing is hard-coded.  **~1.5 weeks**

Build
- MCP servers (MCP Python SDK) wrapping the Spring Boot APIs: `trade-server`, `client-server`, `counterparty-server`, `position-server`, `reference-server`, `market-server`, `ops-server` (logs only — knowledge comes in Phase 4)
- Read tools per `docs/tool-contracts.md`; every tool declares `access: read`
- Common error envelope, timeouts, structured responses
- Contract tests: schema of every tool's output
- Minimal **Connections** page in the portal: servers, tools, access tier, last-seen

Exit criteria
- [ ] MCP Inspector (or equivalent client) lists every tool with its schema
- [ ] Contract tests pass for every scenario's data
- [ ] **Swap test**: replace `trade-server`'s backing implementation (e.g. in-memory vs. Postgres) — client code unchanged, tests pass
- [ ] Scenario 12: `get_settlement_status` returns a structured error, not an exception

---

## Phase 3 — Single investigator agent (killer scenario 1, without RAG)
**Goal:** "Investigate T100245" produces a correct, evidence-backed finding.  **~2 weeks**

Build
- `agent-core` (Python): planner prompt, tool-calling loop (max steps, budget), MCP client with tool discovery — your own orchestrator, no framework
- `InvestigationResult` structured output schema + validation
- `Finding` includes: root cause, evidence refs, proposed action class, rejected alternatives, open questions
- Explicit `INSUFFICIENT_EVIDENCE` and `TOOL_DEGRADED` outcomes
- Portal: chat input, investigation panel, evidence list (tool evidence only for now)
- Basic span logging to Postgres (full Trace screen is Phase 8) — start emitting spans **now**, or you'll retrofit later

Exit criteria
- [ ] Scenarios 1, 3, 5, 6 → correct root cause and correct action class, 5 runs each, ≥ 4/5
- [ ] Scenario 1 finding lists `update_ssi` as a **rejected** alternative
- [ ] Scenario 9 → agent notices remediation and proposes resubmit only
- [ ] Scenario 10 → `INSUFFICIENT_EVIDENCE`, with the list of what was checked
- [ ] Scenario 12 → partial finding, degraded tool named
- [ ] No hallucinated tool names or ids across all runs (grep the spans)

**M1 reached** — you can demo the core loop.

---

## Phase 4 — Knowledge (RAG)
**Goal:** retrieval that changes answers and cites sections.  **~2 weeks**

Build
- Corpus: 20–30 fictional documents (settlement handbook, SSI policy, wire guide, trade exception procedure, incident management, etc.) — write them with section numbers; the Developer Agent can draft later, for now write or generate them yourself
- Incident corpus: INC-1001…INC-1010 with symptom / root cause / resolution
- Ingestion: section-aware chunking, metadata (doc, section, title), embeddings → pgvector
- `ops-server`: `search_knowledge`, `find_incidents` with section-level results and scores
- Planner updated to retrieve SOPs and incidents as evidence
- Portal: **Knowledge** tab — direct search over the corpus; evidence items deep-link to the section

Exit criteria
- [ ] **Scenario 2 flips**: without the custodian notice the agent blames the counterparty; with it, the agent finds our SSI stale — same code, different corpus
- [ ] Scenario 1 evidence cites *Settlement Handbook §8.4* and *INC-1001*
- [ ] Retrieval check: 20 hand-written queries → expected section in top 3 for ≥ 17
- [ ] Trace shows retrieved-vs-cited distinction per query

---

## Phase 5 — Governance: cases, approvals, write tools, policy, audit
**Goal:** the agent proposes; a human decides; the tool enforces it.  **~2 weeks**

Build
- `case-server` (MCP) backed by `platform-api` (FastAPI): `create_case`, `update_case`, `propose_action`, `get_approval`, `log_audit`
- Write tools: `resubmit_settlement`, `cancel_trade`, `update_ssi` — each validates `approval_id` against `case-server` before executing
- `agent-core/policy/`: per-agent action allowlists, enforced in code; rejection emits a POLICY span
- Portal: Cases tab, Approve/Reject with role, audit log per case
- Roles: `OPS_ANALYST`, `WIRE_REVIEWER`, `CHANGE_APPROVER` (simple, but real) — enforced in `platform-api`

Exit criteria
- [ ] Calling any write tool without a valid, APPROVED `approval_id` fails — proven by a test that bypasses the UI entirely
- [ ] Scenario 4 → agent routes to compliance, proposes **no** fix
- [ ] Scenario 8 → `cancel_trade` proposed, approved, executed, audited
- [ ] Forcing the agent to propose an out-of-scope action (test harness) → policy rejection logged, nothing executed
- [ ] Audit for a closed case shows: who asked, what the agent found, what it proposed, who approved, when, what executed

---

## Phase 6 — Eval harness
**Goal:** a scorecard that tells you when you've broken something.  **~1 week**

Build
- `evals/` (pytest): scenario definitions (expected root cause, required evidence, expected action class, unsafe actions), runner, scorer
- Scoring: root cause ✓/✗, evidence coverage n/m, action class ✓/✗, unsafe action = hard fail, tool calls, tokens, latency
- `make eval` → `SCORECARD.md` regenerated; CI runs the suite on PRs touching `agent-core/`, `knowledge/`, or `simulator/`
- Multiple runs per scenario (n=3) to surface nondeterminism

Exit criteria
- [ ] Scenarios 1–6, 8–10, 12 scored; scorecard committed
- [ ] Deliberately break the planner prompt → CI fails on the eval gate
- [ ] Deliberately remove *Handbook §8.4* from the corpus → Scenario 1 evidence coverage drops and it's visible

---

## Phase 7 — Wires (killer scenario 2)
**Goal:** the second killer scenario, and the maker–checker control.  **~2 weeks**

Build
- Schema + simulator: wires, holds, reviewer queue, standing wire instructions, cutoffs, screening results
- `wire-server` (read + `route_to_reviewer`, `add_standing_instruction`, `reschedule_value_date`), `compliance-server` (read + `open_compliance_referral`)
- Wire investigation prompts/plan; cutoff as a hard rule in code, not a model judgment
- `WIRE_REVIEWER` release flow in the portal; audit message posted to the wire record; wire exception report
- Corpus: wire processing guide, INC-2001…2005
- Scenarios 7, 13, 14, 15, 16 planted and in the eval suite

Exit criteria
- [ ] Scenario 13 → routed to reviewer with review packet and cutoff warning; `release_wire` does not exist as an agent tool (test asserts it)
- [ ] Scenario 14 → reschedule proposed, never a forced release
- [ ] Scenario 15 → screening hit: agent freezes, refers to compliance, proposes nothing else
- [ ] Scorecard now covers 16 scenarios

**M2 reached — demo-ready.** Record the 5-minute demo. Publish the repo. Reconcile the README against what exists. **Deploy to Railway now** (consolidated layout: `portal`, `ai-platform`, `enterprise`, `postgres`); set a hard usage limit; sleep services between demos if you don't need it always-on.

---

## Phase 8 — Agent Trace screen
**Goal:** observability the analyst uses.  **~1.5 weeks**

Build
- Finalize span model: agent / tool / retrieval / policy / guardrail / approval / delegation, typed OTel attributes
- Storage: `trace`, `span`, `span_payload` (post-redaction)
- `platform-api/trace`: get by id, by case; export JSON
- Portal (React): `TraceViewer` — virtualised timeline, expandable spans, retrieved-vs-cited, cross-links from Evidence and Audit
- OTel: Python SDK in agents/platform-api, Java agent in `enterprise/` — one trace-id propagated across both
- Guardrail spans: input classification, PII scrub counts, schema validation
- Model routing: cheap model for classify, strong for synthesize — visible per span

Exit criteria
- [ ] Every scenario run produces a complete trace with all span types present where applicable
- [ ] Scenario 1 trace shows the rejected `update_ssi` alternative with its citation
- [ ] Cross-links round-trip: Evidence → span → Case → Trace
- [ ] Replay: rerun Scenario 9's question against remediated data, both traces viewable
- [ ] Deferred to 8.1: trace diff

---

## Phase 9 — Supervisor and specialists
**Goal:** delegation across a client's exceptions.  **~2 weeks**

Build
- Split the investigator into `SettlementAgent`, `WireAgent`, `RiskClientAgent`, `KnowledgeAgent`, each with its own tool scope and allowlist
- `SupervisorAgent`: classify → decompose → parallel sub-tasks → correlate findings → synthesize → case
- Sub-task and `Finding` schemas; correlation by shared cause; budgets per specialist
- Scenario 11 planted (3 settlement fails + 1 held wire for HF101)

Exit criteria
- [ ] Scenario 11 → two distinct causes, three trades grouped under one action, wire handled separately
- [ ] All Phase 3–7 scenarios still pass with the split agents (no regression)
- [ ] Trace shows delegation spans and each specialist's `Finding`
- [ ] A specialist returning `INSUFFICIENT_EVIDENCE` surfaces in the synthesis, not swallowed

---

## Phase 10 — Event-driven investigations
**Goal:** the platform reacts without being asked.  **~1 week**

Build
- `EventBus` topics: `settlement.events`, `wire.events`; simulator publishes FAILED / HELD events — Kafka locally, Postgres outbox on Railway, same consumer code
- Consumer opens a case and starts an investigation; dedup so a flapping trade doesn't spawn ten cases
- Portal: cases appear with source = `event`

Exit criteria
- [ ] Publish one FAILED event → case + investigation + proposed action appear with no user prompt
- [ ] Publish the same event twice → one case
- [ ] Trace shows the event as the trigger span

---

## Phase 11 — Developer Agent: incident + verification
**Goal:** when the platform is the problem.  **~2 weeks**

Build
- `platform-server`: `get_service_health`, `get_job_runs`, `get_deployments`, `diff_config`, `get_topic_lag`; writes `rerun_job`, `replay_message`, `open_change_ticket` (approval-gated, `CHANGE_APPROVER` role)
- `repo-server`: `get_source`, `open_pull_request` (draft only) — GitHub's MCP server or a thin wrapper
- Simulated platform faults: failed job + config diff + queue backlog (scenario 17), intentional change with release note in corpus (18)
- Supervisor hands off to Developer Agent on business `INSUFFICIENT_EVIDENCE`
- Verification workflow: expectation → re-check → delta → hand-off residual → write incident back (scenarios 22–24)

Exit criteria
- [ ] Scenario 17 → failed job, config diff, blast radius (47 trades), revert + rerun + draft PR proposed
- [ ] Scenario 18 → fix-forward, not revert
- [ ] Scenario 23 → 46/47 verified, T100301 handed to Settlement Agent, INC-3012 retrievable afterwards
- [ ] Scenario 24 → verification reports failure; no further autonomous remediation
- [ ] Deploy/merge/approve tools do not exist (test asserts)

**M3 reached — the full platform story.** Second README reconciliation.

---

## Phase 12 — Developer Agent: PR review + eval authoring
**Goal:** the engineering agent reviews and extends the platform's own safety net.  **~2 weeks**

Build
- `ci-server`: `run_static_analysis`, `run_security_scan`, `get_test_coverage`, `run_tests`, `run_eval`
- Standards corpus in `docs/standards/` indexed alongside ops KB; diff classification → targeted retrieval
- Platform-specific security checks (approval_id on write tools, allowlist coverage, PII scrub before model calls)
- Structured `Review` output; `post_review` (comments only); CI webhook trigger
- Eval authoring workflow: scenario YAML + planter + corpus fixture + baseline run → draft PR
- Scenarios 19, 20, 21, 25

Exit criteria
- [ ] PR with a write tool missing `approval_id` → BLOCKER with suggested patch
- [ ] PR changing a planted fixture → the affected scenario re-runs in review
- [ ] Agent-drafted scenario 25 → fails on first run (correct baseline), reviewed by Workflow 2, merged by a human

---

## Phase 13 — Prime finance domains (v3)
**Goal:** recognisably prime finance.  **~1.5 weeks per domain**

Order: stock loan → margin & collateral → corporate actions → cash. Each: schema + planter, MCP server, agent scope/allowlist, corpus slice, 1–2 scenarios (26–29), eval entries.

Exit criteria per domain
- [ ] Its scenarios pass in the eval suite
- [ ] No regression on the existing scorecard
- [ ] Supervisor routes to it correctly in a mixed-client investigation

---

## Working rules

1. **Exit criteria are gates, not suggestions.** If a phase's boxes aren't ticked, the next phase's work is debt.
2. **Every phase ends with three things:** the scorecard regenerated, a 60-second screen recording of what's new, and a README reconciliation (only for what changed).
3. **Emit spans from Phase 3.** The Trace screen is Phase 8, but retrofitting instrumentation is the most expensive mistake in this plan.
4. **Write the scenario before the feature.** Each phase's exit criteria reference scenarios; plant them first, then build until they pass.
5. **Cut list, in order, if time runs short:** trace diff → Phase 13 → Phase 12 → Phase 10. Never cut Phase 5 (governance) or Phase 6 (evals) — they're the differentiator.
6. **Freeze the README between reconciliations.** Ideas go to `docs/backlog.md`.
7. **Watch the two cost levers:** eval-suite trigger scope (CI) and resident containers (Railway). Everything else is noise at this scale.

---

## Summary

| Phase | Goal | Weeks | Cumulative | Scenarios |
|---|---|---|---|---|
| 0 | Foundation | 1 | 1 | — |
| 1 | Simulator | 2 | 3 | planted |
| 2 | MCP read tools | 1.5 | 4.5 | — |
| 3 | Single agent | 2 | 6.5 | 1,3,5,6,9,10,12 |
| 4 | RAG | 2 | 8.5 | 2 |
| 5 | Governance | 2 | 10.5 | 4,8 |
| 6 | Eval harness | 1 | 11.5 | scorecard |
| 7 | Wires | 2 | 13.5 | 7,13–16 |
| 8 | Trace screen | 1.5 | 15 | — |
| 9 | Supervisor | 2 | 17 | 11 |
| 10 | Event-driven | 1 | 18 | — |
| 11 | Dev Agent incident/verify | 2 | 20 | 17,18,22–24 |
| 12 | Dev Agent review/authoring | 2 | 22 | 19–21,25 |
| 13 | Prime finance | 6 | 28 | 26–29 |

M1 at ~6.5 weeks · **M2 (publish) at ~13.5 weeks** · M3 at ~20 weeks.
