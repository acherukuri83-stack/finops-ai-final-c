import { useState } from "react";
import type { OpenTrace } from "./App";
import { api, type Finding, type Review } from "./api";

const mono: React.CSSProperties = { fontFamily: "ui-monospace, monospace" };
const box: React.CSSProperties = {
  marginTop: 12,
  padding: 12,
  background: "#f7f7f7",
  borderRadius: 6,
};
const SEV_COLOR: Record<string, string> = {
  BLOCKER: "#b00",
  MAJOR: "#a5670f",
  MINOR: "#666",
  NIT: "#999",
};

export default function EngineeringView({
  openTrace,
}: {
  openTrace: OpenTrace;
}) {
  const [subject, setSubject] = useState("job-4471");
  const [ticket, setTicket] = useState("");
  const [pr, setPr] = useState("");
  const [finding, setFinding] = useState<Finding | null>(null);
  const [review, setReview] = useState<Review | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function call(fn: () => Promise<Finding>) {
    setBusy(true);
    setError(null);
    setFinding(null);
    setReview(null);
    try {
      setFinding(await fn());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function runReview() {
    setBusy(true);
    setError(null);
    setFinding(null);
    setReview(null);
    try {
      setReview(await api.review(pr.trim()));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const run = () => call(() => api.diagnose(subject.trim()));
  const verify = () => call(() => api.verify(ticket.trim()));

  return (
    <div className="module-workspace engineering-workspace">
      <p className="module-intro">
        Developer Agent — incident mode. Diagnose a platform fault (failing job
        / degraded service): the causing change, the blast radius, and revert vs
        fix-forward. It proposes a change ticket + rerun for a human — it has no
        deploy / merge / approve tool. Try <span style={mono}>job-4471</span>.
      </p>

      <div className="workflow-grid">
        {" "}
        <div className="workflow-card">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M2 12h4l3-8 6 16 3-8h4" />
          </svg>
          <h3>Diagnose an incident</h3>
          <p>Find the causing change and affected services.</p>
          <input
            aria-label="Incident subject"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            style={{ ...mono, padding: "4px 8px", width: 220 }}
          />
          <button onClick={run} disabled={busy || !subject.trim()}>
            {busy ? "Diagnosing…" : "Diagnose"}
          </button>
        </div>
        <div className="workflow-card">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M4 12l5 5L20 6" />
          </svg>
          <h3>Verify a change</h3>
          <p>Check the outcome of a change ticket.</p>
          <input
            aria-label="Change ticket"
            value={ticket}
            placeholder="CHG-0001"
            onChange={(e) => setTicket(e.target.value)}
            style={{ ...mono, padding: "4px 8px", width: 220 }}
          />
          <button onClick={verify} disabled={busy || !ticket.trim()}>
            {busy ? "Verifying…" : "Verify change ticket"}
          </button>
        </div>
        <div className="workflow-card">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M8 5l-6 7 6 7M16 5l6 7-6 7" />
          </svg>
          <h3>Review a pull request</h3>
          <p>Inspect the proposed code change.</p>
          <input
            aria-label="Pull request"
            value={pr}
            placeholder="PR-19"
            onChange={(e) => setPr(e.target.value)}
            style={{ ...mono, padding: "4px 8px", width: 220 }}
          />
          <button onClick={runReview} disabled={busy || !pr.trim()}>
            {busy ? "Reviewing…" : "Review a PR"}
          </button>
        </div>
      </div>
      {error && (
        <p role="alert" className="module-error">
          Error: {error}
        </p>
      )}

      {review && (
        <div className="result-panel" style={box}>
          <div>
            <span style={mono}>{review.pr_id}</span> · recommendation{" "}
            <b
              style={{
                color: review.recommendation === "APPROVE" ? "#137333" : "#b00",
              }}
            >
              {review.recommendation}
            </b>
          </div>
          <div style={{ color: "#555", marginTop: 4 }}>{review.summary}</div>
          {review.surfaces && review.surfaces.length > 0 && (
            <div style={{ ...mono, color: "#888", marginTop: 4 }}>
              surfaces: {review.surfaces.join(", ")}
            </div>
          )}
          {review.findings && review.findings.length > 0 && (
            <div style={{ marginTop: 8 }}>
              {review.findings.map((f, i) => (
                <div key={i} style={{ marginTop: 4 }}>
                  <b style={{ color: SEV_COLOR[f.severity] ?? "#333" }}>
                    {f.severity}
                  </b>{" "}
                  <span style={mono}>
                    {f.file}
                    {f.line ? `:${f.line}` : ""}
                  </span>{" "}
                  — {f.message}
                  {f.evidence ? (
                    <span style={{ color: "#888" }}> [{f.evidence}]</span>
                  ) : null}
                  {f.suggested_patch ? (
                    <div style={{ color: "#555", ...mono, fontSize: 12 }}>
                      fix: {f.suggested_patch}
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {finding && (
        <div className="result-panel" style={box}>
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
            <div style={{ color: "#555", marginTop: 4 }}>
              {finding.confidence_basis}
            </div>
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

          {finding.rejected_alternatives &&
            finding.rejected_alternatives.length > 0 && (
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
