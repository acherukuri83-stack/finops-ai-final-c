import { useCallback, useEffect, useMemo, useState } from "react";
import { api, type SpanRow, type TraceDetail, type TraceDiff, type TraceSummary } from "./api";

const cell: React.CSSProperties = { padding: "6px 10px", borderBottom: "1px solid #eee", textAlign: "left" };
const mono: React.CSSProperties = { fontFamily: "ui-monospace, monospace" };

const TYPE_COLOR: Record<string, string> = {
  agent: "#1a48c4",
  tool: "#137333",
  retrieval: "#7b1fa2",
  policy: "#a5670f",
  guardrail: "#00838f",
  approval: "#b00",
};

function short(id: string): string {
  return id.length > 12 ? `${id.slice(0, 8)}…` : id;
}
function ms(n: number | null | undefined): string {
  return n == null ? "—" : n >= 1000 ? `${(n / 1000).toFixed(1)}s` : `${n}ms`;
}

function depthOf(spans: SpanRow[]): Map<string, number> {
  const byId = new Map(spans.map((s) => [s.span_id, s]));
  const d = new Map<string, number>();
  const walk = (s: SpanRow): number => {
    if (d.has(s.span_id)) return d.get(s.span_id)!;
    const parent = s.parent_span_id ? byId.get(s.parent_span_id) : undefined;
    const val = parent ? walk(parent) + 1 : 0;
    d.set(s.span_id, val);
    return val;
  };
  spans.forEach(walk);
  return d;
}

function Attr({ k, v }: { k: string; v: unknown }) {
  return (
    <div style={{ display: "contents" }}>
      <dt style={{ color: "#888" }}>{k.replace("finops.", "")}</dt>
      <dd style={{ margin: 0, ...mono, wordBreak: "break-word" }}>
        {typeof v === "string" ? v : JSON.stringify(v)}
      </dd>
    </div>
  );
}

function SpanNode({
  span,
  depth,
  focus,
}: {
  span: SpanRow;
  depth: number;
  focus: boolean;
}) {
  const [open, setOpen] = useState(focus);
  useEffect(() => {
    if (focus) setOpen(true);
  }, [focus]);

  const attrs = (span.attributes ?? {}) as Record<string, unknown>;
  const retrieval = attrs["finops.retrieval.results"];
  const rejected =
    span.step === "synthesize" && span.payload_out && typeof span.payload_out === "object"
      ? ((span.payload_out as Record<string, unknown>).rejected_alternatives as
          | { action_type: string; reason: string }[]
          | undefined)
      : undefined;

  return (
    <div
      id={`span-${span.span_id}`}
      style={{
        marginLeft: depth * 16,
        borderLeft: `2px solid ${TYPE_COLOR[span.span_type] ?? "#ccc"}`,
        padding: "2px 0 2px 8px",
        background: focus ? "#fffbe6" : undefined,
      }}
    >
      <div style={{ cursor: "pointer", display: "flex", gap: 8 }} onClick={() => setOpen(!open)}>
        <span style={{ color: TYPE_COLOR[span.span_type] ?? "#666", fontWeight: 600, fontSize: 11 }}>
          {span.span_type || "span"}
        </span>
        <span style={mono}>{span.name}</span>
        <span style={{ color: "#999", marginLeft: "auto" }}>{ms(span.duration_ms)}</span>
        {attrs["finops.model"] ? (
          <span style={{ color: "#999" }}>
            {String(attrs["finops.model"]).replace("claude-", "")} ·{" "}
            {String(attrs["finops.tokens.in"] ?? "?")}/{String(attrs["finops.tokens.out"] ?? "?")} tok
          </span>
        ) : null}
        {span.status && span.status !== "OK" && span.status !== "UNSET" ? (
          <span style={{ color: "#b00" }}>{span.status}</span>
        ) : null}
      </div>

      {open && (
        <div style={{ margin: "4px 0 8px", fontSize: 12 }}>
          {Array.isArray(retrieval) && (
            <div style={{ marginBottom: 6 }}>
              <b>retrieved</b>
              {(retrieval as Record<string, unknown>[]).map((r, i) => (
                <div key={i} style={mono}>
                  {String(r.score ?? r.similarity ?? "")} {String(r.doc ?? r.incident_id ?? "")}{" "}
                  {String(r.section ?? "")}
                </div>
              ))}
            </div>
          )}
          {rejected && rejected.length > 0 && (
            <div style={{ marginBottom: 6 }}>
              <b>rejected alternatives</b>
              {rejected.map((r, i) => (
                <div key={i}>
                  <span style={mono}>{r.action_type}</span> — {r.reason}
                </div>
              ))}
            </div>
          )}
          {(span.payload_in != null || span.payload_out != null) && (
            <pre
              style={{
                background: "#f7f7f7",
                borderRadius: 4,
                padding: 8,
                overflowX: "auto",
                whiteSpace: "pre-wrap",
              }}
            >
              {JSON.stringify({ in: span.payload_in, out: span.payload_out }, null, 2)}
            </pre>
          )}
          {Object.keys(attrs).length > 0 && (
            <dl style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "2px 12px" }}>
              {Object.entries(attrs)
                .filter(([k]) => k !== "finops.retrieval.results")
                .map(([k, v]) => (
                  <Attr key={k} k={k} v={v} />
                ))}
            </dl>
          )}
        </div>
      )}
    </div>
  );
}

