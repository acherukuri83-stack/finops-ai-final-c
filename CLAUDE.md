# FinOps AI — project brief for Claude Code

Agentic trade & settlement operations platform on a fully simulated broker/dealer. **No real firm's data, code, documents, or naming.** Everything is fictional.

## Current phase: mainline A–G complete + the optional Wires module

Every mainline phase A–G has a merged core slice **and** its deferred depth — shipped, or closed-as-accepted with a rationale in `docs/backlog.md` (search `Closed (2026-09-09)`). The optional **Wires** module is built: Wire specialist + `wire` MCP server + maker/checker/cutoff/screening hard rules, seeded Postgres + a `simulator` planter, Sc. 7 / 13–16 (`subject: wire`) ready for a sweep, `supervisor._held_wires` discovery. What remains is not deferred depth: the end-of-project `workflow_dispatch` eval sweep + refreshed `evals/SCORECARD.md` (owner decision), a wire corpus, and the portal `WIRE_REVIEWER` release flow. New work starts from a fresh product ask.

**Depth landed in this pass:**
- **E verification mode** — `developer.verify_change(ticket_id)`: apply → re-check job/lag → residual trade to Settlement (`sub_finding`) → write retrievable `INC-3xxx`; a failed fix reports FAILED, proposes nothing. `POST /verify`, `platform.get_incident`.
- **E PR-review mode** — `repo` + `ci` fixture servers, `Review` schema, `agent_core/review.py` (surface classification + deterministic checks + platform hard rules as code: write tool w/o `approval_id` → BLOCKER `security.md §4.1`; new `action_type` off every allowlist → MAJOR §5; PII into a model call → BLOCKER §7; `authored_by: agent` scenario → needs a human). `POST /review`. No `approve_pr` / `merge_pr` tool.
- **E eval-authoring mode** — `agent_core/eval_authoring.py::author_scenario(failure_code)`: a template per known failure code → a planted-chain YAML + `expect:` block + baseline, labelled `authored_by: agent` (which review mode blocks from merge without a human). `POST /author-scenario`. Deterministic; the model-driven "from any SOP section" version is a follow-up.
- **F Margin domain** — `margin` server + `MARGIN` spec + `agent_core/margin.py::investigate_margin_call`; **meet-vs-close-out hard rule in code** (`_enforce_call_window` on `due_by`). `POST /investigate {margin_call_id}`; Supervisor `margin` sub-task.
- **F CorpActions domain** — `corpactions` server + `CORPACTIONS` spec + `agent_core/corpactions.py::investigate_ca_event`; **record-date hard rules in code** (`_enforce_record_date`): a cash dividend on a lent-out slice → `raise_claim` on the borrower; an elective event past its deadline → `escalate_ca`. `POST /corpaction {event_id, account_id}`; Supervisor `corpactions` sub-task.
- **F Cash domain** — `cash` server + `CASH` spec + `agent_core/cash.py::investigate_cash_break`; **fund-vs-escalate hard rule in code** (`_enforce_funding_cutoff` on the currency `funding_cutoff`). `POST /investigate {cash_break_id}`; Supervisor `cash` sub-task. **All four prime-finance domains now shipped** (stockloan, margin, corpactions, cash).
- **G obs** — `schema_validation` guardrail span (from `complete_structured_traced`) + `finops.tool.retries` (from `_enterprise.last_retries()`).
- **Sc. 30 mechanism** — Supervisor correlates `settlement` + `stockloan` sub-findings into one mixed-domain client answer (unit-tested).
- **F Prime Finance portal tab** — `portal/src/PrimeFinanceView.tsx`: one tab, a domain selector (Stock Loan / Margin / Cash / Corp Actions) → the right endpoint → the shared `Finding` renderer. `api.primeFinance` / `api.corpaction`.
- **E bounded Supervisor→Developer hand-off** — `supervisor._recommend_incident_review`: all sub-findings `INSUFFICIENT_EVIDENCE` → an `open_questions` note recommending `POST /diagnose`. Recommendation only, never auto-dispatch.
- **C Knowledge specialist wired** — `agents/base.py::run_knowledge` (degenerate: fixed retrieval, no planner, no model call, proposes nothing) → cited `evidence` + relevance notes in `checked`, `subject.type = "knowledge"`. Supervisor `_decompose` / `_dispatch` route it; `_business()` keeps it out of outcome reconciliation and the incident recommendation. `decompose.md` rewritten to cover all seven agents (also fixed the `margin` / `corpactions` / `cash` prompt gap).
- **F prime-finance data seeded** — the four domain stores (`mcp_servers/{stockloan,margin,corpactions,cash}/store.py`) moved onto `mcp_servers/_finance_store.py`: a MEM mode (old fixtures verbatim, unit suite) + a SQL mode over seeded Postgres (14 platform-tier tables, `CREATE TABLE IF NOT EXISTS`, mirrored in `simulator/simulator/finance_tables.py` + `finance_baseline.py`, `make seed`). Planter keys `loans` / `lending` / `margin_calls` / `ca_events` / `ca_entitlements` / `cash_breaks`. `supervisor._open_loans` discovers a client's open loans → `_decompose`. `simulator/scenarios/030_mixed_domain_client.yaml` seeded (scored run deferred with the C+ sweep).
- **F fan-out hard rules** — `supervisor._apply_domain_rule` runs the per-domain `_enforce_*` (`_enforce_recall_window` / `_enforce_call_window` / `_enforce_funding_cutoff` / `_enforce_record_date`) on each sub-finding after `run_specialist`, so the Supervisor path no longer bypasses the code rules that `investigate_*` apply (rule 4).
- **B Wires module (core slice)** — `mcp_servers/wire/` (in-process fixture server: wires, holds, standing instructions, reviewer queue, cutoffs, one screening hit, balances; **no `release_wire` tool**), `WIRE` spec + `agent_core/wire.py::investigate_wire`, `planner/wire.md` + `synthesis/wire.md`, **four hard rules in code** (`_enforce_wire_controls`: screening HIT → referral only; balance < amount → no wire action; cutoff passed → `route_to_reviewer` → `reschedule_value_date`; new beneficiary → `route_to_reviewer`). `POST /investigate {wire_id}`; Supervisor `wire` sub-task + `_apply_domain_rule` branch; Prime Finance portal tab gains a Wire option. `tests/test_wire.py` (9).
- **B Wires seeded + discovery** — `wire/store.py` on `_finance_store.FinanceStore` (MEM + SQL over 6 seeded Postgres tables, `simulator/simulator/wire_tables.py` + `wire_baseline.py`); `wires` / `standing_instructions` / `wire_screening` planter keys; `simulator/scenarios/00{7},01{3,4,5,6}_*.yaml` (`subject: wire`, `expect:` ready for a sweep); `evals/harness.py` dispatches `subject: wire` → `investigate_wire`. `supervisor._held_wires` discovers a client's held wires → `_decompose`. Still deferred: a wire corpus; the portal `WIRE_REVIEWER` release flow.

