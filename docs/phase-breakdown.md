# FinOps AI — Phase Breakdown (A → G)

Every phase in the same shape: what it proves, what's in scope, which agents exist, which tools, data, corpus, screens, governance, scenarios, and what you can demo at the end. Cumulative — each phase adds to the previous one.

**Mainline sequence: A → C → D → E → F → G.** **Phase B — Wires is an optional module**: it depends only on Phase A, nothing in C–G depends on it, and it can be built at any point after A (or never). Phase A is complete and deployed; the next mainline phase is C.

**This is the canonical full-scope reference — read this first for orientation.** For execution-level detail (weekend-by-weekend build steps, exit criteria) one phase at a time: Phase A → `docs/final-plan.md`. Phases C–F → `docs/build-plan.md` / `docs/agent-plan.md`, phases 9 (C), 10 (D), 11–12 (E), 13 (F) respectively; the optional Wires module is phase 7 (B) in those files — **phases 0–6 and 8 there are superseded**, absorbed into Phase A by `final-plan.md`; don't treat them as open work. Phase G has no further detail written yet.

## At a glance

| Phase | Theme | Agents (cumulative) | MCP servers (cumulative) | Scenarios | Concepts showcased | Effort |
|---|---|---|---|---|---|---|
| **A** ✅ | One trade use case, end to end | Investigator | trade, client, counterparty, position, reference, market, compliance (r), ops, case | 1–6, 8–10, 12 | LLM · RAG · MCP · Agentic (single) · Platform · Governance · Evals · Trace | 5 weekends — done |
| **C** | Supervisor & specialists | Supervisor, Settlement, Wire, Risk/Client, Knowledge | — | 11 | Delegation · correlation · policy per agent | 1–2 weekends |
| **D** | Event-driven | + event entry | — (EventBus) | event scenarios | Platform reacts unprompted · dedup | 1 weekend |
| **E** | Developer Agent | + Developer (incident, verify, review, author) | + platform, repo, ci | 17–25 | Engineering agents · closed loop · self-review | 2–3 weekends |
| **F** | Prime finance | + StockLoan, Margin, CorpActions, Cash | + stockloan, margin, corpactions, cash | 26–30 | Domain depth from your background | 1 weekend/domain |
| **G** | Hardening | — | — | — | Replay/diff · AWS path · model swaps | as needed |
| **B** | Wires — *optional module* | + wire mode | + wire, compliance (w) | 7, 13–16 | Maker–checker · hard rules · second vertical on same substrate | 1–2 weekends · optional, depends only on A |

---

## Phase A — "Why didn't this trade settle?"

**Proves:** all five concepts plus governance, evaluation, and observability — on one use case, publicly hosted.

| | |
|---|---|
| **Scope in** | Trade settlement failure investigation, approval-gated remediation, evidence with citations, trace, audit, eval scorecard, Railway demo |
| **Scope out** | Wires, multi-agent, events, engineering agents, prime-finance domains, replay/diff, AWS |
| **Agent** | **Investigator** — trade mode. Plan → tool loop (budget 12) → `Finding` with rejected alternatives → policy → propose. Outcomes: `RESOLVED_CAUSE`, `INSUFFICIENT_EVIDENCE`, `TOOL_DEGRADED`. Allowlist: `resubmit_settlement`, `cancel_trade`, `update_ssi`, `open_compliance_referral`, `escalate` |
| **MCP servers / tools** | `trade`: get_trade, get_settlement_status, find_trades, resubmit_settlement (w), cancel_trade (w) · `client`: get_client, get_account, get_ssi, get_ssi_history, update_ssi (w) · `counterparty`: get_counterparty, get_counterparty_ssi, get_affirmation · `position`: get_position, get_borrow_availability · `reference`: get_security, get_market_calendar · `market`: get_price · `compliance`: get_restrictions, get_screening_result · `ops`: search_logs, search_knowledge, find_incidents · `case`: create_case, update_case, propose_action, get_approval, log_audit |
| **Simulated data** | ~50 clients, ~80 accounts, SSIs with history, ~200 securities, 30 days prices, ~500 trades (95% clean, several failed for *other* reasons), affirmations, positions, borrow availability, ~20 counterparties, ~20k log lines; per-scenario plants with 3–8 corroborating logs |
| **Corpus** | ~12 SOPs (settlement failure handbook, SSI policy, trade exception procedure, reference data procedure, delivery/position procedure, incident management, account restrictions, custodian notices), `INC-1001…1008`, 2–3 distractor sections |
| **Portal** | Cases · Trades · Settlements · Knowledge · Connections · Traces · Audit; chat + investigation panel + evidence; Approve/Reject; role `OPS_ANALYST` |
| **Governance** | Approval enforced at the write tool via `approval_id`; policy allowlist; audit per case; input classification guardrail; output schema validation |
| **Observability** | Spans: agent, tool, retrieval, policy, guardrail, approval; Agent Trace screen with retrieved-vs-cited and rejected alternatives; cross-links |
| **Evals** | 10 scenarios × 3 runs; scorecard; CI gate on `prompts/`, `policy/`, `knowledge/`, `simulator/` |
| **Scenarios** | 1 counterparty SSI stale · 2 our SSI stale (KB flips) · 3 reference error · 4 restricted account · 5 short position · 6 expired instruction · 8 duplicate · 9 remediated · 10 no evidence · 12 tool outage |
| **Demo** | Investigate T100245 → evidence §8.4 + INC-1001 → `update_ssi` rejected → approve → audit · Sc. 4 restraint · Sc. 2 flip · trace · scorecard |
| **Deliverables** | Public repo, hosted demo, 4-minute video, scorecard in README, ADRs |

