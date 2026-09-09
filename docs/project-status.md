# FinOps AI — Project Status

**As of:** Phase A complete (2026-09) — Weekends 1–5 shipped, live on Railway
**Phase:** A — one use case ("Why didn't trade T100245 settle?"), trade mode only
**Companion docs:** [`scope-overview.md`](scope-overview.md) is the plan (phases A–G); this
document is what is *actually built* on `main`. [`final-plan.md`](final-plan.md) is the
weekend-by-weekend Phase A plan; [`design.md`](design.md) is the architecture narrative.

---

## 1. At a glance

| Weekend | Theme | State |
|---|---|---|
| 1 | Foundation, data, tools | ✅ merged — monorepo, Compose, CI, simulator, Java enterprise, 8 MCP read servers, portal shell |
| 2 | Agent, then knowledge | ✅ merged — planner → tool loop → RAG → synthesized `Finding`; corpus + pgvector retrieval |
| 3 | Governance, then the eval harness | ✅ merged (PR #4 + PR #5) — case/approval spine, 3 write tools, policy engine, input guardrail; generic n=3 eval harness + `SCORECARD.md` |
| 4 | Trace screen, deploy | ✅ merged (PR #7 + PR #8) — span→Postgres storage, trace API (list/get/export/replay/diff), `TraceViewer` + cross-links; deployed to Railway (4 services), smoke-tested end to end |
| 5 | Polish and publish | ✅ merged — README landing page, ADRs 0003–0005, portal "try these" hint, phase flip; deploy-quality fixes (enterprise log indexes, fastembed baked into the image) |

**Current capability:** a single Investigator agent takes a `trade_id`, plans and runs
read-only MCP tool calls against the simulated bank, retrieves the relevant SOP sections
and past incidents, and returns a schema-validated `Finding` — root cause, cited
evidence, proposed remediation, and rejected alternatives. Every proposed write is
filtered through a per-agent policy allowlist, registered as a **PENDING approval on a
case**, and executed only by a write tool that re-checks the `approval_id` after a human
decision. Every step emits an OpenTelemetry span. A 9-scenario eval suite scores the
agent n=3 against planted golden cases (currently 8/9).

---

## 2. Architecture

Two tiers, two languages. The Python tier is the AI platform; the Java tier is "the
bank" and contains no AI code.

```
portal/        React + TypeScript (Vite)      — ops UI (5 tabs)
ai-platform/   Python 3.12                    — the AI platform (one ASGI process)
  platform_api/  FastAPI app, cases/approvals/audit service, settings, telemetry
  agent_core/    orchestrator loop, prompts, schemas, policy, guardrails, model routing
  mcp_servers/   9 MCP servers wrapping the Java tier (+ the in-process `case` server)
  knowledge/     corpus, chunking, embeddings, pgvector store, ingest, retrieval
  evals/         scenario harness, generic scorer, scorecard, CLI
  events/        EventBus protocol — no-op stub only in Phase A
enterprise/    Java 21 + Spring Boot 3        — simulated bank systems, plain REST + JPA
simulator/     Python                         — deterministic baseline + scenario planter
docs/          contracts, scenarios, standards, ADRs, this file
```

**Request path:** `portal` → `platform_api` (`POST /investigate`) → `agent_core.loop`
→ MCP `hub` (in-process session) → each MCP server → `HttpEnterpriseClient` → Spring
Boot → Postgres. One W3C trace id propagates the whole way.

**Data stores:** one Postgres (+pgvector). Java tier owns `trades`, `accounts`, `ssi`,
`counterparties`, `positions`, `securities`, `restrictions`, `logs`, … via Flyway
(`V1__init.sql`, `V2__phase_a_schema.sql`). Python tier owns `knowledge_chunks`
(pgvector) and `cases` / `approvals` / `audit_events` via idempotent
`CREATE TABLE IF NOT EXISTS` — **not** Flyway, to keep the Java tier AI-free.

---

## 3. Module detail

### 3.1 `enterprise/` — the simulated bank (Java 21, Spring Boot 3, JPA)

Plain REST over JPA. One controller/dtos/entities/repositories quartet per domain.
No AI code, by rule.

| Area | Endpoints | Notes |
|---|---|---|
| Trade | `GET /trades`, `GET /trades/{id}`, `GET /trades/{id}/settlement`, `GET /trades/{id}/affirmation`, `POST /trades/{id}/resubmit`, `POST /trades/{id}/cancel` | settlement status carries `failure_code` + attempt history |
| Client | `GET /clients/{id}`, `GET /accounts/{id}`, `GET /accounts/{id}/ssi`, `GET /accounts/{id}/ssi/history`, `PUT /accounts/{id}/ssi` | SSI is versioned with effective ranges |
| Counterparty | `GET /counterparties/{id}`, `GET /counterparties/{id}/ssi` | the instruction the counterparty holds *for us* |
| Position | `GET /positions`, `GET /borrow/{security}` | available vs pending-deliver quantity |
| Reference | `GET /securities/{id}`, `GET /calendar` | identifiers (ISIN/CUSIP), settlement calendar |
| Market | `GET /prices/{security}` | |
| Compliance | `GET /restrictions`, `GET /screening` | account holds (e.g. `SETTLEMENT_HOLD`) |
| Ops | `GET /logs` | settlement-engine / booking-service log lines |
| Health | `GET /health` | |

- **`FaultInjectionFilter`** — `FAULT_INJECT=<tool>:<status>` env forces an HTTP status
  on a chosen endpoint (drives Scenario 12, `TOOL_DEGRADED`).
- **Tests:** `HealthControllerTest`, `FaultInjectionTest`, `ScenarioContractTest`
  (+ `SimulatorSeeder`) — assert the API against simulator-seeded scenario data,
  Testcontainers Postgres.

### 3.2 `simulator/` — synthetic data (Python)

- **`baseline.py`** — seeded RNG population; deterministic ids. 200 securities (5 pinned
  scenario tickers: AAPL/NVDA/AMZN/GOOGL/META), a common cast (`HEDGE_FUND_101`,
  `ACC-88213`, DTC `1234`, `CP-017`), and failed trades with causes *other* than any
  planted scenario so the agent can't pattern-match.
- **`planter.py`** — one handler per `plant:` key; an unknown key is a hard error.
- **`scenario.py`** — loads a scenario YAML; `unknown_plant_keys()` and `leaks()` guards.
  **The leak test fails the build if planted data contains interpretive language**
  (`stale`, `because`, `root cause`, …) — facts only, never conclusions.
- **`cli.py`** — `python -m simulator.cli seed --scenario <n|all>`; always resets to a
  fresh baseline first.
- Scenario files: `simulator/scenarios/0NN_*.yaml` — planted facts under `plant:`,
  eval targets under `expect:` (read only by the eval harness, never by the planter).

### 3.3 `ai-platform/platform_api/` — the platform API

- **`main.py`** — one FastAPI app; `mount_all` SSE-mounts every MCP server at
  `/mcp/<name>`. Endpoints:
  - `POST /investigate {trade_id}` → `Finding`
  - `GET /connections` → every server, its tools, access tier, enterprise health
  - `GET /trades[?filters]`, `GET /trades/{id}` — proxy to the enterprise
  - `GET /knowledge?q=&k=` — corpus search for the portal
  - `GET /cases`, `GET /cases/{id}` — case list / detail (approvals + audit)
  - `POST /approvals/{id}/decide {decision, decided_by, role}` — human approve/reject
  - `GET /health`
- **`cases.py`** — the case/approval/audit service. `Backend` protocol with two
  implementations behind a facade: `MemBackend` (dicts, unit tests, no DB) and
  `SqlBackend` (Postgres). Selected by `CASES_INMEMORY=1` or `set_backend()`.
  `create_case`, `update_case`, `propose_action` (→ PENDING approval), `get_approval`,
  `decide` (APPROVED/REJECTED + who/role/when), `log_audit`, `list_cases`, `get_case`.
- **`store.py`** — SQLAlchemy Core tables `cases` / `approvals` / `audit_events` +
  idempotent `ensure_schema()` (runs on startup unless `CASES_INMEMORY`).
- **`schemas.py`** — portal response models (`TradeRow`, `ConnectionsResponse`,
  `KnowledgeHit`).
- **`settings.py`** — env-driven; model ids (`finops_strong_model`,
  `finops_cheap_model`), `database_url`, `enterprise_base_url`, OTLP endpoint.
- **`telemetry.py`** — OpenTelemetry bootstrap; one tracer, OTLP HTTP exporter, httpx
  instrumentation for trace propagation into the Java tier.
- **`openapi.json`** — committed; the portal's TS client is generated from it.

### 3.4 `ai-platform/agent_core/` — the Investigator

- **`loop.py`** — `investigate(trade_id, *, request=None, client=None, scenario_id=None)
  → Finding`. Pipeline:
  1. *(if a free-text `request` is given)* input-classification guardrail →
     off-topic ⇒ `OUT_OF_SCOPE` with **zero** tool calls.
  2. `open_session()` — one in-process MCP client over all tools.
  3. plan → tool loop (budget **12**, up to **4** planner turns; observations fed back
     to trigger a re-plan).
  4. synthesize → `Finding` (structured output, retry once).
  5. `outcomes.classify` — code rules for `TOOL_DEGRADED` / `INSUFFICIENT_EVIDENCE`.
  6. `policy.apply` — drop any proposed action off the agent's allowlist, POLICY span.
  7. `_open_case` — open a case, register each surviving action as a PENDING approval,
     stamp `case_id` + `approval_id` onto the `Finding`.
- **`prompts/`** — versioned Markdown, loaded at startup, never inlined:
  `system/domain_framing.md`, `planner/trade.md`, `synthesis/finding.md`,
  `classify/subject.md`.
- **`schemas/`** — Pydantic contracts. `finding.py`: `Finding` (subject, outcome,
  root_cause, `EvidenceRef[]`, `ProposedAction[]`, `RejectedAlternative[]`,
  open_questions, checked, degraded_tools, confidence_basis, trace_id, `case_id`,
  `planning_turns`). `plan.py`: `Plan` / `PlanStep`.
- **`reasoning/`** — `model_client.py`: provider-agnostic `ModelClient` protocol;
  `AnthropicModelClient` (prompt caching on system + tools); `FakeModelClient` for
  tests; `complete_structured[_traced]` (validate → retry once → raise).
  `model_router.py`: `Step.CLASSIFY` → cheap model, `PLAN` / `SYNTHESIZE` → strong
  model. Model names never hard-coded.
- **`policy/`** — `engine.py`: `allowed(agent, action)` from `allowlists.yaml` (loaded
  once); `apply(finding, agent)` drops off-allowlist actions, emits a `policy` span
  (`finops.policy.decision` ALLOWED/REJECTED), notes the drop in `open_questions`.
  Investigator allowlist: `resubmit_settlement`, `cancel_trade`, `update_ssi`,
  `open_compliance_referral`, `escalate`.
- **`guardrails/input_classification.py`** — one cheap-model call: is this an operations
  request at all? Span `guardrail` / `input_classification`.
- **`outcomes.py`** — pure code rules that set `TOOL_DEGRADED` (only *retryable* tool
  errors count) and `INSUFFICIENT_EVIDENCE`.
- **`spans.py`** — `span(name, type, **attrs)` context manager; every kwarg becomes a
  `finops.<key>` attribute per [`standards/observability.md`](standards/observability.md).

### 3.5 `ai-platform/mcp_servers/` — the tool layer

One package per server (`server.py` builds the `FastMCP`, `tools/__init__.py` holds the
functions whose **docstring is the exposed description**, `client.py` re-exports the
enterprise client, `models.py` holds response shapes).

| Server | Tools | Access |
|---|---|---|
| `trade` | `get_trade`, `get_settlement_status`, `find_trades`, **`resubmit_settlement`**, **`cancel_trade`** | read + **write** |
| `client` | `get_client`, `get_account`, `get_ssi`, `get_ssi_history`, **`update_ssi`** | read + **write** |
| `counterparty` | `get_counterparty`, `get_counterparty_ssi`, `get_affirmation` | read |
| `position` | `get_position`, `get_borrow_availability` | read |
| `reference` | `get_security`, `get_market_calendar` | read |
| `market` | `get_price` | read |
| `compliance` | `get_restrictions`, `get_screening_result` | read |
| `ops` | `search_logs`, `search_knowledge`, `find_incidents` | read (last two hit the corpus) |
| `case` | `create_case`, `update_case`, `propose_action`, `get_approval`, `log_audit` | **write\*** (agent-allowed bookkeeping, in-process over `platform_api.cases`) |

**28 tools** — 20 read, 3 write, 5 `write*`.

- **`_enterprise.py`** — `EnterpriseClient` protocol; `HttpEnterpriseClient` (httpx,
  traceparent propagated, **one retry on 5xx/transport** then `retryable: true`
  envelope; 4xx → `retryable: false`, 404 → `NOT_FOUND`). `@guard` turns any internal
  error into an `ErrorEnvelope` — **tools never raise into the loop**.
- **`_common.py`** — `shape` / `shape_list` (payload → contract model); **`check_approval`**
  — the approval check that lives *in the write tool* (ADR-0001): missing / not-APPROVED
  / wrong action / wrong subject → `ApprovalError`, no side effect.
- **`_fake_enterprise.py`** — records writes; drives the governance unit tests.
- **`hub.py`** — the registry. `open_session()` (in-memory MCP client for the loop +
  contract tests), `mount_all(app)` (SSE mounts), `describe()` (backs `GET /connections`).
  Per-tool `access` tier (`read` / `write` / `write*`).
- **`errors.py`** — `ErrorEnvelope{code, message, retryable, tool}`, `is_error`.

### 3.6 `ai-platform/knowledge/` — retrieval (RAG)

- **`corpus/`** — 8 SOP documents with `## §<n> — <title>` sections
  (settlement-handbook, ssi-policy, custodian-notices, reference-data-procedure,
  delivery-position-procedure, trade-exception-procedure, client-account-restrictions,
  incident-management), `incidents/INC-1001…1008.md`, and `fixtures/CN-2026-081.md`
  (a custodian notice that only exists when explicitly named — Scenario 2's flip).
- **`chunking.py`** — section-aware: one chunk per SOP `§`, whole-doc chunk per incident
  / fixture; front-matter carries the citation name.
- **`embeddings.py`** — `fastembed` `BAAI/bge-small-en-v1.5`, 384-dim ONNX (no torch).
- **`store.py`** — one pgvector table `knowledge_chunks`; `ensure_schema`, `replace_all`.
- **`ingest.py`** — `python -m knowledge.ingest [--fixtures CN-2026-081]`; idempotent
  (truncate + reload).
- **`retrieval.py`** — `search_knowledge(q, k)`, `find_incidents(q, k)`; cosine similarity.

### 3.7 `ai-platform/evals/` — the eval harness (Weekend 3, PR #5)

- **`harness.py`** — `Scenario.load` parses a scenario YAML (target = first `FAILED`
  trade; fixtures inferred from any `CN-YYYY-NNN` in `required_evidence`).
  `run_scenario` seeds once, runs the Investigator **n=3**, scores each; a scenario
  passes at **≥ ⌈2n/3⌉** runs. `flip_test` scenarios also run once with the fixture
  removed. Scenario 12 excluded by default (needs process-global `FAULT_INJECT`).
- **`scoring.py`** — one generic `score_run(finding, expect, *, tool_calls)` over every
  `expect:` key in the scenario files. **Four gates:** root cause / outcome, evidence
  coverage ≥ 0.75, action class proposed, no unsafe action (incl. the
  `resubmit_settlement_without_ssi_update` pseudo-token). Nine non-gating sub-checks
  (`followup_action`, `rejected_alternatives_must_include`, `must_not_cite`,
  `max_tool_calls`, `max_proposed_actions`, `impact_must_include`, `checked_list_min`,
  `replan_observed`, `degraded_tool`).
- **`metrics.py`** — `CountingModelClient` (exact token totals, retries included);
  `span_sink()` installs an in-memory OTel exporter to count `tool` / `retrieval` spans.
- **`scorecard.py` / `cli.py`** — `python -m evals.cli [--scenario N] [--n 3]` writes
  `evals/SCORECARD.md` and exits non-zero on any failure. `make eval [SCENARIO=n] [N=k]`.
  Without `ANTHROPIC_API_KEY` it fails loudly (never silent-green).
- **`SCORECARD.md`** — committed; latest CI run **8/9** (see §5).

### 3.8 `ai-platform/events/` — `bus.py`

`EventBus` protocol + `NoopEventBus` only. Event-driven auto-casing is Phase D.

### 3.9 `portal/` — ops UI (React 18 + TS strict + Vite)

Functional components, inline styles, no state library. API client generated from
`openapi.json` (`npm run gen:api`).

| Tab | View | Backing |
|---|---|---|
| Cases | `CasesView.tsx` — case list → detail: proposed actions with **Approve / Reject** (role `OPS_ANALYST`), audit log | `GET /cases`, `POST /approvals/{id}/decide` |
| Trades | `TradesView.tsx` — trade list → detail → **Investigate** → renders the full `Finding` | `GET /trades`, `POST /investigate` |
| Knowledge | `KnowledgeView.tsx` — corpus search | `GET /knowledge` |
| Connections | `ConnectionsView.tsx` — every MCP server, tools, access tier, enterprise health | `GET /connections` |
| Settlements / Traces / Audit | placeholders | Weekend 4+ |

---

## 4. Cross-cutting features

- **Governance (ADR-0001).** The `approval_id` check is enforced *inside each write
  tool*, never in the UI or the agent. Agents propose; humans approve
  (`POST /approvals/{id}/decide`); tools execute. Path: synthesize → `policy.apply` →
  `_open_case` (PENDING approval) → human decision → write tool re-checks →
  enterprise call + audit event.
- **Policy engine.** Every proposed action passes `agent_core/policy/allowlists.yaml`;
  off-allowlist ⇒ dropped from the `Finding` + POLICY span + `open_questions` note.
- **Domain rule (ADR-0002).** A counterparty SSI mismatch is never resolved by
  overwriting the client's SSI; the agent lists `update_ssi` as a rejected alternative
  when our instruction is current, citing Settlement Handbook §8.4 ¶3.
- **Observability.** Every agent step, tool call, retrieval, policy check, and guardrail
  is a span with typed `finops.*` attributes, from the first line of the loop. One
  W3C trace id flows portal → FastAPI → httpx → Spring Boot.
- **Structured outputs.** Every model call that must return data uses a Pydantic schema;
  invalid → retry once → raise.
- **Facts, not conclusions.** Planted simulator data may not interpret; the leak test
  enforces it.
- **Input guardrail.** Off-topic requests are declined before any tool runs.

---

## 5. Scenarios & current scorecard

Ten planted golden scenarios ([`eval-scenarios.md`](eval-scenarios.md)); each = facts +
ideal transcript + `expect:` block. Latest CI n=3 run — **8/9** (Scenario 12 excluded,
needs process-global fault injection):

| # | Scenario | Root cause | Result |
|---|---|---|---|
| 1 | counterparty_ssi_stale | `COUNTERPARTY_INSTRUCTION_STALE` | ✅ 3/3 |
| 2 | client_ssi_stale (flips on corpus fixture) | `CLIENT_SSI_STALE` | ✅ 3/3, flip ✓ |
| 3 | security_reference_error | `SECURITY_MASTER_INCONSISTENT` | ✅ 3/3 |
| 4 | account_restricted | `COMPLIANCE_RESTRICTION` | ✅ 3/3 |
| 5 | insufficient_position | `DELIVERY_SHORTFALL` | ✅ 3/3 |
| 6 | counterparty_instruction_expired | `COUNTERPARTY_INSTRUCTION_EXPIRED` | ✅ 2/3 |
| 8 | duplicate_trade | `DUPLICATE_BOOKING` | ❌ 0–1/3 — deterministically 67% evidence (see backlog) |
| 9 | already_remediated | `REMEDIATED_PENDING_RESUBMIT` | ✅ 3/3 |
| 10 | no_evidence | outcome `INSUFFICIENT_EVIDENCE` | ✅ 2/3 |
| 12 | tool_outage | outcome `TOOL_DEGRADED` | covered by `tests/test_loop.py` |

---

## 6. Testing & CI

- **`scripts/verify.sh`** (and `verify.yml`): `ruff format --check` + `ruff check` +
  `mypy --strict` (ai-platform + simulator), `pytest -m "not eval and not contract"`
  (~43 unit tests), `mvn test` (enterprise), portal `lint` + `tsc`. Then a real-stack
  block: build + start the enterprise, seed all scenarios, ingest the corpus, run
  `pytest -m contract` (~15 tests, incl. the governance propose→approve→execute→audit
  round-trip).
- **`eval.yml`**: **`workflow_dispatch` only** (n / scenario inputs) — the `pull_request`
  path trigger was removed (PR #13), and full sweeps are paused for Phase C and later
  during the build (`backlog.md`). Real Claude calls (~$2 per n=3 run). Uploads
  `SCORECARD.md` as an artifact. Needs the repo secret `ANTHROPIC_API_KEY`. The
  `SCORECARD.md` on record is the Phase A 8/9.
- **Local constraints:** Docker Desktop is broken on the dev machine, and the corporate
  TLS proxy blocks fastembed's model download — so the DB-backed simulator suite, the
  knowledge/contract tests, and the eval suite are **CI-only** locally. `uv` needs
  `--native-tls`.

---

## 7. Not built yet

**Phase A remaining (Weekends 4–5):**
- Trace storage (`trace` / `span` / `span_payload`) + API (by id, by case, export JSON)
- React `TraceViewer` (timeline, expandable spans, retrieved-vs-cited, model/tokens/
  latency, rejected alternatives) + cross-links Evidence → span → Case → Trace
- Railway deploy (portal / ai-platform / enterprise / postgres), seeded demo data,
  usage limit + spend alert
- Polish, README, demo script

**Mainline after A:** ~~C supervisor + specialist agents~~ (done 2026-09-09, PRs #14/#16 —
Supervisor + Settlement/Risk-Client/Knowledge specialists, per-agent allowlists, client
Scenario 11) → **D event-driven auto-casing** (next) → E Developer Agent → F prime-finance
domains → G hardening. **Wires (B) is an optional module** — depends only on A, nothing in
C–G depends on it. See [`phase-breakdown.md`](phase-breakdown.md).

---

## 8. Known gaps / backlog highlights

Full list in [`backlog.md`](backlog.md). Notable:

- **Scenario 8 evidence citation** — the agent reaches the right cause and action for a
  duplicate booking but deterministically cites only 2 of 3 required evidence refs
  (misses `Trade Exception Procedure §6.1`). A synthesis branch + planner step didn't
  move it; the fix is in retrieval. `make eval SCENARIO=8 N=3` (the CLI dumps the
  failing `Finding`).
- **`finops_strong_model = "claude-sonnet-4-6"`** — a valid previous-gen id; revisit if
  the scorecard shows the strong model is the weak link.
- **MCP split mode** — `AI_PLATFORM_SPLIT=1` is wired but Compose has no per-server
  services; add them only when a split deployment is actually exercised.

---

## 9. Key reference docs

| Doc | What |
|---|---|
| [`phase-breakdown.md`](phase-breakdown.md) | canonical full-scope reference, all phases |
| [`final-plan.md`](final-plan.md) | Phase A, weekend by weekend |
| [`scope-overview.md`](scope-overview.md) | digest of the whole doc set |
| [`design.md`](design.md) | architecture narrative |
| [`tool-contracts.md`](tool-contracts.md) | every MCP tool: signature, access, description |
| [`eval-scenarios.md`](eval-scenarios.md) | the 10 scenarios + `expect:` scoring spec |
| [`standards/`](standards/) | `coding.md`, `observability.md`, `security.md` |
| [`adr/`](adr/) | 0001 approval-at-the-tool · 0002 never overwrite client SSI on a counterparty mismatch |
