import { useState } from "react";
import type { OpenTrace } from "./App";
import { api, type Finding } from "./api";

const mono: React.CSSProperties = { fontFamily: "ui-monospace, monospace" };
const box: React.CSSProperties = { marginTop: 12, padding: 12, background: "#f7f7f7", borderRadius: 6 };

export default function EngineeringView({ openTrace }: { openTrace: OpenTrace }) {
  const [subject, setSubject] = useState("job-4471");
  const [finding, setFinding] = useState<Finding | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    setError(null);
    setFinding(null);
    try {
      setFinding(await api.diagnose(subject.trim()));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ fontSize: 13, maxWidth: 720 }}>
      <p style={{ color: "#666", fontSize: 12, marginTop: 0 }}>
        Developer Agent — incident mode. Diagnose a platform fault (failing job / degraded service):
        the causing change, the blast radius, and revert vs fix-forward. It proposes a change ticket
        + rerun for a human — it has no deploy / merge / approve tool. Try <span style={mono}>job-4471</span>.
      </p>

      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <input
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          style={{ ...mono, padding: "4px 8px", width: 220 }}
        />
        <button onClick={run} disabled={busy || !subject.trim()}>
          {busy ? "Diagnosing…" : "Diagnose"}
        </button>
      </div>

      {error && <p style={{ color: "#b00" }}>Error: {error}</p>}

      {finding && (
        <div style={box}>
          <div>
            outcome <b>{finding.outcome}</b>
            {finding.root_cause ? (
              <>
                {" "}
                · root cause <b style={mono}>{finding.root_cause}</b>
              </>
            ) : null}
            {finding.fix_strategy ? (
              <>
                {" "}
                · fix <b style={mono}>{finding.fix_strategy}</b>
              </>
            ) : null}
          </div>
          {finding.confidence_basis ? (
            <div style={{ color: "#555", marginTop: 4 }}>{finding.confidence_basis}</div>
          ) : null}

          {finding.blast_radius && finding.blast_radius.length > 0 && (
            <div style={{ marginTop: 8, ...mono, color: "#555" }}>
              blast radius ({finding.blast_radius.length}):{" "}
              {finding.blast_radius.map((s) => s.id).join(", ")}
            </div>
          )}

          {finding.proposed_actions && finding.proposed_actions.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <b>Proposed</b>
              {finding.proposed_actions.map((a, i) => (
                <div key={i}>
                  <span style={mono}>{a.action_type}</span>
                  {a.params && Object.keys(a.params).length > 0 ? (
                    <span style={{ color: "#888", ...mono }}>
                      {" "}
                      {Object.entries(a.params)
                        .map(([k, v]) => `${k}=${v}`)
                        .join(" ")}
                    </span>
                  ) : null}
                  {" — "}
                  {a.rationale}
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

          <div style={{ color: "#888", marginTop: 8, ...mono }}>
            trace{" "}
            {finding.trace_id ? (
              <button
                onClick={() => openTrace(finding.trace_id!)}
                style={{ ...mono, border: "none", background: "none", padding: 0, color: "#1a48c4", cursor: "pointer" }}
              >
                {finding.trace_id}
              </button>
            ) : (
              "—"
            )}
          </div>
        </div>
      )}
    </div>
  );
}
