# mcp_servers — conventions
- One package per server: `mcp_servers/<name>/{server.py, tools/, client.py, models.py}`.
  `server.py` builds the `FastMCP` instance and registers the tools; `tools/__init__.py`
  holds the tool functions; `models.py` holds that server's response shapes.
- Tools implement docs/tool-contracts.md exactly; the function docstring **is** the exposed
  description (verbatim). `access: read | write` is tracked per server in `hub.py`.
- `client.py` re-exports `mcp_servers._enterprise` (`get_enterprise_client`, `guard`); all
  enterprise HTTP goes through that one module — httpx, traceparent propagated. 5xx /
  transport error → one in-tool retry, then `ErrorEnvelope{retryable: true}`; 4xx →
  `retryable: false` (404 → `NOT_FOUND`). `@guard` turns the internal `EnterpriseError`
  into the envelope payload; **tools never raise**.
- `hub.py` is the registry: `open_session()` (in-memory MCP client for the skeleton +
  contract tests), `mount_all(app)` (SSE mounts at `/mcp/<name>`, skipped when
  `AI_PLATFORM_SPLIT=1`), `describe()` (backs `GET /connections`).
- Write tools (`resubmit_settlement`, `cancel_trade`, `update_ssi`) and the `case` server
  arrive in W3; they will call `case.get_approval` before any side effect
  (docs/standards/security.md §2–§4).
