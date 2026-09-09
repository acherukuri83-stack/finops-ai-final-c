import { useEffect, useState } from "react";
import { api, type ConnectionsResponse } from "./api";

const cell: React.CSSProperties = {
  padding: "6px 10px",
  borderBottom: "1px solid #eee",
  textAlign: "left",
  verticalAlign: "top",
};
const mono: React.CSSProperties = { fontFamily: "ui-monospace, monospace" };

function Dot({ ok }: { ok: boolean }) {
  return (
    <span
      title={ok ? "reachable" : "unreachable"}
      style={{
        display: "inline-block",
        width: 8,
        height: 8,
        borderRadius: 4,
        background: ok ? "#1a8f5f" : "#b00",
        marginRight: 6,
      }}
    />
  );
}

export default function ConnectionsView() {
  const [data, setData] = useState<ConnectionsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .connections()
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, []);

  if (error) return <p style={{ color: "#b00" }}>Error: {error}</p>;
  if (!data) return <p style={{ color: "#888" }}>Loading connections…</p>;

  return (
    <div className="module-workspace connections-workspace">
      <p style={{ color: "#888" }}>
        enterprise <span style={mono}>{data.enterprise_base_url}</span> &nbsp;
        <Dot ok={data.healthy} />
        {data.healthy ? "reachable" : "unreachable"}
      </p>
      <div className="module-stats">
        <div>
          <strong>{data.servers.length}</strong>
          <span>Connected service definitions</span>
        </div>
        <div>
          <strong>{data.servers.filter((s) => s.healthy).length}</strong>
          <span>Reachable services</span>
        </div>
        <div>
          <strong>
            {data.servers.reduce((sum, s) => sum + s.tools.length, 0)}
          </strong>
          <span>Available tool definitions</span>
        </div>
      </div>
      {data.servers.map((s) => (
        <div key={s.name} className="service-card">
          <h3 style={{ margin: "0 0 4px" }}>
            <Dot ok={s.healthy} />
            {s.name}-server{" "}
            <span style={{ color: "#888", fontWeight: 400 }}>· {s.access}</span>
          </h3>
          <p className="service-meta">
            {s.tools.length} tools · {s.healthy ? "Reachable" : "Unavailable"}
          </p>
          <table
            style={{ borderCollapse: "collapse", width: "100%", maxWidth: 820 }}
          >
            <thead>
              <tr>
                {["Tool", "Access", "Description"].map((h) => (
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
              {s.tools.map((t) => (
                <tr key={t.name}>
                  <td style={{ ...cell, ...mono }}>{t.name}</td>
                  <td style={cell}>{t.access}</td>
                  <td style={{ ...cell, color: "#444" }}>{t.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}