**Still deferred (`docs/backlog.md`):**
- **Project-wide** — a full `workflow_dispatch` eval sweep + refreshed `evals/SCORECARD.md`, deferred to the **end of the project** (paused for C+ during the build; the record stays the Phase A 8/9). This is the final validation gate, not deferred depth.

**Before picking up either:** read its section in `docs/phase-breakdown.md`, follow the existing patterns (seeded stores via `_finance_store` / `platform_api.store`, hard rules in code, per-agent allowlists, `run_specialist` / `run_knowledge`). **No eval sweeps for C+ during the build** (owner decision).

## Roadmap (all phases, for orientation only)

**Mainline: Phase A (done) → C supervisor & specialists → D event-driven → E Developer Agent → F prime finance → G hardening.** **Phase B — Wires is an optional module**: it depends only on Phase A, nothing in C–G depends on it, and it can be slotted in at any point after A (or skipped). Each mainline phase is cumulative and reuses everything before it. **`docs/phase-breakdown.md` is the canonical full-scope reference — read it first**; it maps `docs/build-plan.md` / `docs/agent-plan.md` phase numbers (an older 0–13 scheme) to the letters (9=C, 10=D, 11–12=E, 13=F; the optional Wires module is 7=B) and marks which are superseded. **Read the relevant phase's section before starting it — don't build ahead of "Current phase" above.** When a phase starts, update "Current phase" and give its new code its own nested `CLAUDE.md` (see `enterprise/CLAUDE.md` for the pattern), rather than growing this file.

## Architecture (two tiers, two languages)

```
portal/          React + TypeScript (Vite)      — ops UI
ai-platform      Python 3.12                    — FastAPI platform API + agent-core + MCP servers
  platform-api/    cases, approvals, audit, trace API
  agent-core/      orchestrator, prompts, policy, schemas, guardrails
  mcp-servers/     one package per server; MCP Python SDK; wrap enterprise APIs
  knowledge/       corpus, ingestion, retrieval (pgvector)
  evals/           scenarios, runner, scorecard (pytest)
enterprise/      Java 21 + Spring Boot 3         — simulated bank systems (trade, client, …), plain REST over JPA
simulator/       Python                          — synthetic data generator + scenario planter
docs/            contracts, scenarios, standards, ADRs
```

