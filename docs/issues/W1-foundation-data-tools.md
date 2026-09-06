# W1 — Foundation, simulator, enterprise APIs, MCP read tools

Read first: `CLAUDE.md`, `docs/final-plan.md` (Weekend 1), `docs/tool-contracts.md`, `docs/eval-scenarios.md`, `docs/standards/*`.

Split into three PRs, in order. Each PR: `scripts/verify.sh` green, "How I validated" in the body.

---

## PR 1 — Repo foundation

**Deliver**
- Monorepo layout per `CLAUDE.md`. Python workspace with `uv` (`ai-platform/` containing `platform_api/`, `agent_core/`, `mcp_servers/`, `knowledge/`, `evals/`; and `simulator/`), Maven project in `enterprise/`, Vite + React + TS in `portal/`.
- `docker-compose.yml`: `postgres` (pgvector image, volume), `enterprise`, `ai-platform`, `portal`. Compose flag `AI_PLATFORM_SPLIT=1` runs platform-api and each MCP server as separate containers; default runs them as one ASGI app.
- `Makefile`: `up`, `down`, `seed SCENARIO=<n|all>`, `run`, `portal`, `test`, `eval [SCENARIO=n]`, `verify`.
- `scripts/verify.sh`: ruff, mypy --strict, pytest (non-eval), mvn test, portal lint + tsc.
- CI (GitHub Actions): verify on every PR; eval job **only** on paths `ai-platform/agent_core/prompts/**`, `ai-platform/agent_core/policy/**`, `ai-platform/knowledge/**`, `simulator/**` (job may be a stub that skips until W3).
- `agent_core/reasoning/model_client.py`: `ModelClient` protocol with `complete(messages, tools=None, schema=None) -> ModelResponse`; `AnthropicModelClient` (prompt caching on system + tools); `FakeModelClient` for tests. `model_router.py` with `classify → cheap`, `plan|synthesize → strong`, from settings.
- OTel bootstrap in both runtimes; W3C `traceparent` propagation FastAPI → httpx → Spring Boot; Jaeger in compose.
- `EventBus` protocol with a no-op implementation only.

**Out of scope:** any agent logic, any MCP tool, any UI beyond a placeholder page.

**Validate**
- [ ] Clean clone: `make up && make run` starts everything; `curl` to platform-api health and enterprise health both OK
- [ ] `make verify` green locally and in CI
- [ ] A test calls `AnthropicModelClient.complete` with a trivial schema and gets a validated object back (marked `eval`, skipped in CI)
- [ ] A request through platform-api → enterprise shows the same trace id in both logs and in Jaeger

---

## PR 2 — Simulator and enterprise APIs

