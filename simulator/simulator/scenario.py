"""Scenario file schema. `plant:` is facts only; `expect:` is for evals (ignored here)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

# Words that indicate interpretation rather than fact. Their presence in planted data is a bug.
LEAK_WORDS = ("stale", "wrong side", "never picked up", "root cause", "because", "should have")

PLANT_KEYS = {
    "accounts.ssi",
    "counterparties.ssi",
    "trades",
    "settlement_attempts",
    "affirmations",
    "positions",
    "borrow",
    "restrictions",
    "securities",
    "loans",  # Phase F — an open stock loan (mixed-domain client, Sc. 30)
    "lending",  # Phase F — street lending availability for a security
    "margin_calls",  # Phase F — a margin call
    "ca_events",  # Phase F — a corporate-action event
    "ca_entitlements",  # Phase F — an account's held/lent split over the record date
    "cash_breaks",  # Phase F — a projected cash break
    "wires",  # Phase B — a held outgoing wire
    "standing_instructions",  # Phase B — a client's approved wire beneficiaries
    "wire_screening",  # Phase B — a sanctions screening result (incl. a hit)
    "logs",
    "incidents",
    "corpus_fixtures",
}


class Scenario(BaseModel):
    id: int
    name: str
    baseline: str = "default"
    plant: dict[str, Any] = Field(default_factory=dict)
    expect: dict[str, Any] = Field(default_factory=dict)
    fault_inject: str | None = None

    @classmethod
    def load(cls, path: Path) -> Scenario:
        data = yaml.safe_load(path.read_text())
        return cls.model_validate(data)

    def unknown_plant_keys(self) -> set[str]:
        return set(self.plant) - PLANT_KEYS

    def leaks(self) -> list[str]:
        """Return planted strings that contain interpretive language."""
        found: list[str] = []

        def walk(v: Any) -> None:
            if isinstance(v, str):
                low = v.lower()
                if any(w in low for w in LEAK_WORDS):
                    found.append(v)
            elif isinstance(v, dict):
                for x in v.values():
                    walk(x)
            elif isinstance(v, list):
                for x in v:
                    walk(x)

        walk(self.plant)
        return found
