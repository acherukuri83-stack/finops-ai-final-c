# enterprise — conventions
- This tier is "the bank's systems." Plain Spring Boot REST over JPA. No AI, MCP, or agent code.
- Flyway migrations in `src/main/resources/db/migration`. `ddl-auto: validate`.
- Endpoints per docs/issues/W1-foundation-data-tools.md PR2. Write endpoints have **no** approval logic — the MCP write tools own that.
- Testcontainers for integration tests; assert planted scenario values, not shapes.
- `-Xmx512m` everywhere. Propagate W3C traceparent (micrometer-tracing does this).
