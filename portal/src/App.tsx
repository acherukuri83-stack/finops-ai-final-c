import { useEffect, useState } from "react";
import { api, type Health } from "./api";
import ConnectionsView from "./ConnectionsView";
import KnowledgeView from "./KnowledgeView";
import TradesView from "./TradesView";

const TABS = ["Cases", "Trades", "Settlements", "Knowledge", "Connections", "Traces", "Audit"] as const;
type Tab = (typeof TABS)[number];
const LIVE: ReadonlySet<Tab> = new Set<Tab>(["Trades", "Knowledge", "Connections"]);

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [tab, setTab] = useState<Tab>("Trades");

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
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

      {tab === "Trades" && <TradesView />}
      {tab === "Knowledge" && <KnowledgeView />}
      {tab === "Connections" && <ConnectionsView />}

      <p style={{ color: "#888", marginTop: 32, fontSize: 12 }}>
        platform-api: {health ? `${health.status} (${health.service})` : "unreachable"}
      </p>
    </main>
  );
}
