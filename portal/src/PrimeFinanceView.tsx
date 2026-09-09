import { useState } from "react";
import type { OpenTrace } from "./App";
import { api, type Finding } from "./api";

const mono: React.CSSProperties = { fontFamily: "ui-monospace, monospace" };
const box: React.CSSProperties = { marginTop: 12, padding: 12, background: "#f7f7f7", borderRadius: 6 };

type Domain = "loan" | "margin" | "cash" | "corpaction";

const DOMAINS: { key: Domain; label: string; hint: string; sample: string }[] = [
  { key: "loan", label: "Stock Loan", hint: "a loan id — recall window vs buy-in", sample: "LN-5001" },
  { key: "margin", label: "Margin", hint: "a margin call id — meet vs close-out", sample: "MC-9001" },
  { key: "cash", label: "Cash", hint: "a projected cash break — fund vs escalate", sample: "CB-8001" },
  {
    key: "corpaction",
    label: "Corp Actions",
    hint: "an event id + account id — held/lent split over the record date",
    sample: "CA-7001",
  },
];

export default function PrimeFinanceView({ openTrace }: { openTrace: OpenTrace }) {
  const [domain, setDomain] = useState<Domain>("loan");
  const [id, setId] = useState("LN-5001");
  const [account, setAccount] = useState("ACC-88213");
  const [finding, setFinding] = useState<Finding | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const meta = DOMAINS.find((d) => d.key === domain)!;

  function pick(next: Domain) {
    setDomain(next);
    setId(DOMAINS.find((d) => d.key === next)!.sample);
    setFinding(null);
    setError(null);
  }

  async function run() {
    setBusy(true);
    setError(null);
    setFinding(null);
    try {
      const out =
        domain === "corpaction"
          ? await api.corpaction(id.trim(), account.trim())
          : await api.primeFinance(domain, id.trim());
      setFinding(out);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const ready = domain === "corpaction" ? !!id.trim() && !!account.trim() : !!id.trim();

  return (
    <div style={{ fontSize: 13, maxWidth: 720 }}>
      <p style={{ color: "#666", fontSize: 12, marginTop: 0 }}>
        Prime-finance specialists — Stock Loan, Margin, Cash, and Corp Actions. Each runs the same
        plan → tool loop → synthesise → policy pipeline as Settlement, with its own tool set, its own
        hard rule (recall window, call window, funding cutoff, record date), and its own allowlist.
        They propose; a human approves.
      </p>

      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <select value={domain} onChange={(e) => pick(e.target.value as Domain)} style={{ padding: "4px 8px" }}>
          {DOMAINS.map((d) => (
            <option key={d.key} value={d.key}>
              {d.label}
            </option>
          ))}
        </select>
        <input
          value={id}
          onChange={(e) => setId(e.target.value)}
          placeholder={meta.sample}
          style={{ ...mono, padding: "4px 8px", width: 160 }}
        />
        {domain === "corpaction" && (
          <input
            value={account}
            onChange={(e) => setAccount(e.target.value)}
            placeholder="ACC-88213"
            style={{ ...mono, padding: "4px 8px", width: 160 }}
          />
        )}
        <button onClick={run} disabled={busy || !ready}>
          {busy ? "Investigating…" : "Investigate"}
        </button>
      </div>
      <p style={{ color: "#888", fontSize: 12 }}>{meta.hint}</p>

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
          </div>
          {finding.confidence_basis ? (
            <div style={{ color: "#555", marginTop: 4 }}>{finding.confidence_basis}</div>
          ) : null}

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

          {finding.open_questions && finding.open_questions.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <b>Open questions</b>
              {finding.open_questions.map((q, i) => (
                <div key={i} style={{ color: "#555" }}>
                  {q}
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