function DiffView({ diff }: { diff: TraceDiff }) {
  const row = (label: string, a: unknown, b: unknown) => (
    <tr>
      <td style={{ ...cell, color: "#888" }}>{label}</td>
      <td style={cell}>{typeof a === "string" ? a : JSON.stringify(a)}</td>
      <td style={cell}>{typeof b === "string" ? b : JSON.stringify(b)}</td>
    </tr>
  );
  return (
    <div style={{ fontSize: 13 }}>
      <h4>
        diff <span style={mono}>{short(diff.a)}</span> vs <span style={mono}>{short(diff.b)}</span>
        {diff.same_scenario ? "" : " (different scenarios)"}
      </h4>
      <table style={{ borderCollapse: "collapse" }}>
        <tbody>
          {row("root cause", diff.root_cause.a, diff.root_cause.b)}
          {row("outcome", diff.outcome.a, diff.outcome.b)}
          {row("proposed", diff.proposed_actions.a, diff.proposed_actions.b)}
          {row("tools added (b)", "", (diff.tool_calls_added ?? []).join(", "))}
          {row("tools removed (b)", (diff.tool_calls_removed ?? []).join(", "), "")}
          {row("reordered", "", String(diff.tool_calls_reordered))}
          {row("tokens Δ", "", diff.tokens_delta)}
          {row("duration Δ", "", ms(diff.duration_ms_delta))}
          {row("cost Δ", "", `$${(diff.cost_usd_delta ?? 0).toFixed(4)}`)}
        </tbody>
      </table>
      {(diff.retrieval_delta ?? []).length > 0 && (
        <div style={{ marginTop: 8 }}>
          <b>retrieval delta</b>
          {(diff.retrieval_delta as Record<string, unknown>[]).map((r, i) => (
            <div key={i} style={mono}>
              {String(r.only_in)}: {String(r.doc ?? r.incident_id ?? "")} {String(r.section ?? "")}{" "}
              {String(r.score ?? "")}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function TracesView({
  initialTraceId,
  focusSpanId,
}: {
  initialTraceId?: string;
  focusSpanId?: string;
}) {
  const [list, setList] = useState<TraceSummary[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(initialTraceId ?? null);
  const [detail, setDetail] = useState<TraceDetail | null>(null);
  const [diff, setDiff] = useState<TraceDiff | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [focusSpan, setFocusSpan] = useState<string | undefined>(focusSpanId);

  const refreshList = useCallback(() => {
    api.traces().then(setList).catch((e: Error) => setError(e.message));
  }, []);
  useEffect(refreshList, [refreshList]);
  useEffect(() => {
    if (initialTraceId) setSelectedId(initialTraceId);
  }, [initialTraceId]);

  useEffect(() => {
    if (!selectedId) return;
    setDetail(null);
    setDiff(null);
    api.trace(selectedId).then(setDetail).catch((e: Error) => setError(e.message));
  }, [selectedId]);

  useEffect(() => {
    if (detail && focusSpan) {
      document.getElementById(`span-${focusSpan}`)?.scrollIntoView({ block: "center" });
    }
  }, [detail, focusSpan]);

  useEffect(() => setFocusSpan(focusSpanId), [focusSpanId]);

  const depths = useMemo(() => (detail ? depthOf(detail.spans) : new Map()), [detail]);
  const sameScenario = useMemo(
    () =>
      detail?.scenario_id
        ? (list ?? []).filter((t) => t.scenario_id === detail.scenario_id && t.trace_id !== detail.trace_id)
        : [],
    [list, detail],
  );

  async function replay() {
    if (!detail) return;
    setBusy("replay");
    setError(null);
    try {
      const r = await api.replayTrace(detail.trace_id);
      refreshList();
      setSelectedId(r.replay_trace_id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function runDiff(other: string) {
    if (!detail) return;
    setBusy("diff");
    try {
      setDiff(await api.diffTraces(other, detail.trace_id));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  if (error && !list) return <p style={{ color: "#b00" }}>Error: {error}</p>;
  if (!list) return <p style={{ color: "#888" }}>Loading traces…</p>;

  return (
    <div style={{ display: "flex", gap: 24, alignItems: "flex-start" }}>
      <table style={{ borderCollapse: "collapse", fontSize: 12, flexShrink: 0 }}>
        <thead>
          <tr>
            {["Trace", "Subject", "Outcome", "Dur", "$"].map((h) => (
              <th key={h} style={{ ...cell, color: "#888" }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {list.map((t) => (
            <tr
              key={t.trace_id}
              onClick={() => setSelectedId(t.trace_id)}
              style={{ cursor: "pointer", background: selectedId === t.trace_id ? "#eef4ff" : undefined }}
            >
              <td style={{ ...cell, ...mono }}>{short(t.trace_id)}</td>
              <td style={cell}>{t.subject_id}</td>
              <td style={cell}>{t.root_cause || t.outcome}</td>
              <td style={{ ...cell, ...mono }}>{ms(t.duration_ms)}</td>
              <td style={{ ...cell, ...mono }}>{(t.cost_usd ?? 0).toFixed(3)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {selectedId && (
        <div style={{ fontSize: 13, minWidth: 420, flex: 1 }}>
          {!detail ? (
            <p style={{ color: "#888" }}>Loading {short(selectedId)}…</p>
          ) : (
            <>
              <div style={{ color: "#555" }}>
                <span style={mono}>{detail.trace_id}</span>
                {detail.case_id ? (
                  <>
                    {" · case "}
                    <span style={mono}>{detail.case_id}</span>
                  </>
                ) : null}
              </div>
              <div style={{ color: "#555", margin: "4px 0 10px" }}>
                {detail.status} · {ms(detail.duration_ms)} · {detail.tool_calls} tools ·{" "}
                {detail.retrievals} retrievals · {detail.model_calls} model calls ·{" "}
                {detail.tokens_in + detail.tokens_out} tokens · ${(detail.cost_usd ?? 0).toFixed(4)}
              </div>

              <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
                <a href={api.traceExportUrl(detail.trace_id)} target="_blank" rel="noreferrer">
                  <button>Export JSON</button>
                </a>
                <button disabled={busy === "replay"} onClick={replay}>
                  {busy === "replay" ? "Replaying…" : "Replay"}
                </button>
                {sameScenario.length > 0 && (
                  <select
                    defaultValue=""
                    onChange={(e) => e.target.value && runDiff(e.target.value)}
                    disabled={busy === "diff"}
                  >
                    <option value="">Diff vs…</option>
                    {sameScenario.map((t) => (
                      <option key={t.trace_id} value={t.trace_id}>
                        {short(t.trace_id)} — {t.root_cause || t.outcome}
                      </option>
                    ))}
                  </select>
                )}
              </div>

              {diff && (
                <div style={{ border: "1px solid #eee", borderRadius: 6, padding: 10, marginBottom: 12 }}>
                  <DiffView diff={diff} />
                </div>
              )}

              {detail.links.length > 0 && (
                <div style={{ marginBottom: 10, fontSize: 12 }}>
                  <b>evidence</b>{" "}
                  {detail.links.map((l) => (
                    <button
                      key={l.ref}
                      onClick={() => {
                        setFocusSpan(l.span_id);
                        document
                          .getElementById(`span-${l.span_id}`)
                          ?.scrollIntoView({ block: "center" });
                      }}
                      style={{ margin: "0 4px 4px 0" }}
                    >
                      {l.ref}
                    </button>
                  ))}
                </div>
              )}

              <div>
                {detail.spans.map((s) => (
                  <SpanNode
                    key={s.span_id}
                    span={s}
                    depth={depths.get(s.span_id) ?? 0}
                    focus={s.span_id === focusSpan}
                  />
                ))}
              </div>
              {error && <p style={{ color: "#b00" }}>Error: {error}</p>}
            </>
          )}
        </div>
      )}
    </div>
  );
}
