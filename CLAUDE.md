# FinOps AI — project brief for Claude Code

Agentic trade & settlement operations platform on a fully simulated broker/dealer. **No real firm's data, code, documents, or naming.** Everything is fictional.

## Current phase: C — supervisor & specialists (in progress)

Phase A is shipped and deployed (single Investigator, trade mode: the simulated bank, the MCP layer, the agent + knowledge, governance, the n=3 eval harness at 8/9, the Agent Trace screen, live on Railway). **Phase C is now in progress** — split the Investigator into a Supervisor + specialists (Settlement · Risk/Client · Knowledge), each structurally scoped by tool set and policy allowlist. Read the "Phase C — Supervisor and specialists" section of `docs/phase-breakdown.md` and `ai-platform/agent_core/agents/CLAUDE.md` first. Still out of scope until their phase: Developer Agent, events, prime-finance. Wires (B) is an optional module. When Phase C completes, bump this line to "C — complete · next mainline phase: D".

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

`make eval` costs real money (~$2–3/run). **It is not a per-PR gate during the build** —
the CI `eval` workflow is manual-dispatch only. Run `make eval SCENARIO=<n>` locally, or
dispatch the workflow, when you want an agent-behaviour change validated; do a full sweep
before declaring a phase or the project done.

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
