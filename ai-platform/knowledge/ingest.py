"""Build the pgvector index from `knowledge/corpus/`.

    python -m knowledge.ingest                     # all SOPs + incidents, no fixtures
    python -m knowledge.ingest --fixtures CN-2026-081

Idempotent: every run truncates `knowledge_chunks` and reloads. Fixtures under
`corpus/fixtures/` are only ingested when named, so Scenario 2's flip stays honest.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path

from knowledge import store
from knowledge.chunking import Chunk, chunk_file
from knowledge.embeddings import embed

CORPUS = Path(__file__).parent / "corpus"


def gather(fixtures: set[str]) -> list[Chunk]:
    out: list[Chunk] = []
    for path in sorted(CORPUS.glob("*.md")):
        out.extend(chunk_file(path))
    for path in sorted((CORPUS / "incidents").glob("*.md")):
        out.extend(chunk_file(path))
    for path in sorted((CORPUS / "fixtures").glob("*.md")):
        if path.stem in fixtures:
            out.extend(chunk_file(path))
    return out


def ingest(fixtures: set[str] | None = None) -> int:
    corpus = gather(fixtures or set())
    vectors = embed([c.text for c in corpus])
    rows = []
    for chunk, vec in zip(corpus, vectors, strict=True):
        row = {k: v for k, v in asdict(chunk).items() if k != "extra"}
        row["embedding"] = vec
        rows.append(row)
    with store.connect() as conn:
        store.ensure_schema(conn)
        store.replace_all(conn, rows)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", nargs="*", default=[], help="fixture ids to include")
    args = parser.parse_args()
    n = ingest(set(args.fixtures))
    print(f"[ingest] {n} chunks (fixtures: {sorted(args.fixtures) or 'none'})")


if __name__ == "__main__":
    main()