The Python tier is the AI platform. The Java tier is "the bank's systems" — keep it boring: REST + JPA, no AI code. MCP servers wrap the Java APIs; agents talk only to MCP.

## Hard rules (never violate; tests assert these)

1. **Write tools validate `approval_id`** against `case-server` before executing. Enforcement lives in the tool, not the UI or the agent.
2. **Agents propose; humans approve; tools execute.** No agent code path executes a write without an APPROVED approval id.
3. **Every proposed action passes the policy engine** (`agent_core/policy/allowlists.yaml`). Out-of-allowlist → rejected, POLICY span emitted, action dropped from the Finding.
4. **Hard rules are code, not prompts** — outcome classification (`INSUFFICIENT_EVIDENCE`, `TOOL_DEGRADED`), tool budgets, approval checks.
5. **Emit spans on every agent step, tool call, retrieval, policy check, guardrail, approval** — from the first line of agent code. Span attributes: `docs/standards/observability.md`.
6. **Structured outputs are schema-validated** (`agent_core/schemas/`). Invalid → retry once → fail loudly.
7. **Never invent ids, tool names, or document sections.** Evidence must reference real tool results or retrieved chunks.
8. **Domain rule for Sc. 1:** a counterparty SSI mismatch is never resolved by overwriting the client's SSI. The agent must list `update_ssi` as a rejected alternative when our SSI is current.
9. **Plant facts, not conclusions.** Simulated records, logs, and documents state what happened — never why, never who is at fault. The agent derives root cause; the data must not hand it over. Interpretive language in planted data is a test failure.

## Conventions

- Contracts first: implement tools exactly as in `docs/tool-contracts.md`. If the contract is wrong, change the doc in the same PR and say so.
- Scenarios first: for any agent behaviour change, the relevant scenario in `docs/eval-scenarios.md` is the spec.
- Python: `uv`, `ruff`, `mypy --strict`, `pytest`. Type everything. Pydantic for schemas.
- Java: Maven, Spring Boot 3, JPA, Testcontainers for integration tests. `-Xmx512m`.
- React: TypeScript strict, functional components, no state library until needed.
- Prompts live in `agent_core/prompts/*.md`, versioned. Never inline prompt text in Python.
- Prefer to keep `prompts/`, `policy/`, `evals/` changes in their own PR, separate from feature code — unless a change is inseparable from the feature (e.g. a specialist split defined by its per-agent allowlist), in which case call it out in the PR body. (The eval gate that this rule originally served is `workflow_dispatch`-only during the build — see `docs/backlog.md`.)
- Prompt caching on system prompt + tool descriptions is on by default via `ModelClient`.
- Model routing: `classify` → cheap model; `plan`, `synthesize` → strong model. Configured in `agent_core/reasoning/model_router.py`, never hard-coded.

## Running and verifying

```
make up            # postgres+pgvector, enterprise, ai-platform (compose)
make seed SCENARIO=1
make run
make portal
make test          # unit + contract tests, both runtimes
make eval          # full scenario suite against real model calls → evals/SCORECARD.md
scripts/verify.sh  # lint + type + test; run before declaring any task done
```

`make eval` costs real money (~$2–3/run). **It is not a per-PR gate, and full sweeps are
paused for Phase C and later phases during the build** (owner decision, 2026-09 — see
`docs/backlog.md`). The CI `eval` workflow is manual-dispatch only. Run `make eval
SCENARIO=<n>` locally, or dispatch the workflow, if you want to spot-check a specific
agent-behaviour change; a full sweep + refreshed `SCORECARD.md` is deferred to the end of
the project. The `SCORECARD.md` on record is the Phase A result (8/9).

## Definition of done for a task

- `scripts/verify.sh` green
- Contract tests pass against seeded scenario data (not mocks)
- If the task changed agent behaviour: note the eval status — run `make eval SCENARIO=<n>`
  (or dispatch the workflow) if you want it validated now, or flag it for the next sweep
- PR body has a "How I validated" section listing exactly what was run
- No changes outside the task's stated scope; ideas go to `docs/backlog.md`
- Docs updated only where the task changed behaviour

## What not to do

- Don't add wire, supervisor, event, or Developer Agent code in Phase A.
- Don't add a workflow framework (LangGraph etc.) — the orchestrator is ours and small.
- Don't put procedures or domain SOPs in prompts — they come from the corpus via retrieval.
- Don't write tests that only exercise mocks of the enterprise tier.
- Don't rewrite README.md; append to `docs/backlog.md` instead.
- Don't use real institution names, product names, or anything resembling a real firm's conventions.
