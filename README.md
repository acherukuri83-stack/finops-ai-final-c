# FinOps AI — Agentic Trade & Settlement Operations Platform

An AI operations assistant for a **fully simulated** broker/dealer. An analyst asks
*"why didn't trade T100245 settle?"* — the agent plans an investigation, calls the
bank's systems through MCP tools, retrieves the operating procedure and a prior
incident, determines the root cause with **cited evidence**, proposes a fix, and
executes it **only after a human approves**. Every step is traced, audited, and scored
against a golden scenario suite.

> Everything here is fictional. No real firm's data, code, documents, or naming.

**Status:** Phase A complete — single Investigator agent, trade mode. Deployed demo, an
n=3 eval scorecard, and a full Agent Trace screen. Roadmap and phase plan in
[`docs/final-plan.md`](docs/final-plan.md); architecture narrative in
[`docs/design.md`](docs/design.md).

**▶ Hosted demo:** _add your Railway portal URL here_ · try investigating **`T100245`**
(counterparty SSI stale), **`T100261`** (compliance hold), **`T100270`** (short
position).

**▶ Demo video (4 min):** _link_ — Sc. 1 investigate → approve → Sc. 4 restraint →
Sc. 2 flip → the trace → the scorecard.

---

## The investigation

`POST /investigate {"trade_id": "T100245"}` runs, in one traced request:

1. **Guardrail** — is this an operations request at all? Off-topic input is declined
   with zero tool calls.
2. **Plan** — the planner turns the request into tool calls from what MCP exposes; it
   re-plans when an observation contradicts an assumption (budget 12 calls, 4 planner
   turns).
3. **Tool loop** — `get_trade`, `get_settlement_status`, `get_ssi` / `get_ssi_history`,
   `get_affirmation`, `get_counterparty_ssi`, … against the Java "bank" tier.
4. **Retrieval** — `search_knowledge` / `find_incidents` over the SOP + incident corpus;
   chunks come back with `doc §section` so citations are real.
5. **Synthesize** — a schema-validated `Finding`: root cause, cited evidence, proposed
   actions, and the alternatives it explicitly rejected (for T100245: `update_ssi` is
   rejected — *Settlement Handbook §8.4 ¶3*, our instruction is current).
6. **Policy** — every proposed action is filtered against the agent's allowlist; a
   dropped action gets a `POLICY` span and a note.
7. **Case** — a case opens, each surviving action is registered as a **PENDING
   approval**. Nothing mutates a record yet.

A human then approves via the portal (`POST /approvals/{id}/decide`, role
`OPS_ANALYST`). The write tool re-checks the `approval_id` **inside the tool**, calls
the enterprise, and appends an audit event. The whole thing — plan, tools, retrievals,
policy checks, the approval — is one trace you can open in the portal.

## Five concepts, one investigation

