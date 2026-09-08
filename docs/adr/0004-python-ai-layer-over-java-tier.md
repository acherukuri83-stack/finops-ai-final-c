# ADR-0004 — Python AI layer over a boring Java "bank" tier

**Status:** accepted · **Phase:** A

## Decision
Two tiers, two languages. `enterprise/` is Java 21 / Spring Boot 3 — plain REST over
JPA, Flyway migrations, no AI, agent, or MCP code. `ai-platform/` is Python 3.12 and
holds everything intelligent: the platform API, the orchestrator, the MCP servers, the
knowledge index, the evals. The MCP servers wrap the Java REST API over HTTP; the agent
talks only to MCP.

## Why
It mirrors reality: the systems of record are owned by other teams and change on their
own schedule, and the AI platform is a layer *over* them, not a rewrite *of* them. The
split forces a clean contract (`docs/tool-contracts.md`) and makes "swap a backend, the
agent runs unchanged" a real property, not a claim. It also keeps the Java side
reviewable by someone with no AI context, and the Python side free to move fast.

## Consequences
- One extra network hop per tool call (Python → httpx → Spring Boot); the error
  envelope and a one-in-tool retry live in `mcp_servers/_enterprise.py`.
- Schema is owned by Java Flyway; the Python tier adds its own tables
  (`cases`, `knowledge_chunks`, `traces`) with idempotent `CREATE TABLE IF NOT EXISTS`
  in the same Postgres — never a Flyway migration.
- Two toolchains in CI (`uv` + Maven).
