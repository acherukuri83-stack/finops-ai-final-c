# Observability Standard

Every agent run produces one trace. Spans are emitted with OpenTelemetry and exported to Postgres (`trace`, `span`, `span_payload`) for the Trace screen; Jaeger locally for engineers. Payloads are stored post-scrub.

## Span types and required attributes

| `finops.span.type` | Required attributes |
|---|---|
| `agent` | `finops.agent`, `finops.step` (classify / plan / synthesize / replan), `finops.model`, `finops.tokens.in`, `finops.tokens.out`, `finops.cache.read` |
| `tool` | `finops.tool.server`, `finops.tool.name`, `finops.tool.access` (read/write), `finops.tool.ok`, `finops.tool.retryable` (on error), `finops.tool.retries` |
| `retrieval` | `finops.retrieval.query`, `finops.retrieval.k`, `finops.retrieval.results` (json: doc, section, score, cited: bool) |
| `policy` | `finops.agent`, `finops.action`, `finops.policy.decision` (ALLOWED/REJECTED), `finops.policy.rule` |
| `guardrail` | `finops.guardrail.name` (input_classification / pii_scrub / schema_validation), `finops.guardrail.result`, `finops.guardrail.count` |
| `approval` | `finops.approval.id`, `finops.approval.status`, `finops.approval.by`, `finops.approval.role`, `finops.approval.elapsed_ms` |

Common: `finops.trace.id`, `finops.case.id?`, `finops.scenario.id?` (eval runs).

## Rules
- The same trace id propagates from the React request through FastAPI, agent-core, MCP calls, and into the Spring Boot tier (W3C `traceparent`).
- Synthesis spans carry the Finding's `rejected_alternatives` in the payload.
- No span payload contains raw PII (see security §7).
- Traces are immutable once a case is closed.
