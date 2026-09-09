# Observability Standard

Every agent run produces one trace. Spans are emitted with OpenTelemetry and exported to Postgres (`trace`, `span`, `span_payload`) for the Trace screen; Jaeger locally for engineers. Payloads are stored post-scrub.

## Span types and required attributes

| `finops.span.type` | Required attributes |
|---|---|
| `agent` | `finops.agent`, `finops.step` (classify / plan / synthesize / replan), `finops.model`, `finops.tokens.in`, `finops.tokens.out`, `finops.cache.read` |
| `tool` | `finops.tool.server`, `finops.tool.name`, `finops.tool.access` (read/write), `finops.tool.ok`, `finops.tool.retryable` (on error), `finops.tool.retries` |
| `retrieval` | `finops.retrieval.query`, `finops.retrieval.k`, `finops.retrieval.results` (json: doc, section, score, cited: bool) |
| `policy` | `finops.agent`, `finops.action`, `finops.policy.decision` (ALLOWED/REJECTED), `finops.policy.rule` |
| `delegation` | `finops.agent` (always `supervisor`), `finops.subtask.agent`, `finops.subtask.subjects` (json), `finops.subtask.budget` |
| `event` | `finops.event.type` (FAILED / HELD), `finops.event.topic`, `finops.event.key` (dedup key), `finops.event.subject`, `finops.event.deadline?` — the **root** span when an investigation is event-triggered (Phase D) |
| `guardrail` | `finops.guardrail.name` (input_classification / pii_scrub / schema_validation), `finops.guardrail.result`, `finops.guardrail.count` |
| `approval` | `finops.approval.id`, `finops.approval.status`, `finops.approval.by`, `finops.approval.role`, `finops.approval.elapsed_ms` |

Common: `finops.trace.id`, `finops.case.id?`, `finops.scenario.id?` (eval runs).

## Rules
- The same trace id propagates from the React request through FastAPI, agent-core, MCP calls, and into the Spring Boot tier (W3C `traceparent`).
- Synthesis spans carry the Finding's `rejected_alternatives` in the payload.
- A Supervisor run (Phase C) is one trace: each specialist dispatch runs inside a `delegation` span, so every specialist's `agent` / `tool` / `policy` spans share the client trace id.
- An event-triggered investigation (Phase D) has the `event` span as its trace root; the `investigate` / `investigate_client` span nests under it, so the trace shows the trigger.
- (Phase G) `complete_structured_traced` emits the `schema_validation` guardrail span on every structured-output call (`finops.guardrail.count` = retries used, `result` = ok/failed). `finops.tool.retries` on a `tool` span is the in-call retry count of the last enterprise request (`mcp_servers._enterprise.last_retries()`, a `ContextVar`); 0 for in-process fixture servers.
- No span payload contains raw PII (see security §7). `platform_api/trace_store.scrub()`
  runs over every stored payload — emails, 9+-digit runs, and person-name keys
  (`updated_by`, `set_by`, `decided_by`, …) are replaced; the count is stamped on the span
  as `finops.pii.redactions` (Phase G). It is a span **attribute**, not a separate
  `guardrail` span, because the scrub runs inside `PostgresSpanProcessor.on_end` and
  emitting a span there would recurse.
- Traces are immutable once a case is closed.
