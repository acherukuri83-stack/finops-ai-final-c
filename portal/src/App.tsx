import { useCallback, useEffect, useState } from "react";
import { api, type Health } from "./api";
import CasesView from "./CasesView";
import ClientView from "./ClientView";
import ConnectionsView from "./ConnectionsView";
import KnowledgeView from "./KnowledgeView";
import TracesView from "./TracesView";
import TradesView from "./TradesView";

const TABS = ["Cases", "Trades", "Client", "Settlements", "Knowledge", "Connections", "Traces", "Audit"] as const;
type Tab = (typeof TABS)[number];
const LIVE: ReadonlySet<Tab> = new Set<Tab>(["Cases", "Trades", "Client", "Knowledge", "Connections", "Traces"]);

export type OpenTrace = (traceId: string, spanId?: string) => void;

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [tab, setTab] = useState<Tab>("Trades");
  const [traceTarget, setTraceTarget] = useState<{ traceId: string; spanId?: string }>();

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
  }, []);

  const openTrace = useCallback<OpenTrace>((traceId, spanId) => {
    setTraceTarget({ traceId, spanId });
    setTab("Traces");
  }, []);

  return (
    <main style={{ fontFamily: "system-ui", padding: 24 }}>
      <h1>FinOps AI</h1>
      <nav style={{ display: "flex", gap: 16, marginBottom: 20 }}>
        {TABS.map((t) =>
          LIVE.has(t) ? (
            <button
              key={t}
              onClick={() => setTab(t)}
              style={{
                border: "none",
                background: "none",
                cursor: "pointer",
                padding: 0,
                fontWeight: tab === t ? 700 : 400,
                color: tab === t ? "#1a48c4" : "#333",
              }}
            >
              {t}
            </button>
          ) : (
            <span key={t} style={{ color: "#bbb" }}>
              {t}
            </span>
          ),
        )}
      </nav>

      {tab === "Cases" && <CasesView openTrace={openTrace} />}
      {tab === "Trades" && <TradesView openTrace={openTrace} />}
      {tab === "Client" && <ClientView openTrace={openTrace} />}
      {tab === "Knowledge" && <KnowledgeView />}
      {tab === "Connections" && <ConnectionsView />}
      {tab === "Traces" && (
        <TracesView initialTraceId={traceTarget?.traceId} focusSpanId={traceTarget?.spanId} />
      )}

      <p style={{ color: "#888", marginTop: 32, fontSize: 12 }}>
        platform-api: {health ? `${health.status} (${health.service})` : "unreachable"}
      </p>
    </main>
  );
}