---

## Phase B — Wires

> **Optional module — off the critical path.** Build whenever a second write-heavy vertical (maker–checker, cutoffs, screening) is wanted. It depends only on Phase A; nothing in C–G depends on it. Deferring it defers the pure maker–checker / human-only-release demo.

**Proves:** the substrate supports a second vertical with different controls — maker–checker, standing instructions, cutoffs, screening — without touching Phase A code.

| | |
|---|---|
| **Scope in** | Outgoing wire holds and rejections; reviewer routing; standing wire instructions; cutoff handling; screening hits; exception reporting |
| **Agent** | Investigator gains **wire mode** (subject classification selects plan template + tool scope). Hard rules in code: cutoff computation, screening hit ⇒ freeze, new beneficiary ⇒ reviewer. Allowlist (wire): `route_to_reviewer`, `add_standing_instruction`, `reschedule_value_date`, `open_compliance_referral`. **`release_wire` is not an agent tool** |
| **MCP servers / tools** | `wire`: get_wire, get_wire_audit_trail, get_standing_instructions, get_approval_queue, get_cutoff, route_to_reviewer (w), add_standing_instruction (w), reschedule_value_date (w) · `compliance` adds open_compliance_referral (w) · `cash`-lite: get_available_balance (for Sc. 16) |
| **Simulated data** | Wires (in/out), holds with reasons, reviewer queue, standing wire instructions per client, Fedwire cutoffs, screening results incl. one hit, available balances |
| **Corpus** | Wire processing guide (§5.2 new beneficiary, §9.1 cutoff), sanctions procedure, `INC-2001…2005` |
| **Portal** | Wires tab; reviewer queue; review packet view; `WIRE_REVIEWER` role and release action; daily wire exception report |
| **Governance** | Agent is maker, never checker; release is a human-only action; screening hit blocks all remediation |
| **Scenarios** | 7 beneficiary mismatch · 13 new beneficiary before cutoff · 14 cutoff missed · 15 screening hit · 16 insufficient balance |
| **Demo** | "Why is W300917 stuck?" → held for new-beneficiary control, cutoff in 22 min → review packet → reviewer releases → audit message; Sc. 15 freeze |
| **Effort** | 1–2 weekends |

---

## Phase C — Supervisor and specialists

**Proves:** delegation, correlation, and per-agent policy — multiple agents, each structurally unable to do the others' jobs.

| | |
|---|---|
| **Scope in** | Split the Investigator; add a Supervisor that decomposes, dispatches in parallel, correlates findings by shared cause, and synthesizes |
| **Agents** | **Supervisor** (classify → decompose → correlate → synthesize; allowlist: `create_case`, `update_case` only) · **Settlement** (trade mode; scope trade/counterparty/position/client-read/ops — **cannot** propose `update_ssi`) · **Risk/Client** (new: restrictions, screening, SSI current-vs-history; **owns the only path to `update_ssi`**) · **Knowledge** (retrieval + citation packaging; read-only). The **Wire** specialist ships with the optional Wires module, not here. |
| **Contracts** | `SubTask{agent, subject_ids, question, budget}`; `Finding` gains additive `sub_findings` + `proposed_actions[].proposed_by`; known-actions registry so synthesis can't drop a proposal |
| **Simulated data** | Sc. 11 (wire-free): HF101 with 3–4 settlement fails — two sharing one counterparty cause, one distinct (e.g. a short position) |
| **Portal** | Client-level investigation view; grouped actions; delegation shown in trace |
| **Governance** | Allowlists per agent in `allowlists.yaml`; Settlement Agent cannot propose `update_ssi` (policy rejection in trace) |
| **Scenarios** | 11 multi-issue client (built; scorer `groups` branch). Regression on the Phase A scenarios is deferred to the end-of-project eval sweep — no per-phase sweep during the build (`docs/backlog.md`). |
| **Demo** | "Investigate all problems affecting HF101 today" → fan-out → two root causes → several trades under one action, the distinct fail separate → any `INSUFFICIENT_EVIDENCE` surfaced verbatim |
| **Effort** | 1–2 weekends · delivered as two PRs (specialist runner; Supervisor + Sc. 11) |

