import { useEffect, useState } from "react";
import { api, type Finding, type TradeRow } from "./api";

const cell: React.CSSProperties = { padding: "6px 10px", borderBottom: "1px solid #eee", textAlign: "left" };
const mono: React.CSSProperties = { fontFamily: "ui-monospace, monospace" };

export default function TradesView() {
  const [rows, setRows] = useState<TradeRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<TradeRow | null>(null);
  const [finding, setFinding] = useState<Finding | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.trades().then(setRows).catch((e: Error) => setError(e.message));
  }, []);

  async function open(id: string) {
    setFinding(null);
    setError(null);
    try {
      setSelected(await api.trade(id));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function runInvestigation(id: string) {
    setBusy(true);
    setError(null);
    try {
      setFinding(await api.investigate(id));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (error) return <p style={{ color: "#b00" }}>Error: {error}</p>;
  if (!rows) return <p style={{ color: "#888" }}>Loading trades…</p>;

  return (
    <div style={{ display: "flex", gap: 32, alignItems: "flex-start" }}>
      <table style={{ borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr>
            {["Trade", "Client", "Security", "Qty", "Side", "Status", "Settles"].map((h) => (
              <th key={h} style={{ ...cell, color: "#888", fontWeight: 600 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((t) => (
            <tr
              key={t.trade_id}
              onClick={() => open(t.trade_id)}
              style={{ cursor: "pointer", background: selected?.trade_id === t.trade_id ? "#eef4ff" : undefined }}
            >
              <td style={{ ...cell, ...mono }}>{t.trade_id}</td>
              <td style={cell}>{t.client_id}</td>
              <td style={cell}>{t.security_id}</td>
              <td style={{ ...cell, ...mono, textAlign: "right" }}>{t.qty}</td>
              <td style={cell}>{t.side}</td>
              <td style={cell}>{t.status}</td>
              <td style={{ ...cell, ...mono }}>{t.settle_date}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {selected && (
        <div style={{ fontSize: 13, minWidth: 320 }}>
          <h3 style={{ marginTop: 0 }}>
            <span style={mono}>{selected.trade_id}</span>
          </h3>
          <dl style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "4px 12px" }}>
            {Object.entries(selected).map(([k, v]) => (
              <div key={k} style={{ display: "contents" }}>
                <dt style={{ color: "#888" }}>{k}</dt>
                <dd style={{ margin: 0, ...mono }}>{String(v)}</dd>
              </div>
            ))}
          </dl>
          <button
            onClick={() => runInvestigation(selected.trade_id)}
            disabled={busy}
            style={{ marginTop: 12 }}
          >
            {busy ? "Investigating…" : "Investigate"}
          </button>
          {finding && (
            <div style={{ marginTop: 12, padding: 12, background: "#f7f7f7", borderRadius: 6 }}>
              <div>
                outcome <b>{finding.outcome}</b>
                {finding.root_cause ? (
                  <>
                    {" "}
                    · root cause <b style={mono}>{finding.root_cause}</b>
                  </>
                ) : null}
              </div>

              {finding.confidence_basis ? (
                <div style={{ color: "#555", marginTop: 4 }}>{finding.confidence_basis}</div>
              ) : null}

              {finding.proposed_actions && finding.proposed_actions.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  <b>Proposed</b>
                  {finding.proposed_actions.map((a, i) => (
                    <div key={i}>
                      <span style={mono}>{a.action_type}</span> — {a.rationale}
                    </div>
                  ))}
                </div>
              )}

              {finding.rejected_alternatives && finding.rejected_alternatives.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  <b>Rejected</b>
                  {finding.rejected_alternatives.map((r, i) => (
                    <div key={i}>
                      <span style={mono}>{r.action_type}</span> — {r.reason}
                    </div>
                  ))}
                </div>
              )}

              {finding.evidence && finding.evidence.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  <b>Evidence</b>
                  {finding.evidence.map((e, i) => (
                    <div key={i} style={{ color: e.cited ? "#111" : "#999" }}>
                      [{e.kind}] <span style={mono}>{e.ref}</span>
                      {e.cited ? "" : " (retrieved, not cited)"}
                    </div>
                  ))}
                </div>
              )}

              {finding.checked && finding.checked.length > 0 && (
                <div style={{ marginTop: 8, color: "#555" }}>
                  checked: {finding.checked.join(", ")}
                </div>
              )}
              {finding.degraded_tools && finding.degraded_tools.length > 0 && (
                <div style={{ marginTop: 8, color: "#a5670f" }}>
                  degraded: {finding.degraded_tools.join(", ")}
                </div>
              )}

              <div style={{ color: "#888", marginTop: 8, ...mono }}>trace {finding.trace_id || "—"}</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
