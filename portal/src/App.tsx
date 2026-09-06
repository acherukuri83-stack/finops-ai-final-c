import { useEffect, useState } from "react";

const API = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

type Health = { status: string; service: string };

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  useEffect(() => {
    fetch(`${API}/health`).then((r) => r.json()).then(setHealth).catch(() => setHealth(null));
  }, []);
  return (
    <main style={{ fontFamily: "system-ui", padding: 24 }}>
      <h1>FinOps AI</h1>
      <nav style={{ display: "flex", gap: 16, marginBottom: 24 }}>
        {["Cases", "Trades", "Settlements", "Knowledge", "Connections", "Traces", "Audit"].map((t) => (
          <span key={t} style={{ color: "#888" }}>{t}</span>
        ))}
      </nav>
      <p>platform-api: {health ? `${health.status} (${health.service})` : "unreachable"}</p>
      <p style={{ color: "#888" }}>Walking skeleton — W1 PR3 replaces this with Trades and Connections.</p>
    </main>
  );
}
