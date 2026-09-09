import { useCallback, useEffect, useState } from "react";
import type { OpenTrace } from "./App";
import { api, type Approval, type CaseDetail, type CaseRow } from "./api";

const cell: React.CSSProperties = {
  padding: "6px 10px",
  borderBottom: "1px solid #eee",
  textAlign: "left",
};
const mono: React.CSSProperties = { fontFamily: "ui-monospace, monospace" };

const STATUS_COLOR: Record<string, string> = {
  PENDING: "#a5670f",
  APPROVED: "#137333",
  REJECTED: "#b00",
  OPEN: "#1a48c4",
  CLOSED: "#666",
  event: "#6b3fa0",
  user: "#888",
  HIGH: "#b00",
};

function Badge({ value }: { value: string }) {
  return (
    <span
      className="case-badge"
      style={{
        ...mono,
        fontSize: 11,
        padding: "1px 6px",
        borderRadius: 4,
        border: `1px solid ${STATUS_COLOR[value] ?? "#999"}`,
        color: STATUS_COLOR[value] ?? "#999",
      }}
    >
      {value}
    </span>
  );
}

export default function CasesView({ openTrace }: { openTrace: OpenTrace }) {
  const [rows, setRows] = useState<CaseRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [analyst, setAnalyst] = useState("ops.analyst");
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    const load = () =>
      api
        .cases()
        .then(setRows)
        .catch((e: Error) => setError(e.message));
    load();
    const t = setInterval(load, 5000); // event-triggered cases appear without a manual refresh
    return () => clearInterval(t);
  }, []);

  const loadDetail = useCallback(async (id: string) => {
    setSelectedId(id);
    setDetail(null);
    setError(null);
    try {
      setDetail(await api.case(id));
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  async function decide(a: Approval, decision: "APPROVED" | "REJECTED") {
    if (!analyst.trim()) {
      setError("enter your username before deciding");
      return;
    }
    setBusy(a.approval_id);
    setError(null);
    try {
      await api.decide(a.approval_id, {
        decision,
        decided_by: analyst.trim(),
        role: "OPS_ANALYST",
      });
      await Promise.all([loadDetail(a.case_id), api.cases().then(setRows)]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  if (error && !rows) return <p style={{ color: "#b00" }}>Error: {error}</p>;
  if (!rows) return <p style={{ color: "#888" }}>Loading cases…</p>;
  if (rows.length === 0)
    return (
      <p style={{ color: "#888" }}>
        No cases yet. Run an investigation that proposes an action and a case
        opens here.
      </p>
    );

  return (
    <div className="module-workspace split-workspace cases-workspace">
      <div className="workspace-table">
        <h3>
          Case queue <span className="count-label">{rows.length}</span>
        </h3>
        <table style={{ borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr>
              {["Case", "Subject", "Summary", "Source", "Status"].map((h) => (
                <th key={h} style={{ ...cell, color: "#888", fontWeight: 600 }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr
                key={c.case_id}
                onClick={() => loadDetail(c.case_id)}
                style={{
                  cursor: "pointer",
                  background: selectedId === c.case_id ? "#eef4ff" : undefined,
                }}
              >
                <td style={{ ...cell, ...mono }}>
                  <button
                    className="record-link"
                    onClick={(e) => {
                      e.stopPropagation();
                      void loadDetail(c.case_id);
                    }}
                  >
                    {c.case_id}
                  </button>
                </td>
                <td style={{ ...cell, ...mono }}>
                  {c.subject_type}:{c.subject_id}
                </td>
                <td style={cell}>{c.summary}</td>
                <td style={cell}>
                  <Badge value={c.source ?? "user"} />
                  {c.priority === "HIGH" && (
                    <>
                      {" "}
                      <Badge value="HIGH" />
                    </>
                  )}
                </td>
                <td style={cell}>
                  <Badge value={c.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selectedId && (
        <div className="workspace-detail">
          {!detail ? (
            <p style={{ color: "#888" }}>Loading {selectedId}…</p>
          ) : (
            <>
              <h3 style={{ marginTop: 0 }}>
                <span style={mono}>{detail.case_id}</span>{" "}
                <Badge value={detail.status} />{" "}
                <Badge value={detail.source ?? "user"} />
                {detail.priority === "HIGH" && (
                  <>
                    {" "}
                    <Badge value="HIGH" />
                  </>
                )}
              </h3>
              <div style={{ color: "#555" }}>
                {detail.subject_type}{" "}
                <span style={mono}>{detail.subject_id}</span> — {detail.summary}
              </div>
              {detail.trace_id ? (
                <div style={{ marginTop: 4 }}>
                  <button
                    onClick={() => openTrace(detail.trace_id!)}
                    style={{
                      ...mono,
                      border: "none",
                      background: "none",
                      padding: 0,
                      color: "#1a48c4",
                      cursor: "pointer",
                    }}
                  >
                    open trace {detail.trace_id.slice(0, 8)}…
                  </button>
                </div>
              ) : null}

              <div style={{ margin: "10px 0" }}>
                <label style={{ color: "#888" }}>
                  decide as{" "}
                  <input
                    value={analyst}
                    onChange={(e) => setAnalyst(e.target.value)}
                    style={{ ...mono, fontSize: 12, width: 120 }}
                  />{" "}
                  (OPS_ANALYST)
                </label>
              </div>

              <b>Proposed actions</b>
              {detail.approvals.length === 0 && (
                <div style={{ color: "#999" }}>none</div>
              )}
              {detail.approvals.map((a) => (
                <div
                  key={a.approval_id}
                  className="approval-card"
                  style={{
                    marginTop: 8,
                    padding: 10,
                    background: "#f7f7f7",
                    borderRadius: 6,
                  }}
                >
                  <div>
                    <span style={mono}>{a.action_type}</span>{" "}
                    <Badge value={a.status} />
                    {!a.reversible && (
                      <span
                        style={{ color: "#b00", marginLeft: 6, fontSize: 11 }}
                      >
                        irreversible
                      </span>
                    )}
                  </div>
                  <div style={{ color: "#555", marginTop: 4 }}>
                    {a.rationale}
                  </div>
                  {a.impact.length > 0 && (
                    <div
                      style={{
                        color: "#888",
                        marginTop: 4,
                        ...mono,
                        fontSize: 12,
                      }}
                    >
                      impact:{" "}
                      {a.impact
                        .map((i) => `${i.type ?? "?"}:${i.id ?? "?"}`)
                        .join(", ")}
                    </div>
                  )}
                  <div
                    style={{
                      ...mono,
                      fontSize: 12,
                      color: "#888",
                      marginTop: 4,
                    }}
                  >
                    {a.approval_id}
                  </div>
                  {a.status === "PENDING" ? (
                    <div style={{ marginTop: 8, display: "flex", gap: 8 }}>
                      <button
                        disabled={busy === a.approval_id}
                        onClick={() => decide(a, "APPROVED")}
                      >
                        Approve
                      </button>
                      <button
                        disabled={busy === a.approval_id}
                        onClick={() => decide(a, "REJECTED")}
                      >
                        Reject
                      </button>
                    </div>
                  ) : (
                    <div style={{ marginTop: 4, color: "#555" }}>
                      {a.status} by <span style={mono}>{a.decided_by}</span>
                      {a.role ? ` (${a.role})` : ""}
                    </div>
                  )}
                </div>
              ))}

              <div style={{ marginTop: 14 }}>
                <b>Audit</b>
                {detail.trace_id ? (
                  <button
                    onClick={() => openTrace(detail.trace_id!)}
                    style={{ marginLeft: 8, fontSize: 11 }}
                  >
                    view in trace
                  </button>
                ) : null}
                <ol
                  style={{ margin: "4px 0 0", paddingLeft: 18, color: "#555" }}
                >
                  {detail.audit.map((e, i) => (
                    <li key={i}>
                      <span style={{ ...mono, fontSize: 12 }}>{e.at}</span> —{" "}
                      {e.event}
                    </li>
                  ))}
                </ol>
              </div>

              {error && <p style={{ color: "#b00" }}>Error: {error}</p>}
            </>
          )}
        </div>
      )}
    </div>
  );
}
