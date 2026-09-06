# FinOps AI — Cost Analysis

Estimates as of September 2026. Rates change; verify on the providers' pricing pages before quoting these anywhere.

## Rate assumptions

| Item | Rate used |
|---|---|
| Railway compute | $20 per vCPU-month, $10 per GB RAM-month, billed per second on actual usage |
| Railway storage / egress | $0.15 per GB-month volume; $0.05 per GB egress |
| Railway plan | Hobby $5/month, includes $5 usage credit; hard usage limit available (min $10) |
| Claude Sonnet (strong model) | $3 / $15 per million input/output tokens (standard rate) |
| Claude Haiku (cheap model) | $1 / $5 per million input/output tokens |
| Prompt caching | cached input ≈ 10% of standard input price |
| Embeddings | negligible — small corpus; local model (`bge-small` or similar) is free |

## Build cost — model usage

Per-run cost, with routing (Haiku for classify, Sonnet for plan/synthesis) and caching on system prompt + tool descriptions:

| Workload | Tokens (approx.) | Cost |
|---|---|---|
| Single-agent investigation (Sc. 1–10, 12–16) | ~5k in / 1.5k out | **~$0.04** |
| Supervisor run (Sc. 11) | 4 specialists + synthesis | ~$0.15 |
| Developer Agent — incident (Sc. 17–18) | logs + source context | ~$0.10–0.20 |
| Developer Agent — PR review (Sc. 19–21) | diff + standards + scan output | ~$0.15–0.30 |
| Full eval suite, 16 scenarios × 3 runs | | ~$3 |
| Full eval suite, 25 scenarios × 3 runs | | ~$6 |

Monthly by phase (interactive iteration + eval runs):

| Phases | LLM $/month |
|---|---|
| 0–2 | < $5 |
| 3–7 | $40–100 |
| 8–10 | $20–40 |
| 11–12 | $40–80 |
| 13 | $30–60 |

**Build to M2 (~3.5 months): ~$150–400. Build to M3 (~5 months): ~$300–700.** Excludes any coding-assistant subscription.

## Hosting cost — Railway

Nothing hosted until M2 (run locally through Phase 7).

### Consolidated layout (recommended)

| Service | Sizing (avg) | $/month |
|---|---|---|
| `portal` — static React behind Caddy | 0.1 vCPU, 0.25 GB | ~$5 |
| `ai-platform` — FastAPI + agents + all MCP servers, one process | 0.3 vCPU, 0.75 GB | ~$13 |
| `enterprise` — Spring Boot, single JVM | 0.25 vCPU, 1 GB | ~$15 |
| `postgres` — pgvector + event outbox, 2 GB volume | 0.2 vCPU, 0.75 GB | ~$12 |
| Egress | demo traffic | ~$1 |
| **Always-on** | | **~$45/month** (≈ $40 after Hobby credit) |
| **Sleeping between demos** | | **~$15–25/month** |

### What was avoided

| Choice | Saves |
|---|---|
| One Python process instead of ~12 containers (API, agents, 10 MCP servers) | ~$60–100/month |
| Postgres outbox instead of Redpanda on the demo | ~$15/month |
| Static portal instead of a Node server | ~$5/month |

A naive one-container-per-module deployment with Kafka lands at **$120–180/month** for the same demo.

### Guards

- Set a Railway hard usage limit (e.g. $60) with alerts.
- Eval suite runs in CI only on PRs touching `prompts/`, `policy/`, `knowledge/`, `simulator/`.
- Per-investigation token budget enforced in the orchestrator (already required for Scenario 12).
- Spend alert on the Anthropic console.

## Year-one total

| | Low | High |
|---|---|---|
| Build (tokens) | ~$300 | ~$700 |
| Hosting, ~8 months after M2 | ~$160 | ~$480 |
| Domain | ~$12 | ~$12 |
| **Total** | **~$500** | **~$1,200** |

Plus coding-assistant subscription if used.

## AWS alternative (documented, not built)

ECS Fargate for the three app services, RDS Postgres, and either MSK or Redpanda on ECS: roughly **$80–150/month** always-on with more setup. Kept as `docs/deploy-aws.md` because AWS is on the resume; Railway is the better fit for a portfolio demo's cost and effort.
