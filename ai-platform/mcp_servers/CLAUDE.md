# mcp_servers — conventions
- One package per server: `mcp_servers/<name>/{server.py, tools/, client.py}`.
- Tools implement docs/tool-contracts.md exactly; the docstring is the exposed description.
- `access: read | write` declared per tool. Write tools call case.get_approval before any side effect (docs/standards/security.md §2–§4).
- All enterprise calls go through `client.py` (httpx, traceparent propagated). 5xx → ErrorEnvelope{retryable: true}, one retry inside the tool; 4xx → retryable: false.
- Servers are mounted into platform_api.main unless AI_PLATFORM_SPLIT=1.
