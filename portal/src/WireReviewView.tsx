import { useCallback, useEffect, useState } from "react";
import { api, type WireQueueItem, type WireRow } from "./api";

const mono: React.CSSProperties = { fontFamily: "ui-monospace, monospace" };
const box: React.CSSProperties = {
  marginTop: 12,
  padding: 12,
  background: "#f7f7f7",
  borderRadius: 6,
};
const th: React.CSSProperties = {
  textAlign: "left",
  padding: "6px 10px",
  borderBottom: "2px solid #ddd",
  fontSize: 12,
  color: "#666",
};
const td: React.CSSProperties = { padding: "6px 10px", borderBottom: "1px solid #eee" };

const fmt = (n: number, ccy: string) =>
  `${n.toLocaleString("en-US")} ${ccy}`;

export default function WireReviewView() {
  const [queue, setQueue] = useState<WireQueueItem[] | null>(null);
  const [exceptions, setExceptions] = useState<WireRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [q, x] = await Promise.all([api.wireQueue(), api.wireExceptions()]);
      setQueue(q);
      setExceptions(x);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function release(wireId: string) {
    setBusy(wireId);
    setNote(null);
    setError(null);
    try {
      const w = await api.wireRelease(wireId, "reviewer.demo");
      setNote(`Released ${w.wire_id} — status ${w.status}. Audit message posted to the wire.`);
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div style={{ fontSize: 13, maxWidth: 900 }}>
      <p style={{ color: "#666", fontSize: 12, marginTop: 0 }}>
        Acting as <b>WIRE_REVIEWER</b>. The Wire specialist is the maker — it routes, reschedules,
        or refers, and never releases. Release is a human-only action here (<span style={mono}>
          POST /wire/release
        </span>); there is no <span style={mono}>release_wire</span> agent tool.
      </p>

      {error && <p style={{ color: "#b00" }}>Error: {error}</p>}
      {note && <p style={{ color: "#137333" }}>{note}</p>}

      <h3 style={{ marginBottom: 4 }}>Reviewer queue</h3>
      <p style={{ color: "#888", fontSize: 12, marginTop: 0 }}>
        Wires routed to a reviewer by the Wire specialist, with the review packet.
      </p>
      {queue?.length === 0 && <p style={{ color: "#888" }}>Queue is empty.</p>}
      {queue && queue.length > 0 && (
        <table style={{ borderCollapse: "collapse", width: "100%" }}>
          <thead>
            <tr>
              <th style={th}>Wire</th>
              <th style={th}>Reason</th>
              <th style={th}>Review packet</th>
              <th style={th} />
            </tr>
          </thead>
          <tbody>
            {queue.map((q) => (
              <tr key={q.action_id}>
                <td style={{ ...td, ...mono }}>{q.wire_id}</td>
                <td style={td}>{q.reason}</td>
                <td style={{ ...td, color: "#555", maxWidth: 380 }}>{q.packet || "—"}</td>
                <td style={td}>
                  <button onClick={() => void release(q.wire_id)} disabled={busy === q.wire_id}>
                    {busy === q.wire_id ? "Releasing…" : "Release"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h3 style={{ marginTop: 24, marginBottom: 4 }}>Wire exception report</h3>
      <p style={{ color: "#888", fontSize: 12, marginTop: 0 }}>
        Every currently held wire and why — the daily exception view.
      </p>
      <div style={box}>
        {exceptions?.length === 0 && <span style={{ color: "#888" }}>No held wires.</span>}
        {exceptions && exceptions.length > 0 && (
          <table style={{ borderCollapse: "collapse", width: "100%" }}>
            <thead>
              <tr>
                <th style={th}>Wire</th>
                <th style={th}>Client</th>
                <th style={th}>Amount</th>
                <th style={th}>Beneficiary</th>
                <th style={th}>Hold reason</th>
                <th style={th}>Value date</th>
              </tr>
            </thead>
            <tbody>
              {exceptions.map((w) => (
                <tr key={w.wire_id}>
                  <td style={{ ...td, ...mono }}>{w.wire_id}</td>
                  <td style={td}>{w.client_id}</td>
                  <td style={{ ...td, ...mono }}>{fmt(w.amount, w.currency)}</td>
                  <td style={td}>
                    {w.beneficiary}{" "}
                    <span style={{ color: "#888", ...mono }}>({w.beneficiary_account})</span>
                  </td>
                  <td style={{ ...td, ...mono }}>{w.hold_reason}</td>
                  <td style={{ ...td, ...mono }}>{w.value_date}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
