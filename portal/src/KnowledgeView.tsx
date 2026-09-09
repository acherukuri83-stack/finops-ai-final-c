import { useState } from "react";
import { api, type KnowledgeHit } from "./api";

const mono: React.CSSProperties = { fontFamily: "ui-monospace, monospace" };

export default function KnowledgeView() {
  const [q, setQ] = useState("counterparty SSI mismatch settlement failure");
  const [hits, setHits] = useState<KnowledgeHit[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      setHits(await api.knowledge(q));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="module-workspace knowledge-workspace">
      <div className="section-heading">
        <span className="section-symbol">⌕</span>
        <div>
          <h3>Search the knowledge library</h3>
          <p>
            Find procedures and source passages that support an investigation.
          </p>
        </div>
      </div>
      <form
        className="module-form"
        onSubmit={(e) => {
          e.preventDefault();
          void run();
        }}
        style={{ display: "flex", gap: 8, marginBottom: 16 }}
      >
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ flex: 1, padding: "6px 8px" }}
          aria-label="Search the corpus"
        />
        <button type="submit" disabled={busy}>
          {busy ? "Searching…" : "Search"}
        </button>
      </form>

      {error && <p style={{ color: "#b00" }}>Error: {error}</p>}
      {hits?.length === 0 && <p style={{ color: "#888" }}>No results.</p>}

      {hits?.map((h, i) => (
        <div key={i} className="knowledge-card">
          <span className="source-label">SOURCE {i + 1}</span>
          <div style={mono}>
            {h.doc}
            {h.section ? ` §${h.section}` : ""} {h.title ? `— ${h.title}` : ""}
            <span className="score-label">
              {" "}
              Similarity {h.score.toFixed(3)}
            </span>
          </div>
          <div style={{ color: "#444", marginTop: 4, whiteSpace: "pre-wrap" }}>
            {h.text}
          </div>
        </div>
      ))}
    </div>
  );
}
