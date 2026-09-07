import type { components } from "./api-types";

const API = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export type Health = { status: string; service: string };
export type TradeRow = components["schemas"]["TradeRow"];
export type ConnectionsResponse = components["schemas"]["ConnectionsResponse"];
export type Finding = components["schemas"]["Finding"];

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
};
