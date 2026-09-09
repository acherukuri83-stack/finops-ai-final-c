import { useCallback, useEffect, useState } from "react";
import { api, type Health } from "./api";
import CasesView from "./CasesView";
import ClientView from "./ClientView";
import ConnectionsView from "./ConnectionsView";
import EngineeringView from "./EngineeringView";
import KnowledgeView from "./KnowledgeView";
import PrimeFinanceView from "./PrimeFinanceView";
import TracesView from "./TracesView";
import TradesView from "./TradesView";
import "./styles.css";

const TABS = [
  "Cases",
  "Trades",
  "Client",
  "Prime Finance",
  "Engineering",
  "Settlements",
  "Knowledge",
  "Connections",
  "Traces",
  "Audit",
] as const;
type Tab = (typeof TABS)[number];
const LIVE: ReadonlySet<Tab> = new Set<Tab>([
  "Cases",
  "Trades",
  "Client",
  "Prime Finance",
  "Engineering",
  "Knowledge",
  "Connections",
  "Traces",
]);

const DETAILS: Record<Tab, [string, string]> = {
  Trades: [
    "Trade intelligence",
    "Investigate exceptions. Understand the evidence. Decide with confidence.",
  ],
  Cases: [
    "Case workspace",
    "Review findings, evaluate proposed actions and manage approvals.",
  ],
  Client: [
    "Client intelligence",
    "Bring specialist findings together for a complete client investigation.",
  ],
  "Prime Finance": [
    "Prime finance",
    "Investigate stock lending, margin, corporate actions and cash with specialist agents.",
  ],
  Engineering: [
    "Engineering",
    "Diagnose incidents, verify changes, review PRs and draft evaluations.",
  ],
  Knowledge: [
    "Knowledge library",
    "Find the procedures and source evidence behind every decision.",
  ],
  Connections: [
    "Connected tools",
    "Explore the services and capabilities available to your agents.",
  ],
  Traces: [
    "Agent observability",
    "Follow the reasoning, tool calls and evidence across an investigation.",
  ],
  Settlements: ["Settlements", ""],
  Audit: ["Audit", ""],
};
const ICONS: Record<Tab, string> = {
  Trades: "M4 17l5-5 4 3 7-10M15 5h5v5",
  Cases: "M3 7h7l2 2h9v11H3zM3 7V4h7l2 3",
  Client:
    "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M17 4a4 4 0 0 1 0 8M22 21v-2a4 4 0 0 0-3-4",
  "Prime Finance": "M3 21h18M5 21V10h4v11M10 21V4h4v17M15 21v-7h4v7",
  Engineering: "M8 5L2 12l6 7M16 5l6 7-6 7M14 3l-4 18",
  Knowledge:
    "M12 5v16M12 5C8 2 4 3 2 4v15c4-1 7-1 10 2 3-3 6-3 10-2V4c-2-1-6-2-10 1",
  Connections: "M8 12h8M8 8V4H2v6h6M16 14v6h6v-6h-6M5 10v7h11",
  Traces: "M2 12h4l3-8 6 16 3-8h4",
  Settlements: "M4 7h16l-4-4M20 17H4l4 4",
  Audit: "M5 3h14v18H5zM8 8h8M8 12h8M8 16h5",
};

export type OpenTrace = (traceId: string, spanId?: string) => void;

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [tab, setTab] = useState<Tab>("Trades");
  const [traceTarget, setTraceTarget] = useState<{
    traceId: string;
    spanId?: string;
  }>();

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  const openTrace = useCallback<OpenTrace>((traceId, spanId) => {
    setTraceTarget({ traceId, spanId });
    setTab("Traces");
  }, []);

  return (
    <div className="app-shell">
      <a className="skip-link" href="#workspace">
        Skip to workspace
      </a>
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">
            f<span> /</span>
          </span>
          <div>
            FinOps<span className="brand-sub">AGENT WORKSPACE</span>
          </div>
        </div>
        <div className="nav-label">WORKSPACE</div>
        <nav aria-label="Main navigation">
          {TABS.map((t) => (
            <button
              key={t}
              className={`nav-item ${tab === t ? "active" : ""}`}
              disabled={!LIVE.has(t)}
              aria-current={tab === t ? "page" : undefined}
              onClick={() => setTab(t)}
            >
              <svg
                width="19"
                height="19"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d={ICONS[t]} />
              </svg>
              <span>{t}</span>
              {!LIVE.has(t) && <small>Soon</small>}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <span className="workspace-avatar">S</span>
          <div>
            Simulation workspace<small>FinOps AI · Portal</small>
          </div>
        </div>
      </aside>
      <div className="main-column">
        <header className="topbar">
          <div>
            Workspace <span className="breadcrumb-divider">/</span>{" "}
            <strong>{tab}</strong>
          </div>
          <div
            className={`health-chip ${health ? "connected" : "offline"}`}
            role="status"
          >
            <span />
            {health ? `API · ${health.status}` : "API unavailable"}
          </div>
        </header>
        <main id="workspace" className="workspace" tabIndex={-1}>
          <div className="page-heading">
            <div>
              <p className="eyebrow">OPERATIONS / {tab.toUpperCase()}</p>
              <h1>{DETAILS[tab][0]}</h1>
              <p className="page-description">{DETAILS[tab][1]}</p>
            </div>
            <span className="environment-tag">SIMULATED DATA</span>
          </div>
          <section className="view-panel" aria-label={DETAILS[tab][0]}>
            {tab === "Cases" && <CasesView openTrace={openTrace} />}
            {tab === "Trades" && <TradesView openTrace={openTrace} />}
            {tab === "Client" && <ClientView openTrace={openTrace} />}
            {tab === "Prime Finance" && (
              <PrimeFinanceView openTrace={openTrace} />
            )}
            {tab === "Engineering" && <EngineeringView openTrace={openTrace} />}
            {tab === "Knowledge" && <KnowledgeView />}
            {tab === "Connections" && <ConnectionsView />}
            {tab === "Traces" && (
              <TracesView
                initialTraceId={traceTarget?.traceId}
                focusSpanId={traceTarget?.spanId}
              />
            )}
          </section>
          <footer className="workspace-footer">
            <span>FinOps AI</span>
            <span>Evidence-led operations · Human oversight</span>
          </footer>
        </main>
      </div>
    </div>
  );
}