---

## Phase D — Event-driven investigations

**Proves:** the platform is a platform, not a chat box — it reacts to the estate without a user.

| | |
|---|---|
| **Scope in** | `EventBus` — **Postgres-outbox** (real, `platform_api/events/outbox.py`, works local + hosted) + a lazy **Kafka** adapter (`kafka.py`, untested here); simulator publishes FAILED events (`make emit`); an **in-process consumer** (app lifespan, `EVENTS_ENABLED=1`) opens a case + runs the investigation; dedup on `{subject}:{failure_code}` |
| **Routing** | Code, not an LLM classify — a FAILED settlement event carries `trade_id` + `failure_code` → `investigate(trade_id)`. Urgency: a `deadline` inside 60 min → case `priority=HIGH`. (Wire / client event subjects are `OUT_OF_SCOPE` — they arrive with their modules.) |
| **Portal** | Cases show a `source` badge (`event`/`user`) + `HIGH` chip; the Cases list polls so event cases appear live |
| **Built** | FAILED event → case; duplicate event → same case (audit note, no 2nd investigation); near-deadline event → case `HIGH`. Wire prioritisation ships with the Wires module. |
| **Demo** | `make emit TRADE=T100245` → case + finding + proposal appear unprompted; trace root span is the `event` |
| **Effort** | 1 weekend |

---

## Phase E — Developer Agent

**Proves:** software-engineering agents on the same substrate — incident diagnosis, verification, PR review, and eval authoring — with the same propose-then-human-approves gate.

| | |
|---|---|
| **Core slice built (2026-09-09)** | **Incident mode only.** `platform` MCP server (in-process, fixture-backed): reads (`get_service_health` / `get_job_runs` / `get_deployments` / `diff_config` / `get_topic_lag` / `get_platform_logs` / `get_source`) + approval-gated writes (`open_change_ticket` / `rerun_job` / `replay_message`). `agent_core/developer.py::investigate_incident`, `developer` allowlist (no deploy/merge/approve — asserted), `planner/incident.md` + `synthesis/incident.md`, `Finding.blast_radius` + `Finding.fix_strategy` (hard rule in code, keyed on `release_note`). `POST /diagnose`, portal Engineering tab. **Deferred** (`docs/backlog.md`): verification / PR-review / eval-authoring modes, the `repo` + `ci` servers, the Supervisor hand-off, the standards corpus. |
| **Scope in (full)** | Four Developer Agent modes; platform-fault simulation; standards corpus; CI integration |
| **Agent** | **Developer Agent** · *incident*: health → jobs → deployments → config diff → topic lag → logs → source → blast radius; `fix_strategy: revert \| fix_forward` · *verification*: expectation → re-check → delta → hand residual to business agent → write incident back · *review*: diff classification → targeted standards retrieval → static/security/coverage/tests/eval-rerun as tools → structured `Review` → `post_review` · *eval authoring*: SOP section → planted chain + `expect:` + fixtures → baseline run → draft PR. Allowlist: `open_change_ticket`, `rerun_job`, `replay_message`, `open_pull_request` (draft), `post_review`. **No deploy, merge, approve, or config-write tools exist** |
| **MCP servers / tools** | `platform`: get_service_health, get_job_runs, get_deployments, diff_config, get_topic_lag, rerun_job (w), replay_message (w), open_change_ticket (w) · `repo`: get_pull_request, get_diff, get_linked_issue, get_source, open_pull_request (w), post_review (w) · `ci`: run_static_analysis, run_security_scan, get_test_coverage, run_tests, run_eval |
| **Simulated data** | Job runs, deployments, config versions, topic lag, stack traces, a 47-trade backlog (Sc. 17); intentional change + release note (Sc. 18); seeded PR fixtures (19–21) |
| **Corpus** | `docs/standards/` (coding, security, tool-contract conventions, observability), ADRs, release notes — indexed with diff-surface filtering; `INC-3xxx` written back by verification |
| **Portal** | Engineering tab: incidents, verifications, reviews; `CHANGE_APPROVER` role |
| **Governance** | Change tickets approval-gated; PRs reviewed by the same workflow including the agent's own; agent-authored scenarios need a human reviewer |
| **Scenarios** | 17 failed job + config diff · 18 fix-forward · 19 write tool missing `approval_id` → BLOCKER · 20 eval fixture changed → re-run · 21 clean PR · 22 verified 47/47 · 23 46/47 + hand-off · 24 fix didn't work · 25 agent-authored scenario |
| **Demo** | Business agents find nothing → Developer Agent finds the job, diff, backlog → revert + rerun + PR → applied → verified 46/47 → residual to Settlement Agent → INC-3012 retrievable · PR #142 review with BLOCKER |
| **Effort** | 2–3 weekends |

