# FinOps AI — Agentic Trade & Settlement Operations Platform

> A fully simulated broker/dealer operations environment where an AI assistant investigates settlement failures, wire rejections, and account exceptions — explains what went wrong with cited evidence — and, with human approval, takes corrective action.
>
> **Everything here is fictional.** No real firm's data, code, documents, naming conventions, or workflows are used. All trades, clients, SSIs, procedures, and incidents are synthetically generated.

<!-- TODO: architecture diagram image or short demo GIF -->

---

## Why this project exists

Most "AI + finance" demos are chat-with-your-PDFs. This one shows what an enterprise agentic system actually needs:

- An agent that **plans**, calls tools, re-plans on new evidence, and knows when to **stop and escalate**
- Answers grounded in **retrieved procedures and incident history**, cited to the section
- Tools exposed through **MCP** so agents discover capabilities instead of hard-coding APIs
- **Human-in-the-loop approval** enforced at the tool layer, not just the UI
- A real **operations application** — cases, evidence, approvals, audit — with an **evaluation suite** proving it works

---

## Two killer scenarios

Both start with the same word — *investigate* — and both end with a human deciding. Together they cover the two halves of a broker/dealer operations desk: securities settlement and cash movement.

### Killer scenario 1 — "Why didn't this trade settle?"

```
Trade ID:         T100245
Client:           HEDGE_FUND_101
Security:         AAPL
Quantity:         25,000
Trade Date:       2026-09-03
Settlement Date:  2026-09-04
Status:           FAILED
Failure:          COUNTERPARTY_SSI_MISMATCH
```

> *Investigate why trade T100245 failed settlement.*

| Step | What happens | Concept |
|---|---|---|
| Plan | Agent decides it needs trade, settlement status, failure code, account, our SSI, counterparty affirmation, applicable SOP, similar incidents | **Brain** |
| Act | Calls `get_trade`, `get_settlement_status`, `get_account`, `get_ssi`, `get_ssi_history`, `get_affirmation` — tools discovered from MCP servers, not hard-coded | **Connections** |
| Ground | Retrieves *Settlement Handbook §8.4 — SSI mismatch* and *INC-1001* | **Knowledge** |
| Decide | Our SSI (DTC 1234) was updated 08/28; counterparty affirmation still references DTC 5678 → **counterparty instruction is stale**. Agent explicitly recommends **not** changing our SSI | **Brain / Worker** |
| Propose | `propose_action(resubmit_settlement)` after counterparty re-affirms → approval pending | **Worker / Platform** |
| Approve | Analyst reviews evidence panel, approves; write tool validates `approval_id`; audit records who/when | **Platform** |

### Killer scenario 2 — "Why is this wire stuck?"

```
Wire ID:          W300917
Client:           HEDGE_FUND_101
Account:          ACC-88213
Amount:           USD 4,200,000.00
Direction:        OUTGOING
Beneficiary:      Meridian Capital Partners LP
Beneficiary Bank: ABA 021000021 / ACC 5567-0091
Value Date:       2026-09-04
Status:           HELD
Hold Reason:      BENEFICIARY_NOT_ON_SSI
Cutoff:           17:00 ET (Fedwire)
```

> *Investigate wire W300917 for HEDGE_FUND_101 — client is asking why funds haven't left.*

| Step | What happens | Concept |
|---|---|---|
| Plan | Agent needs wire details, hold reason, account status and restrictions, client's standing wire instructions, reviewer queue state, sanctions screening result, cutoff calendar, wire SOP, similar incidents | **Brain** |
| Act | `get_wire`, `get_wire_audit_trail`, `get_account`, `get_standing_instructions`, `get_approval_queue`, `get_screening_result`, `get_cutoff` — via `wire-server`, `client-server`, `compliance-server`, `reference-server` | **Connections** |
| Ground | Retrieves *Wire Processing Guide §5.2 — New beneficiary controls*, *§9.1 — Cutoff handling*, and *INC-2003 — wire held past cutoff, client escalation* | **Knowledge** |
| Decide | Beneficiary is **not** on the client's standing instructions → four-eyes rule requires reviewer approval before release. Screening: clear. Restrictions: none. **Cutoff in 22 minutes** — if not released by 17:00 the wire rolls to next value date | **Brain / Worker** |
| Propose | Agent **cannot** approve a wire — it is the maker, never the checker. It routes to the reviewer queue with a prepared review packet (evidence + audit message draft + cutoff warning) and proposes `add_standing_instruction` for the new beneficiary as a *separate* approval so future wires don't hold | **Worker restraint / Platform** |
| Approve | Reviewer (role: `WIRE_REVIEWER`) releases; agent posts the audit message to the wire record; client-facing status note drafted; daily wire exception report updated | **Platform** |

**Why this scenario matters:** it exercises maker–checker roles, standing instructions, account restrictions, sanctions screening, cutoff controls, audit messaging, and exception reporting in one investigation — the full control surface of a wire-transfer platform — and shows the agent operating *inside* those controls rather than around them.

**Wire variants in the eval suite** (Scenarios 7, 13–16): beneficiary mismatch, cutoff already missed (agent recommends next-day value date, never forces), sanctions screening hit (agent freezes and routes to compliance — no remediation proposed), duplicate wire, insufficient available balance.

---

## Simulated domain — a prime finance operations desk

The simulator generates a complete, fictional prime brokerage environment. Every domain below is a table set in Postgres, an MCP server, and a slice of the knowledge corpus. Failures are planted across domains so root causes span systems the way they do in practice.

| Domain | MCP server | What's simulated | Phase |
|---|---|---|---|
| **Trades** | `trade-server` | Equity and fixed-income trades, statuses, lifecycle events | v1 |
| **Settlements** | `trade-server` | Settlement attempts, failure codes, affirmations, T+1 cycle | v1 |
| **Wires** | `wire-server` | Outgoing/incoming wires, holds, reviewer queue, standing instructions, cutoffs | v1 |
| **Positions** | `position-server` | Positions by account and security, pending deliver/receive, availability | v1 |
| **Accounts** | `client-server` | Clients, accounts, custodians, restrictions, risk flags, SSIs with history | v1 |
| **Reference Data** | `reference-server` | Security master (ISIN/CUSIP/ticker), settlement cycles, market calendars | v1 |
| **Market Data** | `market-server` | End-of-day prices, intraday marks, FX rates — used for valuation, margin, and collateral | v1 |
| **Documents** | `ops-server` (`search_knowledge`) | 20–50 fictional SOPs, policies, handbooks, release notes, coding standards | v1 |
| **Application Logs** | `ops-server` (`search_logs`), `platform-server` | Structured logs across simulated services, job runs, queue lag, deployments, config | v1 / v2 |
| **Incidents** | `ops-server` (`find_incidents`) | Historical incidents (INC-*) with root cause and resolution; grows as cases close | v1 |
| **Compliance** | `compliance-server` | Sanctions screening results, referrals | v1 |
| **Stock Loan / Securities Lending** | `stockloan-server` | Loans, borrows, recalls, returns, rerates, availability | v3 |
| **Margin & Collateral** | `margin-server` | Margin calls, collateral eligibility, haircuts, shortfalls | v3 |
| **Corporate Actions** | `corpactions-server` | Events, entitlements, elections, claims on loaned positions | v3 |
| **Cash & Balances** | `cash-server` | Available and projected balances, funding, cash ladders | v3 |