**Deliver**
- Postgres schema (Flyway in `enterprise/`): clients, accounts, ssi_versions, securities, market_calendar, prices, counterparties, counterparty_ssi, trades, settlement_attempts, affirmations, positions, borrow_availability, restrictions, screening_results, app_logs, incidents (metadata only; text lives in knowledge/).
- `simulator/` (Python): 
  - `baseline.py` — seeded RNG; ~50 clients, ~80 accounts each with a current SSI and 1–3 prior versions, ~200 securities with valid ISIN/CUSIP/ticker, 30 business days of prices, ~20 counterparties with SSIs and `valid_to`, ~500 trades over 10 business days with ~95% SETTLED, **at least 8 FAILED trades for reasons other than the planted scenarios** (spread across failure codes), positions for every account × held security, borrow availability, ~20k app_log lines of realistic noise across services `settlement-engine`, `booking-service`, `reference-service`, `position-service`, `affirmation-gateway`.
  - `planter.py` — loads `simulator/scenarios/*.yaml`; `plant:` keyed by domain (`accounts.ssi`, `counterparties.ssi`, `trades`, `affirmations`, `positions`, `borrow`, `restrictions`, `securities`, `logs`, `incidents`, `corpus_fixtures`); one handler per key; unknown key = error. `expect:` is ignored by the planter (evals read it).
  - Scenario files for 1, 3, 5, 6, 8, 9, 10, 12 exactly per `docs/eval-scenarios.md`, each with its corroborating log lines (timestamps aligned to the scenario's own timeline). Sc. 2 file too, but its `corpus_fixtures` are consumed in W2.
  - HF101 must also have **healthy settled trades** in the baseline.
  - Fault injection: `enterprise` reads `FAULT_INJECT=trade.settlement_status:503` and returns 503 for that endpoint (Sc. 12).
- `enterprise/` Spring Boot REST over the schema: `/trades/{id}`, `/trades/{id}/settlement`, `/trades?client=&account=&status=&security=&tradeDate=&settleDate=`, `/clients/{id}`, `/accounts/{id}`, `/accounts/{id}/ssi`, `/accounts/{id}/ssi/history`, `/counterparties/{id}`, `/counterparties/{id}/ssi`, `/trades/{id}/affirmation`, `/positions?account=&security=`, `/borrow/{security}`, `/securities/{id}`, `/calendar?date=&market=`, `/prices/{security}`, `/restrictions?account=`, `/screening?client=`, `/logs?q=&tradeId=&system=&from=&to=`. Plus write endpoints `/trades/{id}/resubmit`, `/trades/{id}/cancel`, `/accounts/{id}/ssi` (PUT) — **these take no approval logic; the MCP write tools own that in W3**.

**Out of scope:** MCP servers, agent, knowledge ingestion.

**Validate**
- [ ] `make seed SCENARIO=1` twice → identical ids and timestamps
- [ ] `make seed SCENARIO=all` plants every scenario without collisions (distinct trade ids per `docs/eval-scenarios.md`)
- [ ] Integration tests (Testcontainers): every endpoint returns the planted facts for every scenario in the doc — assert the specific values (e.g. Sc. 1 affirmation cpty_dtc == "5678")
- [ ] Baseline check test: ≥ 8 non-scenario FAILED trades; HF101 has ≥ 5 SETTLED trades; ≥ 3 SSI versions exist for ACC-88213 after Sc. 1 plant
- [ ] **Leak test:** planted records, log messages, and corpus fixture text contain no interpretive language (`stale`, `wrong side`, `never picked up`, `root cause`, `because`, `should have`). Scenario YAML `plant:` blocks are facts only; anything explanatory belongs in `expect:` or the transcript
- [ ] Fault injection returns 503 for the target endpoint only

---

## PR 3 — MCP read servers, Connections page, walking skeleton

**Deliver**
- `mcp_servers/{trade,client,counterparty,position,reference,market,compliance,ops}` implementing **read** tools exactly per `docs/tool-contracts.md` (write tools and `case` server are W3). Tool docstring = exposed description text from the contract. Common `ErrorEnvelope`; HTTP 5xx from enterprise → `retryable: true`; 4xx → `retryable: false`. One retry on retryable inside the tool.
- `ops.search_logs` only in this PR (`search_knowledge`, `find_incidents` are W2 — register them as tools that return `NotYetAvailable` so tool discovery shape is stable).
- Servers mounted into the single ASGI app; discoverable via MCP client; also runnable separately under the split flag.
- Contract tests: for each tool, call through an MCP client against seeded scenario data and assert output schema + planted values.
- `portal/`: Trades tab (list + detail from platform-api proxy), Connections tab (servers, tools, access tier, last health check).
- **Walking skeleton**: `agent_core/skeleton.py` — no planning: given a trade id, calls `get_trade` via MCP and returns a minimal `Finding{subject, outcome: SKELETON, evidence:[tool result id]}`; platform-api endpoint `POST /investigate` calls it; portal shows the result. This proves the whole pipeline; it is replaced in W2.

**Out of scope:** planner, synthesis, prompts, knowledge, approvals.

**Validate**
- [ ] MCP Inspector (or `mcp` CLI) lists every read tool with schema for every server
- [ ] Contract tests pass for every planted scenario
- [ ] Swap test: point `trade` server at an in-memory fake of the enterprise API via env; contract tests for `trade` still pass unchanged
- [ ] Sc. 12: `get_settlement_status` under fault injection returns `ErrorEnvelope{retryable: true}` after one retry, no exception
- [ ] Walking skeleton: portal → `/investigate` → MCP → enterprise → back; one trace id visible end to end in Jaeger
- [ ] **Manual:** using only the MCP tools from the Inspector, trace Sc. 1 to its root cause by hand following the ideal transcript. Record the tool sequence in the PR body.
