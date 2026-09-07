"""Prompt loader. Prompts live in `agent_core/prompts/**/*.md` and are read at import,
never inlined in Python (agent_core/CLAUDE.md).
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

_ROOT = Path(__file__).parent


@cache
def load(name: str) -> str:
    """`load("planner/trade")` -> the text of `agent_core/prompts/planner/trade.md`."""
    return (_ROOT / f"{name}.md").read_text(encoding="utf-8").strip()
