# agent_core — conventions
- Orchestrator is ours; no LangGraph or similar.
- Every model call goes through `reasoning/model_client.py`; model names via `model_router.py`.
- Prompts in `prompts/**/*.md`, loaded at startup; never inline.
- Structured outputs via `complete_structured` with a Pydantic schema from `schemas/`.
- Hard rules (outcomes, budgets, approval checks) are code. Prompts describe, code decides.
- Emit spans per docs/standards/observability.md on every step.
- `policy/allowlists.yaml` is the only source of what an agent may propose.
