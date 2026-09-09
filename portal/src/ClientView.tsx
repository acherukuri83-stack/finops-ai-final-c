import { useState } from "react";
import type { OpenTrace } from "./App";
import { api, type Finding } from "./api";

const mono: React.CSSProperties = { fontFamily: "ui-monospace, monospace" };
const box: React.CSSProperties = {
  marginTop: 12,
  padding: 12,
  background: "#f7f7f7",
  borderRadius: 6,
};

export default function ClientView({ openTrace }: { openTrace: OpenTrace }) {
  const [clientId, setClientId] = useState("HEDGE_FUND_101");
  const [finding, setFinding] = useState<Finding | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    setError(null);
    setFinding(null);
    try {
      setFinding(await api.investigateClient(clientId.trim()));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="module-workspace client-workspace">
      <p className="module-intro">
        A client-level question fans out across specialists (Settlement ·
        Risk/Client), correlates the findings by shared cause, and opens one
        case. Try <span style={mono}>HEDGE_FUND_101</span> (scenario 11: three
        counterparty SSI fails + one short position).
      </p>

      <div className="module-form">
        <div className="form-caption">
          <strong>Client investigation</strong>
          <span>Coordinate specialist findings for one client.</span>
        </div>
        <input
          aria-label="Client ID"
          value={clientId}
          onChange={(e) => setClientId(e.target.value)}
          style={{ ...mono, padding: "4px 8px", width: 260 }}
        />
        <button onClick={run} disabled={busy || !clientId.trim()}>
          {busy ? "Investigating…" : "Investigate client"}
        </button>
      </div>

      {error && (
        <p role="alert" className="module-error">
          Error: {error}
        </p>
      )}

      {finding && (
        <div className="result-panel" style={box}>
          <div>
            outcome <b>{finding.outcome}</b>
            {finding.subject ? (
              <>
                {" "}
                ·{" "}
                <span style={mono}>
                  {finding.subject.type}:{finding.subject.id}
                </span>
              </>
            ) : null}
          </div>
          {finding.confidence_basis ? (
            <div style={{ color: "#555", marginTop: 4 }}>
              {finding.confidence_basis}
            </div>
          ) : null}

          {finding.proposed_actions && finding.proposed_actions.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <b>Grouped actions</b>
              {finding.proposed_actions.map((a, i) => (
                <div key={i} style={{ marginTop: 4 }}>
                  <span style={mono}>{a.action_type}</span>
                  {a.proposed_by ? (
                    <span style={{ color: "#888" }}> · {a.proposed_by}</span>
                  ) : null}
                  {" — "}
                  {a.rationale}
                  {a.impact && a.impact.length > 0 && (
                    <div style={{ color: "#555", ...mono }}>
                      impact: {a.impact.map((s) => s.id).join(", ")}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {finding.open_questions && finding.open_questions.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <b>Open questions</b>
              {finding.open_questions.map((q, i) => (
                <div key={i} style={{ color: "#a5670f" }}>
                  {q}
                </div>
              ))}
            </div>
          )}

          {finding.sub_findings && finding.sub_findings.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <b>Sub-findings</b>
              {finding.sub_findings.map((sf, i) => (
                <details className="specialist-finding" key={i}>
                  <summary style={mono}>
                    {sf.subject?.type}:{sf.subject?.id} — {sf.outcome}
                    {sf.root_cause ? ` · ${sf.root_cause}` : ""}
                  </summary>
                  <div style={{ padding: "4px 0 4px 16px" }}>
                    {sf.proposed_actions?.map((a, j) => (
                      <div key={j}>
                        <span style={mono}>{a.action_type}</span> —{" "}
                        {a.rationale}
                      </div>
                    ))}
                    {sf.rejected_alternatives?.map((r, j) => (
                      <div key={j} style={{ color: "#888" }}>
                        rejected <span style={mono}>{r.action_type}</span> —{" "}
                        {r.reason}
                      </div>
                    ))}
                  </div>
                </details>
              ))}
            </div>
          )}

          <div style={{ color: "#888", marginTop: 10, ...mono }}>
            trace{" "}
            {finding.trace_id ? (
              <button
                onClick={() => openTrace(finding.trace_id!)}
                style={{
                  ...mono,
                  border: "none",
                  background: "none",
                  padding: 0,
                  color: "#1a48c4",
                  cursor: "pointer",
                }}
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