---

## Phase F — Prime finance domains

**Proves:** domain depth — the scenarios that only someone with a securities lending and asset servicing background would build.

| | |
|---|---|
| **Core slice built (2026-09-09)** | **Stock Loan only.** `stockloan` MCP server (in-process, fixture-backed): reads (`get_loan` / `list_loans` / `get_recall` / `get_rerate_history` / `get_lending_availability`) + approval-gated writes (`initiate_recall` / `rerate_loan` / `book_buy_in`). `agent_core/stockloan.py::investigate_loan`, `stockloan` allowlist, `planner/stockloan.md` + `synthesis/stockloan.md`, **recall-vs-buy-in hard rule in code** (`_enforce_recall_window` on `RECALL_NOTICE_DAYS` before `return_needed_by`). `POST /investigate {loan_id}`; Supervisor `_decompose` + prompt extended for a `stockloan` sub-task (loan subject). **Deferred** (`docs/backlog.md`): seeded table + simulator planter (Python fixtures for now), Margin / CorpActions / Cash, mixed-client Sc. 30, portal affordance. |
| **Scope in (full)** | One domain at a time: stock loan → margin & collateral → corporate actions → cash |
| **Agents** | **StockLoan** (loans, recalls, returns, rerates, availability) · **Margin** (calls, eligibility, haircuts, shortfall) · **CorpActions** (events, entitlements, elections, claims on loaned positions) · **Cash** (balances, projections, funding ladders). Each: own scope, allowlist, corpus slice; hard rules in code (recall deadlines, call windows, record-date logic); proposals only |
| **MCP servers** | `stockloan`, `margin`, `corpactions`, `cash` — each read + 1–2 approval-gated writes |
| **Simulated data** | Loans and recalls against positions; price moves driving margin; corporate-action calendar; cash ladders |
| **Corpus** | Stock loan operations, margin & collateral policy, corporate actions guide (already listed in the doc set), funding procedure; `INC-4xxx` |
| **Supervisor** | `classify` extended with new subject types; correlation on loan id / event id |
| **Scenarios** | 26 recall vs loaned position · 27 margin call after price move · 28 dividend claim on stock lent over record date · 29 collateral ineligible after downgrade · 30 HF101 mixed: settlement fail + held wire + recall |
| **Demo** | Sc. 30 — one client, three domains, one synthesized answer |
| **Effort** | ~1 weekend per domain |

---

## Phase G — Hardening (as needed)

| | |
|---|---|
| **Trace replay & diff** | Re-run a request against current data; diff two traces (model swap, prompt change) — the principled answer to "which model?" |
| **Model swap** | Bedrock `ModelClient`; per-step routing shown in the diff |
| **AWS path** | `docs/deploy-aws.md` (ECS Fargate, RDS, MSK) — documented because it's on the resume |
| **Memory loop** | Closed-case → incident indexing across all domains |
| **Guardrail depth** | PII scrubbing on logs before model calls, with counts in the guardrail span |

---

## Concept coverage by phase

Mainline is A · C · D · E · F. **B (opt)** is the optional Wires module — deferring it
defers the pure maker–checker / human-only-release demo; approval-at-the-tool, per-agent
allowlists, and "no deploy/merge tools" (E) carry the governance story on the mainline.

| Concept | A | C | D | E | F | B (opt) |
|---|---|---|---|---|---|---|
| LLM — reason, decide, explain | plan, root cause, rejected alternatives | decomposition, synthesis | classify from event | diff classification, review synthesis | domain reasoning | wire reasoning around hard rules |
| R2D2 / RAG — evidence | SOP + incident citations; Sc. 2 flip | Knowledge Agent | — | standards corpus, release notes, write-back | domain corpora | wire guide, sanctions |
| MCP — connections | 9 servers, read/write tiers | scoped per agent | — | + platform, repo, ci | + 4 domains | + wire, compliance writes |
| Agentic AI — worker | single agent, restraint (4, 10, 12) | delegation, correlation | unprompted | engineering modes, self-review | specialists | maker not checker |
| Platform — shell | cases, approvals, audit, trace, evals, UI | client-level view | event source | engineering tab, change control | mixed-domain synthesis | reviewer role, reports |
| Governance | approval at tool, allowlists | per-agent policy | dedup | no deploy/merge tools | proposals only | hard rules, human-only release |
| Evaluation | 10 scenarios, CI gate | regression on split | event tests | 25 + agent-authored | 30 | 16 |
| Observability | Trace screen | delegation spans | event root span | review/verification traces | — | — |