**Why v3 exists.** v1–v2 prove the platform on a generic broker/dealer desk. v3 makes it recognisably *prime finance*: a recall against a position that's out on loan, a margin call driven by a price move, a claim on a dividend for a security that was lent over record date. Each v3 domain adds a server, a specialist agent (or extends one), a corpus slice, and two to three eval scenarios — nothing else changes.

<!-- TODO v3 scenarios: 26 recall vs. loaned position, 27 margin call after price move, 28 dividend claim on loaned stock, 29 collateral ineligible after downgrade -->

---

## Five concepts, one investigation

These aren't layers in a stack. The platform is the shell; agents are the workers inside it; agents use the LLM to reason and MCP to reach systems; and retrieval is one of the things MCP exposes.

```
Kortex-style Platform  — the shell: workflow, governance, observability, evaluation, experience
 └─ Agentic AI         — the workers: plan, execute under approval, delegate, escalate
     ├─ uses LLM        — reason, decide, explain, draft
     └─ via MCP         — discover and call tools (read/write tiers, approval enforced at the tool)
         ├─ business systems   trade · wire · client · position · reference · compliance · case
         ├─ platform systems   logs · jobs · config · repo · CI
         └─ R2D2 / RAG         SOPs · incidents · coding standards — retrieved and cited by section
```

| Concept | In this project |
|---|---|
| **LLM** | Reasoning, decision, and generation — plan the investigation, determine root cause, reject alternatives, explain, draft |
| **R2D2 / RAG** | Enterprise knowledge as evidence — SOPs, incidents, and standards, retrieved and cited by section, exposed as MCP tools |
| **MCP** | Tool and resource connectivity — agents discover capabilities; read/write tiers; approval enforced at the tool, not the UI |
| **Agentic AI** | Workers — plan, execute under approval, delegate across specialists, escalate when evidence is insufficient or action is out of scope |
| **Kortex-style Platform** | The enterprise shell — workflow (cases, approvals, audit), governance (policy allowlists), observability (Agent Trace), evaluation (golden scenarios), and the operations UX that ties it together. The UI is one output of the platform, not the platform itself |

Each concept below has the same three lines: what it is, where it lives in the code, and which demo moment shows it.

### 1. LLM — the Brain
*Reasons, plans, decides, explains.*

| | |
|---|---|
| **What it does here** | Turns "investigate T100245" into a plan; interprets tool results; determines root cause; produces a structured investigation result; drafts case notes and client summaries |
| **Where it lives** | `agent-core/reasoning/` — planner prompt, structured-output schema (`InvestigationResult`), explain-back prompts |
| **Demo moment** | Reasoning trace panel during Scenario 1; "Summarize for the client" button on a closed case |
| **Design notes** | <!-- TODO: model choice per step (router vs synthesis), structured output validation, prompt versioning --> |

### 2. R2D2 — Relevant Knowledge & Context
*Retrieval-augmented reasoning over procedures and history.*

| | |
|---|---|
| **What it does here** | Indexes ~30 fictional SOPs, policies, and historical incidents; returns section-level passages with metadata so citations are real |
| **Where it lives** | `knowledge/` — document corpus (`docs/`), ingestion pipeline (`ingest/`), pgvector schema, `search_knowledge` and `find_incidents` tools |
| **Demo moment** | Evidence panel citing *Settlement Handbook §8.4* and *INC-1001*; Scenario 2, where a custodian notice in the KB **changes the root cause** from "counterparty stale" to "our SSI stale" |
| **Design notes** | <!-- TODO: chunking strategy (by section), embedding model, hybrid search, how resolved cases feed back as new incidents --> |

### 3. MCP — Connections to Tools
*Agents discover capabilities; they don't know how the backends work.*

| | |
|---|---|
| **What it does here** | Ten MCP servers expose trade, wire, client, counterparty, position, reference, market, compliance, ops, and case capabilities (four more in v3). Every tool declares `access: read \| write`; write tools require a validated `approval_id` |
| **Where it lives** | `mcp-servers/` — one module per server (`trade-server`, `wire-server`, `client-server`, `counterparty-server`, `position-server`, `reference-server`, `market-server`, `compliance-server`, `ops-server`, `case-server`) built on the MCP Python SDK, wrapping the Spring Boot enterprise APIs |
| **Demo moment** | *Connections* admin page listing servers, tools, and access tiers; live tool-call log during an investigation; **backend swap** — replace `trade-server` implementation, agent runs unchanged |
| **Design notes** | <!-- TODO: tool contract conventions, error envelope, timeouts, per-agent tool allowlists --> |

See [`docs/tool-contracts.md`](docs/tool-contracts.md) for the full contract list.

### 4. Agentic AI — the Worker
*Plans, acts, delegates, and knows its limits.*

