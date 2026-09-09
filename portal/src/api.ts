import type { components } from "./api-types";

const API = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export type Health = { status: string; service: string };
export type TradeRow = components["schemas"]["TradeRow"];
export type ConnectionsResponse = components["schemas"]["ConnectionsResponse"];
export type Finding = components["schemas"]["Finding"];
export type Review = components["schemas"]["Review"];
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

// `/wire/*` return plain dicts from `mcp_servers.wire.store` — named here, mirrors that file.
export type WireRow = {
  wire_id: string;
  client_id: string;
  account_id: string;
  direction: string;
  currency: string;
  amount: number;
  beneficiary: string;
  beneficiary_account: string;
  value_date: string;
  status: string;
  hold_reason: string;
};
export type WireQueueItem = {
  wire_id: string;
  action_id: string;
  reviewer: string;
  reason: string;
  packet: string;
};
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
  diagnose: (subjectId: string) => postJSON<Finding>("/diagnose", { subject_id: subjectId }),
  verify: (ticketId: string) => postJSON<Finding>("/verify", { ticket_id: ticketId }),
  review: (prId: string) => postJSON<Review>("/review", { pr_id: prId }),
  primeFinance: (kind: "loan" | "margin" | "cash" | "wire", id: string) => {
    const key =
      kind === "loan"
        ? "loan_id"
        : kind === "margin"
          ? "margin_call_id"
          : kind === "wire"
            ? "wire_id"
            : "cash_break_id";
    return postJSON<Finding>("/investigate", { [key]: id });
  },
  corpaction: (eventId: string, accountId: string) =>
    postJSON<Finding>("/corpaction", { event_id: eventId, account_id: accountId }),
  wireQueue: () => getJSON<WireQueueItem[]>("/wire/queue"),
  wireExceptions: () => getJSON<WireRow[]>("/wire/exceptions"),
  wireRelease: (wireId: string, releasedBy: string) =>
    postJSON<WireRow>("/wire/release", {
      wire_id: wireId,
      released_by: releasedBy,
      role: "WIRE_REVIEWER",
    }),
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
