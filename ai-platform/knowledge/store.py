"""pgvector store for the knowledge corpus. One table, cosine distance.

The `vector` extension is created by enterprise `V1__init.sql`; `ensure_schema` re-creates
it and the table idempotently so `make ingest` works against a bare Postgres too.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Column,
    Connection,
    Engine,
    MetaData,
    String,
    Table,
    create_engine,
    delete,
    select,
    text,
)

from knowledge.embeddings import DIM
from platform_api.settings import settings

_metadata = MetaData()

chunks = Table(
    "knowledge_chunks",
    _metadata,
    Column("id", String, primary_key=True),
    Column("kind", String, nullable=False),
    Column("doc", String, default=""),
    Column("section", String, default=""),
    Column("title", String, default=""),
    Column("incident_id", String, default=""),
    Column("summary", String, default=""),
    Column("root_cause", String, default=""),
    Column("resolution", String, default=""),
    Column("text", String, nullable=False),
    Column("embedding", Vector(DIM), nullable=False),
)

_engine: Engine | None = None


def engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(settings.database_url, future=True)
    return _engine


@contextmanager
def connect() -> Iterator[Connection]:
    with engine().begin() as conn:
        yield conn


def ensure_schema(conn: Connection) -> None:
    conn.execute(text("create extension if not exists vector"))
    _metadata.create_all(conn.engine, tables=[chunks])
    conn.execute(
        text(
            "create index if not exists knowledge_chunks_embedding_idx "
            "on knowledge_chunks using ivfflat (embedding vector_cosine_ops) with (lists = 20)"
        )
    )


def replace_all(conn: Connection, rows: list[dict[str, Any]]) -> None:
    conn.execute(delete(chunks))
    if rows:
        conn.execute(chunks.insert(), rows)


def search(
    conn: Connection, query_vec: list[float], k: int, kinds: list[str] | None = None
) -> list[dict[str, Any]]:
    distance = chunks.c.embedding.cosine_distance(query_vec).label("distance")
    stmt = select(chunks, distance).order_by(distance).limit(k)
    if kinds is not None:
        stmt = stmt.where(chunks.c.kind.in_(kinds))
    out: list[dict[str, Any]] = []
    for row in conn.execute(stmt).mappings():
        item = dict(row)
        item.pop("embedding", None)
        item["score"] = round(1.0 - float(item.pop("distance")), 4)
        out.append(item)
    return out
