# ADR-0005 — One process for the AI platform; four services on the demo

**Status:** accepted · **Phase:** A

## Decision
`ai-platform` runs the platform API **and every MCP server in one ASGI process**
(`mcp_servers.hub.mount_all`, plus an in-memory client session for the loop).
`AI_PLATFORM_SPLIT=1` skips the in-process mounting so the servers can run as separate
processes later. The hosted demo is four Railway services — `portal`, `ai-platform`,
`enterprise`, `postgres` — and `EventBus` is a no-op stub (no Kafka).

## Why
Phase A has one agent and nine servers that all wrap the same enterprise tier; running
them as one process removes eight deployments, eight health checks, and the inter-service
latency, for no loss of capability. The split flag keeps the option open for when a
server needs independent scaling or a different runtime. On the demo, a Postgres outbox
would be the event path, not Kafka — but Phase A never emits an event, so the stub is
honest and Kafka stays out of the hosting bill.

## Consequences
- The loop reaches tools through an in-memory MCP session, not a socket — fast, and the
  contract tests exercise the same path.
- A crash takes the API and all tools down together; acceptable at this stage,
  revisited if a server needs isolation.
- `docs/deploy-railway.md` provisions four services; the split topology (~8 services)
  is documented but not wired in Compose.