| Concept | Here | |
|---|---|---|
| **LLM** | plan the investigation, determine root cause, reject alternatives, explain | [design.md](docs/design.md#five-concepts-one-investigation) |
| **RAG** | SOPs + incidents as evidence, retrieved and cited by section, exposed as MCP tools | [design.md](docs/design.md#five-concepts-one-investigation) |
| **MCP** | 9 servers (28 tools); `access: read \| write`; a write needs a validated `approval_id` | [tool-contracts.md](docs/tool-contracts.md) |
| **Agentic worker** | plan → act under approval → escalate when evidence is thin or the action is out of scope | [design.md](docs/design.md#five-concepts-one-investigation) |
| **Platform** | cases, approvals, audit, policy allowlists, the Agent Trace screen, the eval suite | [design.md](docs/design.md#five-concepts-one-investigation) |

## What's built (Phase A)

- **9 MCP servers, 28 tools** wrapping the Java tier — trade / client / counterparty /
  position / reference / market / compliance / ops, plus an in-process `case` server.
  Three write tools (`resubmit_settlement`, `cancel_trade`, `update_ssi`) validate the
  `approval_id` themselves ([ADR-0001](docs/adr/0001-approval-enforced-at-the-tool.md)).
- **Governance spine** — `cases` / `approvals` / `audit_events`, the `ProposedAction`
  schema, a policy engine over `agent_core/policy/allowlists.yaml`, an
  input-classification guardrail.
- **Knowledge / RAG** — 8 SOPs (`§`-sectioned) + `INC-1001…1008` + a custodian-notice
  fixture, `fastembed` (`bge-small-en-v1.5`) into pgvector.
- **Agent Trace screen** — every span persisted (`traces` / `spans` / `span_payloads`);
  timeline, expandable payloads, retrieved-vs-cited, replay, diff, JSON export;
  Evidence / Audit / Case ↔ Trace cross-links.
- **Eval harness** — one generic scorer over each scenario's `expect:` block, run
  **n=3**; CI gates on it.

## Scorecard

**8 / 9 scenarios pass** (n=3) — see
[`ai-platform/evals/SCORECARD.md`](ai-platform/evals/SCORECARD.md). Scenario 8
(duplicate-booking) reaches the right cause and action but cites 2 of 3 required
evidence refs — tracked in [`docs/backlog.md`](docs/backlog.md). Scenario 12 (tool
outage) needs process-global fault injection and is covered by a unit test.

## Stack

React + TypeScript (Vite) · Python 3.12 (FastAPI, own orchestrator, MCP Python SDK,
pgvector, pytest) · Java 21 / Spring Boot 3 (the simulated bank) · Postgres + pgvector ·
Claude via the Anthropic API · OpenTelemetry · Docker Compose locally · Railway for the
hosted demo (four services).

## Run it locally

Needs Docker, `uv`, and an Anthropic API key. ~10–15 min (mostly image pulls).

```bash
cp .env.example .env               # add ANTHROPIC_API_KEY
make up                            # postgres · jaeger · enterprise · ai-platform · portal
make seed                          # baseline + all 10 scenarios
make ingest FIXTURES=CN-2026-081   # build the knowledge index
```

Open the portal at **http://localhost:5173** → **Trades** → `T100245` → **Investigate**.
Approve the proposed action in **Cases**, then open the **Traces** tab for that run.

```bash
make verify        # ruff + mypy + pytest (both runtimes) + portal lint/tsc
make eval          # the n=3 scorecard — real model calls, ~$2
```

## Deploy

Four services on Railway. Per-service `railway.json` + Dockerfiles are in the repo; the
dashboard checklist — variables, domains, one-time seeding, usage/spend guardrails — is
in [`docs/deploy-railway.md`](docs/deploy-railway.md).

## Layout

```
ai-platform/   platform_api · agent_core · mcp_servers · knowledge · evals   (Python)
enterprise/    simulated bank systems — plain REST + JPA, no AI code         (Spring Boot)
simulator/     deterministic baseline + scenario planter                     (Python)
portal/        ops UI — Cases · Trades · Knowledge · Connections · Traces     (React)
docs/          design · final-plan · tool-contracts · eval-scenarios · standards · ADRs
```

## Docs

| | |
|---|---|
| [`docs/design.md`](docs/design.md) | the full architecture narrative and the five concepts |
| [`docs/final-plan.md`](docs/final-plan.md) | Phase A, weekend by weekend; the A–G roadmap |
| [`docs/project-status.md`](docs/project-status.md) | what is actually built, module by module |
| [`docs/tool-contracts.md`](docs/tool-contracts.md) | every MCP tool: signature, access, description |
| [`docs/eval-scenarios.md`](docs/eval-scenarios.md) | the 10 golden scenarios and their `expect:` blocks |
| [`docs/standards/`](docs/standards/) · [`docs/adr/`](docs/adr/) | coding / observability / security · the decisions and why |

## Disclaimer

A portfolio / learning project. Fully fictional domain — any resemblance to a real
firm, product, or person's data is coincidental. Not investment advice.
