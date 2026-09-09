import { useEffect, useRef, useState } from "react";
import type { OpenTrace } from "./App";
import { api, type Finding, type TradeRow } from "./api";

const cell: React.CSSProperties = {
  padding: "6px 10px",
  borderBottom: "1px solid #eee",
  textAlign: "left",
};
const mono: React.CSSProperties = { fontFamily: "ui-monospace, monospace" };

export default function TradesView({ openTrace }: { openTrace: OpenTrace }) {
  const [rows, setRows] = useState<TradeRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<TradeRow | null>(null);
  const [finding, setFinding] = useState<Finding | null>(null);
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState("trade");
  const [detailError, setDetailError] = useState<string | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const request = useRef(0);
  const pageSize = 25;

  useEffect(
    () => () => {
      request.current += 1;
    },
    [],
  );

  const filtered = (rows ?? [])
    .filter(
      (trade) =>
        (!status || (trade.status ?? "UNKNOWN") === status) &&
        [trade.trade_id, trade.client_id, trade.security_id].some((value) =>
          String(value ?? "")
            .toLowerCase()
            .includes(query.trim().toLowerCase()),
        ),
    )
    .sort((a, b) =>
      sort === "date"
        ? String(a.settle_date ?? "").localeCompare(
            String(b.settle_date ?? ""),
          ) || a.trade_id.localeCompare(b.trade_id)
        : sort === "quantity"
          ? Number(b.qty ?? 0) - Number(a.qty ?? 0) ||
            a.trade_id.localeCompare(b.trade_id)
          : a.trade_id.localeCompare(b.trade_id),
    );
  const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const currentPage = Math.min(page, pages);
  const visible = filtered.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize,
  );

  function closeDrawer() {
    request.current += 1;
    setBusy(false);
    dialog.current?.close();
  }

  useEffect(() => {
    api
      .trades()
      .then(setRows)
      .catch((e: Error) => setError(e.message));
  }, []);

  async function open(id: string) {
    const token = ++request.current;
    setSelected(rows?.find((trade) => trade.trade_id === id) ?? null);
    setFinding(null);
    setDetailError(null);
    setBusy(false);
    setLoadingDetail(true);
    dialog.current?.showModal();
    try {
      const trade = await api.trade(id);
      if (request.current === token) setSelected(trade);
    } catch (e) {
      if (request.current === token) setDetailError((e as Error).message);
    } finally {
      if (request.current === token) setLoadingDetail(false);
    }
  }

  async function runInvestigation(id: string) {
    const token = ++request.current;
    setBusy(true);
    setDetailError(null);
    setFinding(null);
    try {
      const result = await api.investigate(id);
      if (request.current === token) setFinding(result);
    } catch (e) {
      if (request.current === token) setDetailError((e as Error).message);
    } finally {
      if (request.current === token) setBusy(false);
    }
  }

  function viewTrace(id: string) {
    closeDrawer();
    openTrace(id);
  }

  if (error) return <p style={{ color: "#b00" }}>Error: {error}</p>;
  if (!rows) return <p style={{ color: "#888" }}>Loading trades…</p>;

  return (
    <div>
      <div className="trade-metrics">
        <div>
          <span>Total trades</span>
          <strong>
            {rows.length}
            <small>In this workspace</small>
          </strong>
        </div>
        <div>
          <span>Failed trades</span>
          <strong>
            {rows.filter((t) => t.status === "FAILED").length}
            <small>Ready for investigation</small>
          </strong>
        </div>
        <div>
          <span>Investigation workflow</span>
          <strong className="metric-label">
            Evidence → decision<small>Agent-assisted analysis</small>
          </strong>
        </div>
      </div>
      <p className="help-banner">
        Try investigating <span style={mono}>T100245</span> (counterparty SSI
        stale) · <span style={mono}>T100261</span> (compliance hold) ·{" "}
        <span style={mono}>T100270</span> (short position)
      </p>
      <div className="trade-toolbar">
        <label className="trade-search">
          Search trades
          <input
            type="search"
            placeholder="Trade, client or security ID"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(1);
            }}
          />
        </label>
        <label>
          Status
          <select
            aria-label="Status"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setPage(1);
            }}
          >
            <option value="">All statuses</option>
            {[
              ...new Set(
                (rows ?? []).map((trade) => trade.status ?? "UNKNOWN"),
              ),
            ]
              .sort()
              .map((value) => (
                <option key={value}>{value}</option>
              ))}
          </select>
        </label>
        <label>
          Sort by
          <select
            aria-label="Sort by"
            value={sort}
            onChange={(event) => {
              setSort(event.target.value);
              setPage(1);
            }}
          >
            <option value="trade">Trade ID</option>
            <option value="date">Settlement date</option>
            <option value="quantity">Quantity: high to low</option>
          </select>
        </label>
        {(query || status) && (
          <button
            onClick={() => {
              setQuery("");
              setStatus("");
              setPage(1);
            }}
          >
            Clear filters
          </button>
        )}
      </div>
      <div className="trade-layout">
        <div className="table-scroll">
          <table style={{ borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr>
                {[
                  "Trade",
                  "Client",
                  "Security",
                  "Qty",
                  "Side",
                  "Status",
                  "Settles",
                ].map((h) => (
                  <th
                    key={h}
                    style={{ ...cell, color: "#888", fontWeight: 600 }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visible.map((t) => (
                <tr
                  key={t.trade_id}
                  onClick={() => open(t.trade_id)}
                  style={{
                    cursor: "pointer",
                    background:
                      selected?.trade_id === t.trade_id ? "#eef4ff" : undefined,
                  }}
                >
                  <td style={{ ...cell, ...mono }}>
                    <button
                      className="trade-link"
                      onClick={(event) => {
                        event.stopPropagation();
                        void open(t.trade_id);
                      }}
                    >
                      {t.trade_id}
                    </button>
                  </td>
                  <td style={cell}>{t.client_id}</td>
                  <td style={cell}>{t.security_id}</td>
                  <td style={{ ...cell, ...mono, textAlign: "right" }}>
                    {t.qty}
                  </td>
                  <td style={cell}>{t.side}</td>
                  <td style={cell}>
                    <span
                      className={`status-badge status-${(t.status ?? "unknown").toLowerCase()}`}
                    >
                      {t.status}
                    </span>
                  </td>
                  <td style={{ ...cell, ...mono }}>{t.settle_date}</td>
                </tr>
              ))}
              {visible.length === 0 && (
                <tr>
                  <td colSpan={7}>
                    <div className="trade-empty">
                      <strong>No matching trades</strong>
                      <p>Try another ID or clear your filters.</p>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <dialog
          ref={dialog}
          className="investigation-drawer"
          aria-labelledby="investigation-title"
          onCancel={closeDrawer}
        >
          <header className="drawer-header">
            <div>
              <p className="eyebrow">INVESTIGATION WORKSPACE</p>
              <h2 id="investigation-title">
                {selected?.trade_id ?? "Trade details"}
              </h2>
            </div>
            <button
              autoFocus
              onClick={closeDrawer}
              aria-label="Close investigation"
            >
              Close
            </button>
          </header>
          {selected && (
            <div className="drawer-body">
              <h3>Trade details</h3>
              {loadingDetail && <p role="status">Loading trade details…</p>}
              {detailError && (
                <p role="alert" className="investigation-error">
                  Request failed: {detailError}. You can retry the investigation
                  or close and reopen this trade.
                </p>
              )}
              <dl
                style={{
                  display: "grid",
                  gridTemplateColumns: "auto 1fr",
                  gap: "4px 12px",
                }}
              >
                {Object.entries(selected).map(([k, v]) => (
                  <div key={k} style={{ display: "contents" }}>
                    <dt style={{ color: "#888" }}>{k}</dt>
                    <dd style={{ margin: 0, ...mono }}>{String(v)}</dd>
                  </div>
                ))}
              </dl>
              <button
                onClick={() => runInvestigation(selected.trade_id)}
                disabled={busy || loadingDetail}
                style={{ marginTop: 12 }}
              >
                {busy
                  ? "Investigation running…"
                  : finding
                    ? "Run again"
                    : "Investigate trade"}
              </button>
              {busy && (
                <div className="investigation-progress" role="status">
                  <strong>Investigation running</strong>
                  <p>
                    Waiting for the agent’s findings. Individual steps will be
                    available in the completed trace.
                  </p>
                  <small>
                    Closing this drawer does not cancel the server
                    investigation.
                  </small>
                </div>
              )}
              {!finding && !busy && (
                <p className="drawer-hint">
                  Run an investigation to review the root cause, supporting
                  evidence and proposed actions.
                </p>
              )}
              {finding && (
                <div
                  style={{
                    marginTop: 12,
                    padding: 12,
                    background: "#f7f7f7",
                    borderRadius: 6,
                  }}
                >
                  <div>
                    <h3>Findings</h3>
                    <span className="status-badge">{finding.outcome}</span>
                    {finding.root_cause ? (
                      <>
                        {" "}
                        · root cause <b style={mono}>{finding.root_cause}</b>
                      </>
                    ) : null}
                  </div>

                  {finding.confidence_basis ? (
                    <div style={{ color: "#555", marginTop: 4 }}>
                      {finding.confidence_basis}
                    </div>
                  ) : null}

                  {finding.proposed_actions &&
                    finding.proposed_actions.length > 0 && (
                      <div style={{ marginTop: 8 }}>
                        <h3>Proposed actions</h3>
                        <p className="drawer-hint">
                          Proposals only. Review approvals in Cases before
                          execution.
                        </p>
                        {finding.proposed_actions.map((a, i) => (
                          <div key={i}>
                            <span style={mono}>{a.action_type}</span> —{" "}
                            {a.rationale}
                          </div>
                        ))}
                      </div>
                    )}

                  {finding.rejected_alternatives &&
                    finding.rejected_alternatives.length > 0 && (
                      <div style={{ marginTop: 8 }}>
                        <h3>Rejected alternatives</h3>
                        {finding.rejected_alternatives.map((r, i) => (
                          <div key={i}>
                            <span style={mono}>{r.action_type}</span> —{" "}
                            {r.reason}
                          </div>
                        ))}
                      </div>
                    )}

                  {finding.evidence && finding.evidence.length > 0 && (
                    <div style={{ marginTop: 8 }}>
                      <h3>Evidence</h3>
                      {finding.evidence.map((e, i) => (
                        <div
                          key={i}
                          style={{ color: e.cited ? "#111" : "#999" }}
                        >
                          [{e.kind}]{" "}
                          {finding.trace_id ? (
                            <button
                              onClick={() => viewTrace(finding.trace_id!)}
                              style={{
                                ...mono,
                                border: "none",
                                background: "none",
                                padding: 0,
                                color: "#1a48c4",
                                cursor: "pointer",
                              }}
                            >
                              {e.ref}
                            </button>
                          ) : (
                            <span style={mono}>{e.ref}</span>
                          )}
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
                  {finding.degraded_tools &&
                    finding.degraded_tools.length > 0 && (
                      <div style={{ marginTop: 8, color: "#a5670f" }}>
                        degraded: {finding.degraded_tools.join(", ")}
                      </div>
                    )}

                  <div style={{ color: "#888", marginTop: 8, ...mono }}>
                    trace{" "}
                    {finding.trace_id ? (
                      <button
                        onClick={() => viewTrace(finding.trace_id!)}
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
          )}
        </dialog>
      </div>
      <div className="trade-pagination">
        <span role="status">
          {filtered.length === 0
            ? "0"
            : `${(currentPage - 1) * pageSize + 1}–${Math.min(currentPage * pageSize, filtered.length)}`}{" "}
          of {filtered.length} trades
        </span>
        <div>
          <button
            disabled={currentPage === 1}
            onClick={() => setPage(currentPage - 1)}
          >
            Previous
          </button>
          <span>
            Page {currentPage} of {pages}
          </span>
          <button
            disabled={currentPage === pages}
            onClick={() => setPage(currentPage + 1)}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
