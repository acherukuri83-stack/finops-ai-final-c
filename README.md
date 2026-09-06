# FinOps AI — Agentic Trade & Settlement Operations Platform

An AI operations assistant for a **fully simulated** broker/dealer. An analyst asks *"why didn't trade T100245 settle?"* — the agent plans, calls tools through MCP, retrieves the operating procedure and a prior incident, determines the root cause with cited evidence, proposes a fix, and executes it only after a human approves. Everything is traced, audited, and scored against a golden scenario suite.

> Everything here is fictional. No real firm's data, code, documents, or naming.

**Status:** Phase A in progress — see [`docs/final-plan.md`](docs/final-plan.md). Full design: [`docs/design.md`](docs/design.md).

## Stack
React + TypeScript · Python 3.12 (FastAPI, own orchestrator, MCP Python SDK, pgvector) · Java 21 / Spring Boot 3 (simulated enterprise tier) · Postgres + pgvector · Claude via Anthropic API · OpenTelemetry · Docker Compose · Railway

## Getting started
```bash
cp .env.example .env            # add ANTHROPIC_API_KEY
make up                         # postgres, jaeger, enterprise, ai-platform, portal
make seed SCENARIO=1
make verify
```

## Layout
```
ai-platform/   platform_api · agent_core · mcp_servers · knowledge · evals   (Python)
enterprise/    simulated bank systems                                       (Spring Boot)
simulator/     synthetic data + scenario planter                            (Python)
portal/        ops UI                                                        (React)
docs/          plan, design, contracts, scenarios, standards, ADRs, issues
```
