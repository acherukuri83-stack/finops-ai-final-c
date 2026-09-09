import type { components } from "./api-types";

const API = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export type Health = { status: string; service: string };
export type TradeRow = components["schemas"]["TradeRow"];
export type ConnectionsResponse = components["schemas"]["ConnectionsResponse"];
export type Finding = components["schemas"]["Finding"];
export type KnowledgeHit = components["schemas"]["KnowledgeHit"];
export type DecideRequest = components["schemas"]["DecideRequest"];

// `/cases` returns plain dicts (platform_api.cases) — the generator can't infer the
// shape, so name it here. Mirrors `platform_api/cases.py`.
export type CaseRow = {
  case_id: string;
  subject_type: string;
  subject_id: string;
  summary: string;
  status: string;
  source: "user" | "event";
  priority: "NORMAL" | "HIGH";
  dedup_key: string | null;
  created_at: string;
};
export type Approval = {
  approval_id: string;
  case_id: string;
  action_type: string;
  params: Record<string, string>;
  rationale: string;
  impact: { type?: string; id?: string }[];
  reversible: boolean;
  status: "PENDING" | "APPROVED" | "REJECTED";
  decided_by: string | null;
  role: string | null;
  decided_at: string | null;
  created_at: string;
};
export type AuditEvent = { case_id: string; event: string; at: string };
export type CaseDetail = CaseRow & { trace_id?: string; approvals: Approval[]; audit: AuditEvent[] };

export type TraceSummary = components["schemas"]["TraceSummary"];
export type SpanRow = components["schemas"]["SpanRow"];
export type TraceDetail = components["schemas"]["TraceDetail"];
export type TraceDiff = components["schemas"]["TraceDiff"];
export type TraceReplay = components["schemas"]["TraceReplay"];

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

export const api = {
  health: () => getJSON<Health>("/health"),
  trades: () => getJSON<TradeRow[]>("/trades"),
  trade: (id: string) => getJSON<TradeRow>(`/trades/${encodeURIComponent(id)}`),
  connections: () => getJSON<ConnectionsResponse>("/connections"),
  investigate: (tradeId: string) => postJSON<Finding>("/investigate", { trade_id: tradeId }),
  investigateClient: (clientId: string) =>
    postJSON<Finding>("/investigate", { client_id: clientId }),
  knowledge: (q: string) => getJSON<KnowledgeHit[]>(`/knowledge?q=${encodeURIComponent(q)}`),
  cases: () => getJSON<CaseRow[]>("/cases"),
  case: (id: string) => getJSON<CaseDetail>(`/cases/${encodeURIComponent(id)}`),
  decide: (approvalId: string, body: DecideRequest) =>
    postJSON<Approval>(`/approvals/${encodeURIComponent(approvalId)}/decide`, body),
  traces: (params: { case_id?: string; scenario_id?: string } = {}) => {
    const q = new URLSearchParams(params as Record<string, string>).toString();
    return getJSON<TraceSummary[]>(`/traces${q ? `?${q}` : ""}`);
  },
  trace: (id: string) => getJSON<TraceDetail>(`/traces/${encodeURIComponent(id)}`),
  traceExportUrl: (id: string) => `${API}/traces/${encodeURIComponent(id)}/export`,
  replayTrace: (id: string) => postJSON<TraceReplay>(`/traces/${encodeURIComponent(id)}/replay`, {}),
  diffTraces: (a: string, b: string) =>
    getJSON<TraceDiff>(`/traces/diff?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`),
};
