# Coding Standard

## Python (ai-platform, simulator, evals)
- §1 Python 3.12, `uv` for env and lockfile. `ruff` (format + lint), `mypy --strict`, `pytest`.
- §2 Pydantic models for every schema in `agent_core/schemas/`; no untyped dicts cross a module boundary.
- §3 Async by default in agent-core and MCP servers; sync only in the simulator.
- §4 One package per MCP server under `mcp_servers/<name>/`; tools in `tools/`, each tool a single function with a typed input model and a docstring that **is** the exposed description.
- §5 Prompts live in `agent_core/prompts/**/*.md`, loaded at startup, never inlined.
- §6 Configuration via environment + a single `settings.py`; no secrets in code.
- §7 Public functions have docstrings; §7.2 tool functions additionally state when to use / when not to.
- §8 Tests: contract tests hit the real Spring Boot tier with seeded data; unit tests may fake `ModelClient`; scenario tests use real model calls and are marked `@pytest.mark.eval`.

## Java (enterprise)
- §10 Java 21, Spring Boot 3, Maven. Plain REST controllers over JPA. No business logic beyond what the simulator needs.
- §11 Testcontainers for integration tests. `-Xmx512m` in all run configs.
- §12 No AI, MCP, or agent code in this tier — it represents the bank's estate.

## React (portal)
- §20 TypeScript strict. Functional components. No global state library until two screens need the same server state.
- §21 API client generated from the FastAPI OpenAPI spec.
- §22 Trace ids surfaced in the UI wherever a request is shown.

## Repo
- §30 Conventional commits. One concern per PR. `prompts/`, `policy/`, `evals/` changes in their own PR.
- §31 Every PR body has "How I validated" listing the exact commands run.
- §32 Ideas that are out of scope go to `docs/backlog.md`, not into code or README.