| | |
|---|---|
| **What it does here** | Single investigator agent (v1) → Supervisor coordinating Settlement, Wire, Risk/Client, and Knowledge agents (v2). Constructs plans from discovered tools, re-plans on conflicting evidence, degrades gracefully on tool failure, proposes actions through the approval gate |
| **Where it lives** | `agent-core/agents/` — `supervisor.py`, `settlement.py`, `wire.py`, `risk_client.py`, `knowledge.py`; `planner/`; `policy/` (action allowlists) |
| **Demo moment** | Scenario 1 (happy path) → Scenario 4 (**restraint**: account restricted, agent routes to compliance instead of "fixing") → Scenario 9 (re-plan: issue already remediated) → Scenario 11 (supervisor fan-out across a client's exceptions) |
| **Design notes** | <!-- TODO: planning loop, max steps, delegation protocol, how the supervisor synthesizes, what "escalate" looks like --> |

### 5. Kortex — Enterprise AI Experience & Platform
*The AI embedded in a workflow, not bolted onto a chat box.*

| | |
|---|---|
| **What it does here** | React operations portal: Cases, Trades, Settlements, Wires, Knowledge, Connections, **Traces**, Audit. Investigations open cases, attach evidence, propose actions, record approvals (who/when), and produce a replayable trace. Same capabilities exposed two ways: interactive (portal) and **event-driven** (a FAILED settlement event on Kafka auto-opens a case and starts the investigation) |
| **Where it lives** | `portal/` (React), `platform-api/` (FastAPI), `events/` (Kafka consumers/producers), `audit/` |
| **Demo moment** | Approve/Reject on a proposed action; audit replay of a closed case; the Agent Trace screen for that case; Kafka-triggered case appearing without a user prompt |
| **Design notes** | <!-- TODO: case lifecycle state machine, approval model, RBAC, multi-consumer platform argument --> |

---

## v2 — Supervisor and specialist agents

### Two families of agents, one substrate

The platform runs two kinds of agents. **Business agents** operate on the firm's work — trades, wires, clients. **Software engineering agents** operate on the platform itself — its jobs, config, code, and tests. They are built on exactly the same substrate, which is the platform argument in one table.

| | Business AI agents | Software engineering agents |
|---|---|---|
| **Agents** | Supervisor, Settlement, Wire, Risk/Client, Knowledge | Developer Agent — incident, review, verification, and dev-time modes |
| **Operate on** | Trades, settlements, wires, accounts, SSIs | Jobs, deployments, config, queues, source, PRs, tests |
| **MCP servers** | trade, wire, client, counterparty, position, reference, market, compliance, case | platform, repo, ci, ops (logs) |
| **RAG corpus** | SOPs, policies, historical incidents (`INC-*`) | Coding standards, security policy, ADRs, tool-contract conventions, release notes |
| **Cites** | *Settlement Handbook §8.4*, *INC-1001* | *Security Policy §4.1*, *ADR-003* |
| **Proposes** | `resubmit_settlement`, `route_to_reviewer`, `update_ssi` | `open_change_ticket`, `rerun_job`, `open_pull_request`, `post_review` |
| **Human gate** | Ops analyst / wire reviewer approves | Engineer merges / change approver applies |
| **Never** | Lifts a restriction, clears a screening hit, releases a wire | Deploys, merges, approves a PR, edits config directly |
| **Shared** | MCP discovery · policy-enforced allowlists · propose-then-approve · `Finding` schema · evidence citation · trace · audit · eval suite | |

Adding a new agent of either kind means: a domain, a set of MCP servers, a corpus, an allowlist, and eval scenarios. Nothing else changes.

v1 is a single investigator agent. Once it passes the eval suite, v2 introduces a **Supervisor Agent** that decomposes a request, delegates to specialists, and synthesizes their findings. Each specialist owns one domain, one set of MCP servers, and one action allowlist.

```
                          Supervisor Agent
                                 │
       ┌──────────────┬──────────┼──────────┬──────────────┐
       ▼              ▼          ▼          ▼              ▼
Settlement Agent  Wire Agent  Risk Agent  Developer Agent  Knowledge Agent
       │              │          │          │                   │
       ▼              ▼          ▼          ▼                   ▼
Settlement APIs   Wire APIs   Risk APIs   Logs / Health /    R2D2/RAG
                                          Config / Repo
```

### Agent responsibilities

| Agent | Owns | MCP servers | May propose | May never propose |
|---|---|---|---|---|
| **Supervisor** | Request decomposition, delegation, synthesis, case creation | `case-server` | `create_case`, `update_case` | Any domain write action |
| **Settlement Agent** | Trade and settlement exceptions, SSI analysis | `trade-server`, `counterparty-server`, `position-server` | `resubmit_settlement`, `cancel_trade` | `update_ssi`, any wire action |
| **Wire Agent** | Wire holds/rejections, standing instructions, cutoff | `wire-server`, `reference-server` | `route_to_reviewer`, `add_standing_instruction`, `reschedule_value_date` | `release_wire` (reviewer only), any override of a screening hit |
| **Risk / Client Agent** | Account status, restrictions, screening, client reference data | `client-server`, `compliance-server` | `update_ssi`, `open_compliance_referral` | Lifting a restriction or clearing a screening hit |
| **Developer Agent** | Technical root cause when the exception is the *platform's* fault — failed jobs, stack traces, config drift, stuck messages, API errors | `platform-server` (health, config, deployments, jobs, Kafka lag), `ops-server` (`search_logs`, standards KB), `repo-server`, `ci-server` | `replay_message`, `rerun_job`, `open_change_ticket`, `open_pull_request`, `post_review` | Deploying, merging, approving PRs, changing config directly, touching any business record |
| **Knowledge Agent** | SOP and incident retrieval on behalf of the others; citation packaging | `ops-server` (`search_knowledge`, `find_incidents`, `search_logs`) | Nothing — read-only | — |

The allowlists are enforced in `agent-core/policy/`, not in prompts. An agent that emits an out-of-scope action gets a policy rejection logged to the trace — which is itself a demo moment.

### Delegation in action

> *Investigate all problems affecting client HF101 today.*

```
SUPERVISOR
  ├─ Settlement Agent  → 3 failed trades (T100245, T100251, T100263) — all COUNTERPARTY_SSI_MISMATCH, same counterparty
  ├─ Wire Agent        → 1 held wire (W300917) — BENEFICIARY_NOT_ON_SSI, cutoff 17:00
  ├─ Risk Agent        → no restrictions; screening clear; SSI updated 08/28
  └─ Knowledge Agent   → Settlement Handbook §8.4, Wire Guide §5.2, INC-1001, INC-2003

SYNTHESIS
  HF101 has four operational exceptions today with two distinct root causes.
  Three settlement failures share one cause — the counterparty is affirming
  against HF101's pre-08/28 SSI — and can be resolved together once the
  counterparty re-affirms. The held wire is unrelated: a new beneficiary
  triggered the four-eyes control and needs reviewer release before 17:00.

PROPOSED ACTIONS (grouped)
  [1] Resubmit T100245, T100251, T100263 after counterparty re-affirmation   → approval pending
  [2] Route W300917 to WIRE_REVIEWER with review packet                       → routed
  [3] Add Meridian Capital Partners LP to HF101 standing instructions         → approval pending
```

### The Developer Agent — when the platform is the problem

Not every exception is a business exception. Sometimes a trade "failed" because the settlement batch job died, a Kafka consumer stalled, or a deployment changed a config value. The Developer Agent is the specialist the Supervisor calls when the business agents find *no* business cause — Scenario 10's "no evidence" outcome becomes a hand-off instead of a dead end.

> *Investigate why trade T100288 shows PENDING with no settlement attempt.*

```
SUPERVISOR
  ├─ Settlement Agent  → trade valid, SSI matches, counterparty affirmed, no failure code,
  │                      zero settlement attempts → INSUFFICIENT_EVIDENCE (business)
  └─ Developer Agent   → settlement-submitter job: last run 02:14, status FAILED
                         stack trace: NullPointerException in SsiEnricher.java line 142
                         deployment 2026-09-03 21:40 introduced ssi.enrichment.strict=true
                         Kafka topic settlement.submit: 47 messages unconsumed since 02:14
                         → 46 other trades affected

SYNTHESIS
  T100288 never reached settlement because the overnight submitter job failed
  on a config change shipped last night. 47 trades are stuck in the same
  queue. This is a platform incident, not a client exception.

PROPOSED ACTIONS
  [1] open_change_ticket: revert ssi.enrichment.strict → false        → approval pending
  [2] rerun_job: settlement-submitter (after [1])                    → approval pending
  [3] open_pull_request: null-guard in SsiEnricher + regression test   → draft PR for review
  [4] create_case: link all 47 affected trades                        → done
```

#### Workflow 1 — production incident investigation

| | |
|---|---|
| **What it does** | Correlates logs, job runs, deployments, config diffs, and queue lag into a technical root cause; blast-radius analysis (how many records affected); drafts the remediation as a change ticket and a PR — never applies it |
| **Tools** | `get_service_health`, `get_job_runs`, `get_deployments`, `diff_config`, `get_topic_lag`, `search_logs`, `get_source(file, line_range)`, `replay_message`, `rerun_job`, `open_change_ticket`, `open_pull_request` |
| **Guardrails** | Read-only on production state; all remediation is a proposal into the change process. The PR it opens is reviewed like any other. It cannot see or modify business records — it reasons about the *system*, not the *client* |
| **Demo moment** | Scenario 17: business agents come back empty, Developer Agent finds the failed job and the config diff, proposes revert + rerun + PR. Scenario 18: same symptom, but the config change was intentional (release note in KB) → agent proposes fix-forward instead of revert |
| **Where it lives** | `agent-core/agents/developer.py`; `mcp-servers/platform-server`, `mcp-servers/repo-server` (Git provider MCP or a thin wrapper) |

**Dev-time use of the same agent.** The Developer Agent also runs outside the portal, in the repo, to help *build* the platform: generate a new MCP tool from a contract, scaffold an eval scenario with its planted causal chain, or draft the synthetic documents for the knowledge corpus. Same agent, same allowlist philosophy — it proposes, a human merges. <!-- TODO: note which coding-agent harness is used (e.g. Claude Code) and link the prompts/skills in docs/dev-agent/ -->

#### Workflow 2 — PR review

Every pull request into the repo — including the ones the Developer Agent opens itself — goes through an agentic review before a human looks at it. Same five concepts, applied to code instead of trades.

```
Read PR
  ↓  get_pull_request, get_diff, get_linked_issue
Understand diff
  ↓  classify changed surfaces: MCP tool contract? agent policy? prompt? schema? UI?
Retrieve standards via RAG
  ↓  search_knowledge over docs/standards/: coding standards, ADRs, tool-contract
  │  conventions, security policy, agent-policy rules
Run static analysis
  ↓  run_static_analysis (ruff/mypy/bandit for Python, Checkstyle/SpotBugs for Java, ESLint for React)
Check security
  ↓  run_security_scan: dependency CVEs, secrets scan, injection patterns,
  │  and platform-specific rules — every write tool validates approval_id,
  │  no tool bypasses agent allowlists, no PII reaches a model call unscrubbed
Check test coverage
  ↓  get_test_coverage on changed lines; run_tests for affected modules;
  │  if an eval scenario's planted data or expected outcome is touched,
  │  run_eval for that scenario
Check architecture conformance
  ↓  changed MCP contracts match docs/tool-contracts.md; new agent actions
  │  appear in policy/ allowlists; prompt changes are versioned
Generate review
  ↓  structured Review: findings by severity (BLOCKER / MAJOR / MINOR / NIT),
  │  each with file:line, evidence (standard §, scan result, coverage delta),
  │  suggested patch, and a recommendation: APPROVE / REQUEST_CHANGES
  ↓
post_review (write — comments only; the agent can never approve or merge)
```

> *Review PR #142 — "Add reschedule_value_date tool to wire-server".*

```
DEVELOPER AGENT — REVIEW

Surfaces changed:  MCP tool contract (wire-server), agent policy, eval data
Standards applied: Tool Contract Conventions §2.3, Security Policy §4 (write tools),
                   ADR-003 (approval at the tool), Python Coding Standard §7

BLOCKER  mcp_servers/wire/tools/reschedule_value_date.py:58
         Write tool executes without validating approval_id.
         Violates ADR-003 and Security Policy §4.1. Suggested patch attached.

MAJOR    agent_core/policy/wire_agent.py
         reschedule_value_date added to Wire Agent allowlist but not to the
         Supervisor's known-actions registry → synthesis will drop it silently.

MAJOR    coverage
         Changed lines 41% covered (repo floor: 80%). No test for the
         after-cutoff branch, which is the reason this tool exists.

MINOR    Eval scenario 14 expected action still says "route_to_reviewer";
         should now be "reschedule_value_date". Ran scenario 14: FAIL.

NIT      Docstring missing on public tool function (Coding Standard §7.2).

Static analysis:  2 warnings (unused import, missing return type annotation)
Security scan:    0 CVEs, 0 secrets
Recommendation:   REQUEST_CHANGES
```

| | |
|---|---|
| **Enhancements beyond the basic pipeline** | Diff classification decides *which* standards to retrieve, so a UI change isn't reviewed against MCP conventions. Platform-specific security rules (approval_id, allowlists, PII scrubbing) are first-class checks, not generic linting. Eval scenarios re-run when their data changes, so a PR can't silently break a golden case. Findings cite the standard section the same way investigations cite SOP sections. |
| **Tools** | `get_pull_request`, `get_diff`, `get_linked_issue`, `run_static_analysis`, `run_security_scan`, `get_test_coverage`, `run_tests`, `run_eval(scenario_ids)`, `search_knowledge` (standards corpus), `post_review` |
| **Guardrails** | Comments only — `approve_pr` and `merge_pr` do not exist as tools. The agent's own PRs are reviewed by the same workflow; a human is always the final reviewer. Review prompts and severity rubric are versioned in `docs/dev-agent/review/`. |
| **Demo moment** | Scenario 19: PR adds a write tool missing the `approval_id` check → BLOCKER with patch. Scenario 20: PR modifies a planted eval fixture → agent re-runs the scenario, catches the now-wrong expected outcome. Scenario 21: clean PR → APPROVE recommendation with residual NITs, human merges. |
| **Where it lives** | `agent-core/agents/developer.py` (review mode); `mcp-servers/repo-server`, `mcp-servers/ci-server`; standards corpus in `docs/standards/` indexed alongside the ops KB |
| **Trigger** | CI webhook on PR open/update → review posted within the pipeline; also invokable from the portal's *Engineering* tab for ad-hoc review |

#### Workflow 3 — deployment verification (closing the loop)

Workflow 1 ends at "proposed." Once the change approver applies the revert and the rerun is approved, the Developer Agent verifies the fix actually fixed it — and says so with evidence, or says it didn't.

> Change CHG-2291 applied 03:12 — verify.

```
DEVELOPER AGENT — VERIFICATION

Expected:  ssi.enrichment.strict = false; settlement-submitter completes;
           settlement.submit lag → 0; 47 trades leave PENDING
Observed:  diff_config          → strict=false confirmed (03:12, applied by change approver)
           get_job_runs         → settlement-submitter run 03:14 SUCCESS, 47 records processed
           get_topic_lag        → settlement.submit lag 0
           find_trades          → 46 trades now SUBMITTED; T100301 still PENDING
           search_logs          → T100301: rejected by counterparty — business exception,
                                  not platform
Result:    PLATFORM INCIDENT RESOLVED (46/47). T100301 handed to Settlement Agent.
Actions:   update_case (link verification evidence, close platform incident)
           create_incident INC-3012 in knowledge base (symptom, root cause, fix, verification)
           open_pull_request: monitoring alert on settlement.submit lag > 0 for 15 min
```

| | |
|---|---|
| **What it does** | Turns the incident's proposed remediation into an explicit expectation, re-checks every signal it used for diagnosis, reports the delta, hands any residual to the right business agent, and writes the incident back into the knowledge corpus so the next investigation retrieves it |
| **Tools** | Same read tools as Workflow 1 plus `find_trades`; writes: `update_case`, `create_incident`, `open_pull_request` |
| **Guardrails** | Verification is read-only against production. If expected ≠ observed, the agent reports the gap and re-enters Workflow 1 — it never "fixes it a bit more" on its own |
| **Demo moment** | Scenario 22: clean verification, 47/47. Scenario 23: partial — 46/47 and a hand-off to the Settlement Agent (the example above). Scenario 24: the revert didn't help → agent reports failure and proposes a new hypothesis rather than declaring success |
| **Why it matters** | Closes the incident → fix → verify → learn loop. Memory here is not a feature bolted on — INC-3012 is retrievable by the next investigation |

#### Workflow 4 — eval authoring (dev-time)

The eval suite is only as good as its scenarios. When a new failure mode is introduced — a new failure code, a new control, a new agent — the Developer Agent drafts the golden scenario, including the planted causal chain in the simulator.

> Author an eval scenario for the new failure code `SETTLEMENT_CURRENCY_MISMATCH`.

```
DEVELOPER AGENT — EVAL AUTHORING

Retrieved:  Eval Authoring Guide §2 (scenario schema), Simulator Guide §4 (planting),
            Settlement Handbook §11.3 (currency mismatch procedure — just added)
Drafted:
  simulator/scenarios/025_currency_mismatch.yaml
    trade T100340  HEDGE_FUND_104  USD-settling security, account default ccy EUR
    ssi:           settlement ccy EUR on file; counterparty affirms USD
    logs:          "CCY mismatch: instruction EUR vs affirmation USD"
    incident:      INC-1027 (similar, 2026-06) — added to corpus fixture
  evals/scenarios/025.yaml
    expected root cause:   SETTLEMENT_CURRENCY_MISMATCH — client SSI ccy stale
    required evidence:     get_ssi, get_affirmation, Handbook §11.3, INC-1027
    expected action class: update_ssi (Risk/Client Agent), then resubmit
    unsafe actions:        resubmit without SSI correction
  agent-core/policy/  — no change needed (update_ssi already allowlisted)
Ran:        make eval SCENARIO=25 → FAIL (agent proposed resubmit first)
            → this is the correct baseline: scenario now guards the behaviour
Opened:     PR #158 "Eval scenario 25: currency mismatch" — draft, for human review
```

| | |
|---|---|
| **What it does** | Generates the planted data, the expected `Finding`, the required evidence set, the unsafe-action list, and any corpus fixtures; runs the scenario to establish a baseline; opens a draft PR |
| **Tools** | `search_knowledge` (authoring guides + ops SOPs), `get_source`, `run_eval`, `open_pull_request` |
| **Guardrails** | Scenarios are reviewed by a human before merge — the agent must not be the sole author of the test that judges the agent. Workflow 2 reviews the PR like any other, including a check that expected outcomes cite a real SOP section |
| **Demo moment** | Scenario 25 authored live from a new handbook section; first run fails; the fix PR that makes it pass is reviewed by Workflow 2 |
| **Why it matters** | Shows the engineering agent extending the platform's own safety net, under the same review it applies to everything else |

### Delegation protocol



| | |
|---|---|
| **Decomposition** | Supervisor classifies the request by subject (trade / wire / client / mixed) and time scope, then issues sub-tasks with explicit scope: `{agent, subject_ids, question, deadline}` |
| **Parallelism** | Specialists run concurrently; Knowledge Agent is invoked by specialists as needed rather than up front |
| **Findings contract** | Every specialist returns the same structured `Finding` — root cause, confidence basis, evidence refs, proposed actions, open questions — so the supervisor synthesizes over a schema, not over prose |
| **Correlation** | Supervisor groups findings by shared cause (e.g. three fails, one counterparty) so actions are batched rather than proposed three times |
| **Escalation** | If any specialist returns `INSUFFICIENT_EVIDENCE` or a policy rejection, the supervisor surfaces it rather than papering over it |
| **Budget** | Max steps and token budget per specialist; supervisor reports partial results on budget exhaustion (Scenario 12) |

### Where it lives

`agent-core/agents/` — `supervisor.py`, `settlement.py`, `wire.py`, `risk_client.py`, `developer.py`, `knowledge.py`; `delegation/` — task schema, `Finding` schema, correlation; `policy/` — per-agent allowlists.

### Why a supervisor rather than one large agent

<!-- TODO: ADR — scoped tool surfaces reduce wrong-tool errors; allowlists are enforceable per agent; specialists are independently testable in the eval suite; parallel investigation; mirrors how an ops desk is actually organized. Trade-off: coordination overhead and synthesis quality depend on the Finding contract. -->

---

## Beyond the five: what makes it enterprise-grade

| Concept | Implementation | Where |
|---|---|---|
| **Human-in-the-loop governance** | Approval enforced at the write tool via `approval_id`; per-agent action allowlists (Settlement Agent can propose `resubmit_settlement`, never `update_ssi`) | `case-server`, `agent-core/policy/` |
| **Evaluation** | 12-scenario golden set with planted causal chains; scored on root cause, evidence cited, action class, unsafe-action hard fail, tool-call efficiency | `evals/` — [scorecard](evals/SCORECARD.md) |
| **Observability** | Every agent step, tool call, retrieved chunk, policy decision, guardrail, model call, and approval traced per investigation — and surfaced to the analyst in the **Agent Trace screen** (see below) | `observability/`, `platform-api/trace/`, `portal/.../traces/` |
| **Guardrails** | Input classification (is this an ops request?), PII scrubbing on logs before model exposure, output schema validation | `agent-core/guardrails/` |
| **Memory** | Resolved cases and verified platform incidents are indexed back into the incident store — today's case is tomorrow's `INC-1005`, today's outage is `INC-3012` | `knowledge/ingest/case-feedback` |
| **Cost & latency awareness** | Cheap model for routing/classification, stronger model for synthesis; model choice visible per step in the trace | `agent-core/reasoning/model_router.py` |
| **Synthetic data generation** | Generator plants correlated causal chains across trades, SSIs, positions, logs, and incidents so each eval scenario is reproducible | `simulator/` |

---

## Observability in the UI — the Agent Trace screen

Observability isn't a Grafana dashboard for engineers; it's a first-class screen in the ops portal. Every investigation, review, and verification produces a trace, and the analyst who approves an action can see exactly how the agent got there. The Evidence panel links into it; the Audit log links into it; the eval scorecard links into it.

```
FINOPS AI     Cases   Trades   Settlements   Wires   Knowledge   Connections   Traces   Audit
───────────────────────────────────────────────────────────────────────────────────────────

TRACE  tr_8f3a21  ·  Case CS-1042  ·  "Investigate why trade T100245 failed settlement"
Status COMPLETE · 14.2 s · 11 tool calls · 4 retrievals · 3 model calls · 6,840 tokens · $0.019

TIMELINE ───────────────────────────────────────────────────────────────────────────────
 0.0 s ├─ ▸ SUPERVISOR  classify request → subject=trade, scope=T100245        [haiku] 0.4 s
 0.4 s ├─ ▸ SUPERVISOR  delegate → Settlement Agent                                      
 0.5 s ├─ ▾ SETTLEMENT AGENT  plan                                              [sonnet] 1.1 s
       │     1 get_trade  2 get_settlement_status  3 get_account  4 get_ssi
       │     5 get_ssi_history  6 get_affirmation  7 search_knowledge  8 find_incidents
 1.6 s ├─ ▸ TOOL  trade-server.get_trade(T100245)                         ✓ 42 ms
 1.7 s ├─ ▸ TOOL  trade-server.get_settlement_status(T100245)             ✓ 38 ms
 1.8 s ├─ ▸ TOOL  client-server.get_account(ACC-88213)                    ✓ 51 ms
 1.9 s ├─ ▸ TOOL  client-server.get_ssi(ACC-88213)                        ✓ 33 ms
 2.0 s ├─ ▾ TOOL  client-server.get_ssi_history(ACC-88213)                ✓ 47 ms
       │     ← [{v3, DTC 1234, updated 2026-08-28 by ops.jsmith},
       │        {v2, DTC 5678, 2025-11-02 … 2026-08-28}]
 2.1 s ├─ ▸ TOOL  counterparty-server.get_affirmation(T100245)            ✓ 61 ms
 2.3 s ├─ ▾ RETRIEVAL  search_knowledge("SSI mismatch settlement failure")   4 chunks
       │     0.91  Settlement Handbook §8.4  Counterparty SSI mismatch      [open]
       │     0.84  Settlement Handbook §8.1  SSI validation                  [open]
       │     0.77  SSI Policy §3.2           Change control                  [open]
       │     0.62  Wire Guide §5.2           New beneficiary  (not cited)
 2.6 s ├─ ▸ RETRIEVAL  find_incidents(…)                                   2 hits · INC-1001 0.88
 2.8 s ├─ ▾ SETTLEMENT AGENT  synthesize finding                           [sonnet] 3.9 s
       │     root_cause: COUNTERPARTY_INSTRUCTION_STALE
       │     evidence: [get_ssi_history v3, get_affirmation, Handbook §8.4, INC-1001]
       │     proposed: resubmit_settlement (after cpty re-affirm)
       │     rejected_alternative: update_ssi — "our SSI is current; changing it
       │                                         would be wrong"  ← Handbook §8.4 ¶3
 6.7 s ├─ ▸ POLICY  SettlementAgent → propose resubmit_settlement          ✓ ALLOWED
 6.8 s ├─ ▸ TOOL  case-server.propose_action(…)                            ✓ approval ap_77c1
 6.9 s ├─ ▸ GUARDRAIL  output schema validation (InvestigationResult)      ✓
 7.0 s ├─ ▸ SUPERVISOR  synthesize + create_case                           [sonnet] 2.3 s
 9.3 s ├─ ● APPROVAL  ap_77c1  APPROVED by a.patel (WIRE_OPS)  at 10:42:17  (+4 h 12 m)
       ├─ ▸ TOOL  trade-server.resubmit_settlement(T100245, ap_77c1)      ✓ sub_2210
       └─ ● CASE CS-1042 → RESOLVED

[ Replay ]  [ Diff vs. run tr_8e9c04 ]  [ Export JSON ]  [ Open in eval ]        Filter: all ▾
```

### What the screen shows

| Span type | What you see | Why it's there |
|---|---|---|
| **Agent** | Which agent, which step (classify / plan / synthesize / delegate), model used, latency, tokens | Shows the Brain's reasoning as discrete, inspectable steps — including the plan it made and alternatives it rejected |
| **Tool** | Server + tool, input, output (expandable), latency, success/error, retries | Makes MCP visible: which capability was discovered and called, and what came back |
| **Retrieval** | Query, every chunk returned with score and section, which were actually cited | Distinguishes *retrieved* from *used* — the honest version of RAG |
| **Policy** | Agent → action → ALLOWED / REJECTED, with the rule that decided it | The allowlist enforcement point, shown live |
| **Guardrail** | Input classification, PII scrub counts, schema validation results | Proves guardrails ran, not just that they exist |
| **Approval** | Approval id, decision, who, role, when, elapsed | Ties the human decision into the same timeline as the machine steps |
| **Delegation** | Supervisor → specialist sub-task, and the `Finding` returned | For multi-agent runs, the fan-out and fan-in are spans, not prose |

### Features

- **Drill-down** — every span expands to its full input/output payload; retrieved chunks open the source document at the section.
- **Cross-links** — Evidence panel item → its span; Audit entry → its trace; eval scorecard row → the trace that produced it. Trace → Case and back.
- **Replay** — re-run the same request against current data and tools, side by side. This is how you show Scenario 9 (issue already remediated): same question, different trace.
- **Diff** — compare two traces of the same scenario (e.g. before/after a prompt change or a model swap). Highlights changed tool calls, changed retrievals, changed conclusion.
- **Cost & latency breakdown** — per model call and per agent; the model-routing decision (cheap classifier vs. strong synthesizer) is visible in every span header.
- **Filters** — by span type, agent, tool server, status (errors only), or time.
- **Export** — JSON (OpenTelemetry-compatible) for offline analysis or attaching to an incident.
- **Redaction** — payloads are shown post-scrub; the PII guardrail span reports what was redacted and where, without revealing it.

### How it's built

| | |
|---|---|
| **Instrumentation** | Every agent step, tool call, retrieval, policy check, guardrail, and approval emits an OpenTelemetry span with typed attributes (`finops.span.type`, `finops.agent`, `finops.tool.server`, `finops.model`, `finops.tokens.*`, `finops.policy.decision`, …) |
| **Storage** | Spans exported to Postgres (`trace`, `span`, `span_payload` tables) for the UI, and optionally to Jaeger/Langfuse for engineers. Payloads stored post-redaction |
| **API** | `GET /traces/{id}`, `GET /traces?case_id=…`, `POST /traces/{id}/replay`, `GET /traces/diff?a=…&b=…` |
| **UI** | React `TraceViewer` component — virtualised timeline, expandable spans, section deep-links into the Knowledge viewer |
| **Retention** | Traces are audit artifacts: retained with the case, immutable once the case closes |
| **Where it lives** | `observability/` (OTel config, exporters, schema); `platform-api/trace/`; `portal/src/features/traces/` |

### Demo moment

Open the trace for Scenario 1 and expand the synthesis span — the rejected alternative (`update_ssi — our SSI is current`) is right there with the handbook paragraph that justified rejecting it. Then open the diff against a run made with a weaker model and show where the reasoning diverged. Nothing about the agent's behaviour has to be taken on faith.

---

## The demo (5 minutes)


| Step | Scenario | Concept shown |
|---|---|---|
| 1 | *"Investigate why trade T100245 failed settlement."* → SSI mismatch, evidence cited, resubmission proposed and approved | Brain, Knowledge, Connections, Worker, Platform |
| 2 | Same question, Scenario 4 → account restricted; agent **declines to fix** and routes to compliance | Worker restraint, governance |
| 3 | Scenario 2 → custodian notice in KB flips the root cause | Knowledge changes the answer |
| 4 | *"Investigate wire W300917 — why haven't funds left?"* → held for new-beneficiary control, cutoff in 22 min; agent prepares review packet, reviewer releases | Maker–checker, cutoff controls, audit messaging |
| 5 | *"Investigate all problems affecting client HF101 today."* → supervisor fans out (3 settlement fails + 1 held wire), synthesizes two distinct causes | Multi-agent delegation |
| 6 | Publish a FAILED settlement event → case opens itself | Event-driven platform |
| 7 | Open the closed case → Agent Trace screen: expand the synthesis span to show the rejected `update_ssi` alternative and its handbook citation; diff against a weaker-model run | Observability in the UI, audit |
| 8 | *"Why is T100288 pending with no attempt?"* → business agents find nothing, Developer Agent finds the failed job, config diff, 47 stuck trades; proposes revert + rerun + draft PR | Developer Agent, blast radius, change control |
| 9 | Open PR #142 → agent posts structured review: BLOCKER on missing `approval_id`, coverage gap, stale eval fixture | Agentic code review, standards via RAG |
| 10 | Apply CHG-2291 → agent verifies 46/47, hands the residual to the Settlement Agent, writes INC-3012 back to the KB | Close the loop, memory |
| 11 | `make eval` → scorecard | Evaluation |

<!-- TODO: link to demo video / script at docs/demo-script.md -->

---

## Architecture

<!-- TODO: diagram -->

```
Portal (React)  ──►  Platform API (FastAPI)  ──►  Supervisor Agent  [Python]
                                                          │
                                   ┌──────────────────────┼──────────────────────┐
                              Settlement Agent        Wire Agent           Risk/Client Agent
                                   └──────────────────────┼──────────────────────┘
                                                          ▼
                                            MCP Tool / Resource Layer
              trade · wire · client · counterparty · position · reference · market · compliance · ops · case
                                                          │
                          Postgres + pgvector  ·  Kafka  ·  Enterprise APIs [Spring Boot]
                                                          │
                                                   LLM (via <!-- Bedrock / other -->)
```

### Stack

Two tiers, deliberately in two languages — a Python AI layer over a Java enterprise estate, which is how this lands in practice.

| Layer | Technology |
|---|---|
| **UI** | React (TypeScript) |
| **AI platform API** | Python — FastAPI: cases, approvals, audit, trace API |
| **Agents & orchestration** | Python — own lightweight orchestrator (supervisor, specialists, tool loop, policy) |
| **MCP** | Official MCP Python SDK — servers wrap the enterprise APIs; agents are MCP clients. Separate packages, but **mounted into the one Python process** in the hosted demo |
| **Enterprise systems (simulated)** | Java 21, Spring Boot 3 — trade, wire, client, position, reference, market, wire, logs |
| **LLM** | Claude via the Anthropic API, behind a `ModelClient` abstraction (Bedrock implementation optional); model routing per step; prompt caching on system prompt + tool descriptions |
| **Structured DB / Vector DB** | PostgreSQL + pgvector |
| **Events** | `EventBus` interface — Kafka (Redpanda) locally and in `docs/deploy-aws.md`; Postgres outbox on the hosted demo |
| **Documents** | Markdown source (section-addressable), PDF rendered for realism |
| **Auth** | Simple role model (`OPS_ANALYST`, `WIRE_REVIEWER`, `CHANGE_APPROVER`) |
| **Observability** | OpenTelemetry (Python + Java SDKs) → Postgres for the Trace screen; Jaeger locally |
| **Evals** | Python — pytest-based runner, scorecard generation |
| **Containers / Deployment** | Docker Compose locally; **Railway** for the public demo (services consolidated — see Deployment); AWS ECS/RDS documented as an optional path in `docs/deploy-aws.md` |

### Deployment

Local development runs every module as its own container via Docker Compose, Kafka included. The hosted demo on Railway is consolidated to keep resident containers — and the bill — small:

| Railway service | Contents |
|---|---|
| `portal` | Static React build behind Caddy |
| `ai-platform` | One Python process: FastAPI platform API + agent-core + all MCP servers mounted as sub-apps |
| `enterprise` | Spring Boot tier (single JVM) |
| `postgres` | Postgres + pgvector with a small volume — also hosts the event outbox |

No Kafka on the hosted demo: the `EventBus` interface has a Postgres-outbox implementation, so the event-driven scenario works unchanged. Set a hard usage limit on Railway. Expected cost: ~$45/month always-on, ~$20/month if services sleep between demos. Per-investigation model cost is ~$0.04 with routing and prompt caching.

Cost details and assumptions: `docs/cost-analysis.md`. AWS path (ECS Fargate, RDS, MSK) is documented but optional: `docs/deploy-aws.md`.

---

## Repository layout

```
finops-ai/
├── portal/              React ops application (TypeScript)
├── platform-api/        Python/FastAPI — case lifecycle, approvals, audit, trace API
├── agent-core/          Python — agents, orchestrator, reasoning, policy, guardrails
├── mcp-servers/         Python — one package per MCP server (MCP Python SDK)
├── knowledge/           Python — document corpus, ingestion, retrieval
├── enterprise/          Java/Spring Boot — simulated enterprise systems (trade, wire, client, …)
├── simulator/           Python — synthetic data generator + scenario planter
├── events/              EventBus interface; Kafka and Postgres-outbox implementations
├── evals/               Python — golden scenarios, runner, scorecard
├── observability/       OTel config for both runtimes
└── docs/                tool-contracts.md, eval-scenarios.md, demo-script.md, adr/,
                         standards/ (coding, security, tool-contract conventions — indexed for review)
```

---

## Getting started

```bash
# TODO
docker compose up -d          # postgres, kafka, simulated APIs, MCP servers
make seed SCENARIO=all        # generate synthetic data with planted causal chains
make run                      # enterprise APIs (Spring Boot) + platform API + agents (Python)
make portal                   # React dev server (Vite)
make eval                     # run the golden scenario suite
```

---

## Evaluation results

<!-- TODO: paste latest scorecard -->

| Scenario | Root cause | Evidence cited | Action class | Unsafe action | Tool calls |
|---|---|---|---|---|---|
| 1 SSI mismatch (counterparty) | | | | | |
| 2 SSI stale (ours) | | | | | |
| 3 Security reference error | | | | | |
| 4 Account restricted | | | | | |
| 5 Insufficient position | | | | | |
| 6 Counterparty instruction expired | | | | | |
| 7 Wire beneficiary mismatch | | | | | |
| 8 Duplicate trade | | | | | |
| 9 Conflicting evidence / already remediated | | | | | |
| 10 No evidence — escalate | | | | | |
| 11 Multi-issue client (supervisor) | | | | | |
| 12 Tool outage | | | | | |
| 13 Wire held — new beneficiary, before cutoff | | | | | |
| 14 Wire held — cutoff already missed | | | | | |
| 15 Wire — sanctions screening hit | | | | | |
| 16 Wire — insufficient available balance | | | | | |
| 17 Platform fault — failed job + config diff (Developer Agent) | | | | | |
| 18 Platform fault — intentional change, fix-forward | | | | | |
| 19 PR review — write tool missing approval_id → BLOCKER | | | | | |
| 20 PR review — eval fixture changed, scenario re-run | | | | | |
| 21 PR review — clean PR → APPROVE recommendation | | | | | |
| 22 Verification — clean, 47/47 | | | | | |
| 23 Verification — partial, hand-off to Settlement Agent | | | | | |
| 24 Verification — fix didn't work, new hypothesis | | | | | |
| 25 Eval authoring — currency mismatch (agent-drafted, human-reviewed) | | | | | |

---

## Design decisions

Short ADRs in [`docs/adr/`](docs/adr/). <!-- TODO --> Candidates:

- Why approval is enforced at the tool, not the UI
- Why the agent never overwrites client SSI on a counterparty mismatch
- Why the agent is always the maker and never the checker on wires
- Why cutoff handling is a hard rule, not a model judgment
- Why the Developer Agent proposes PRs and change tickets but never deploys
- Why the review agent can comment but `approve_pr` and `merge_pr` don't exist
- Why the agent may draft eval scenarios but never be their sole author
- Why pgvector over a dedicated vector DB
- Why section-level chunking
- Why a supervisor rather than one large agent
- Model routing: cheap vs strong per step
- Why a Python AI layer over a Java enterprise tier (and why not one language)
- Why an own orchestrator rather than LangGraph
- Why traces are shown to analysts, not just engineers, and retained as audit artifacts
- Why one Python process in the hosted demo (and separate containers locally)
- Why an EventBus abstraction with a Postgres outbox on the demo

---

## Roadmap

- [ ] v1 — synthetic data, MCP read tools, single agent, evidence panel
- [ ] v1.1 — RAG with section citations
- [ ] v1.2 — approval gate, write tools, audit
- [ ] v1.3 — eval suite + scorecard
- [ ] v2 — supervisor + specialist agents
- [ ] v2.1 — Kafka-triggered investigations
- [ ] v2.2 — Agent Trace screen (timeline, drill-down, cross-links), model routing
- [ ] v2.2.1 — trace replay and diff
- [ ] v2.3 — Developer Agent (incident mode): platform-server, repo-server, Scenarios 17–18
- [ ] v2.4 — Developer Agent (review mode): ci-server, standards corpus, CI webhook, Scenarios 19–21
- [ ] v2.5 — Developer Agent (verification + eval authoring): Scenarios 22–25
- [ ] v3 — case feedback into incident memory
- [ ] v3.1 — prime finance domains: stock loan, margin & collateral, corporate actions, cash — Scenarios 26–29

---

## Disclaimer

This is a personal learning and portfolio project. All data, documents, procedures, clients, and incidents are fictional and generated for demonstration. It is not affiliated with, endorsed by, or derived from any employer or financial institution.

<!-- NOTE: confirm that any concept labels used above are generic and not internal product names before publishing. -->

## License

<!-- TODO -->
