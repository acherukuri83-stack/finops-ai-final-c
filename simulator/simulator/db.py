"""Database connection for the simulator.

The simulator runs on the host (via `make seed`), against the same Postgres the
Compose stack exposes on localhost:5432 — not the in-network `postgres` hostname
`enterprise`/`ai-platform` use. Override with DATABASE_URL if needed.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Connection, Engine, create_engine

DEFAULT_URL = "postgresql+psycopg://finops:finops@localhost:5432/finops"


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_URL)


_engine: Engine | None = None


def engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(database_url(), future=True)
    return _engine


@contextmanager
def connect() -> Iterator[Connection]:
    with engine().connect() as conn:
        with conn.begin():
            yield conn
