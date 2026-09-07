# knowledge — conventions
- `corpus/*.md` — SOP docs, front-matter `doc:` (the citation name). Sections are
  `## §<num> — <title>`; one chunk per section. `corpus/incidents/INC-*.md` — one chunk
  per incident, fields in front-matter. `corpus/fixtures/*.md` — `kind: fixture`, only
  ingested when named on `python -m knowledge.ingest --fixtures <id>` (keeps Sc. 2's flip
  honest). Fixture text is facts only — the leak check applies.
- Embeddings: fastembed `BAAI/bge-small-en-v1.5`, 384-dim, cosine. Model is pulled from
  Hugging Face on first use (fails behind the corporate TLS proxy — CI is the run path).
- Store: one pgvector table `knowledge_chunks`. `ensure_schema` is idempotent DDL; the
  `vector` extension already comes from enterprise `V1__init.sql`.
- `retrieval.search_knowledge` / `find_incidents` are what `ops.search_knowledge` /
  `ops.find_incidents` call. Return shapes are exactly `docs/tool-contracts.md`.
- No AI/model code beyond the local embedder; the agent lives in `agent_core/`.
