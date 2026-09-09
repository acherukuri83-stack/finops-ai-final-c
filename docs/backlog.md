# Backlog

Ideas that are out of the current phase's scope. Append; don't build.

**Status (2026-09-09): the deferred-depth backlog is closed; the optional Wires module has
a core slice.** Every mainline A–G phase has a merged core slice plus its deferred depth,
either shipped or closed-as-accepted with a rationale inline below (search
`Closed (2026-09-09)`). The optional **Wires** module now has a merged core slice —
`mcp_servers/wire/`, `agent_core/wire.py`, the four maker/checker/cutoff/screening hard
rules, `POST /investigate {wire_id}`, `tests/test_wire.py` (Sc. 7 / 13–16 unit-tested).
One thing remains by explicit owner decision, not a gap: the end-of-project
`workflow_dispatch` eval sweep + refreshed `evals/SCORECARD.md` (paused for C+ during the
build; the record stays Phase A 8/9). Older `revisit-if-a-scenario-needs-it` notes below
stay as-is — they're pointers, not open work.

- Phase B (Wires) module (2026-09-09):
  - Core slice: the Wire specialist + `wire` server + the four maker/checker/cutoff/
    screening hard rules + `POST /investigate {wire_id}` + `tests/test_wire.py` (9).
  - ~~seeded Postgres + `simulator` planter for the wire scenarios~~ **DONE (2026-09-09)**
    — `wire/store.py` moved onto `_finance_store.FinanceStore` (MEM + SQL); 6 tables
    mirrored in `simulator/simulator/wire_tables.py` + populated by `wire_baseline.py`;
    `wires` / `standing_instructions` / `wire_screening` planter keys;
    `simulator/scenarios/00{7}_*.yaml` + `01{3,4,5,6}_*.yaml` with `subject: wire`
    `expect:` blocks; `evals/harness.py` dispatches a `subject: wire` scenario to
    `investigate_wire`. `simulator/tests/test_seed_integration.py` (+2). **Scored `make
    eval` run stays deferred** with the C+ sweep (owner decision) — the YAMLs are ready.
  - ~~`_held_wires` Supervisor discovery~~ **DONE (2026-09-09)** —
    `supervisor._held_wires(client_id)` pulls the client's HELD wires (`wire.list_wires`)
    and feeds `_decompose` (`_format_wires`), so a client-level ask can raise a `wire`
    sub-task the way it raises `settlement` / `stockloan`. `_apply_domain_rule` already
    runs `_enforce_wire_controls` on the sub-finding. `tests/test_supervisor.py` (+2).
  - ~~wire corpus~~ **DONE (2026-09-09)** — `knowledge/corpus/wire-processing-guide.md`
    (§3.1 hold reasons, §5.2 new beneficiary, §7.4 available funds, §9.1 same-day cutoffs,
    §11.2 value-date reschedule), `knowledge/corpus/sanctions-procedure.md` (§2.1 hits,
    §2.4 referral + freeze), `knowledge/corpus/incidents/INC-2001…2005.md`. `planner/wire.md`
    + `synthesis/wire.md` cite the governing section; the wire scenarios' `required_evidence`
    names it. Ingested by the standard `python -m knowledge.ingest` glob (CI does this).
  - ~~portal `WIRE_REVIEWER` release flow~~ **DONE (2026-09-09)** — `GET /wire/queue`,
    `GET /wire/exceptions`, `POST /wire/release {wire_id, released_by, role}` in
    `platform_api/main.py` (role-gated to `WIRE_REVIEWER`; 403 otherwise). `wire.store`
    gains `release_wire` (mark RELEASED, close the OPEN route action, record a `release`
    action) and `exceptions`; `_finance_store.FinanceStore.update` added for the
    human-initiated mutation. `portal/src/WireReviewView.tsx` — a **Wire Review** tab with
    the reviewer queue (+ Release button) and the exception report. Still **no
    `release_wire` agent tool**. `tests/test_wire_review.py` (3). **Phase B is complete.**

- `docs/tool-contracts.md`'s `Account` shape lists `risk_flags[]`, and `Client`/`Counterparty`
  mention `restrictions[]`/`contacts[]` — the Phase A schema (`V2__phase_a_schema.sql`) has no
  risk-flag or counterparty-contact tables, and restrictions are only modeled at the account
  level. PR2's enterprise endpoints return `risk_flags: []` and `contacts: []` always (no data
  source), and `GET /clients/{id}` aggregates restrictions across the client's accounts rather
  than having its own restrictions table. Revisit if a scenario ever needs real values here.
- `PUT /accounts/{id}/ssi` (enterprise write endpoint) always creates a new SSI version and
  closes out the prior one; it has no concept of validating the caller's intent beyond that —
  by design, since `update_ssi`'s approval/rationale checks are the MCP tool's job in W3, not
  this tier's.
- W1 PR3: the MCP servers honour `AI_PLATFORM_SPLIT=1` (they skip in-process mounting), but
  Compose does not yet define per-server services for actually running them split. No Phase A
  validation needs it; add the ~8 Compose services if/when a split deployment is exercised.
- W1 PR3: `ops.search_logs` exposes `from`/`to` as `from_ts`/`to_ts` because `from` is a
  Python keyword — the only place a tool signature can't match `docs/tool-contracts.md`
  verbatim. `get_ssi`'s `security_type` and `get_position`'s `as_of` are accepted but not
  forwarded (the Phase A enterprise endpoints take neither).
- W2: `settings.finops_strong_model = "claude-sonnet-4-6"` is a valid model id
  (previous-generation Sonnet). `claude-sonnet-5` is the current-gen alternative if the
  eval scorecard shows the strong model is the weak link — that's a model-choice call, not
  a bug.
- W2: `fastembed` pulls the `bge-small-en-v1.5` ONNX model from Hugging Face on first use.
  This fails behind the corporate TLS proxy locally (`CERTIFICATE_VERIFY_FAILED`); CI
  runners download it fine. To ingest/retrieve locally, point `SSL_CERT_FILE` at a bundle
  that includes the corporate root CA, or run on an unfiltered network. Same stance as
  `ScenarioContractTest`.
- W3 PR2: eval scorecard shows **Sc. 8 (duplicate_trade) at 0–1/3**, deterministically
  67% evidence — right root cause (`DUPLICATE_BOOKING`), right action (`cancel_trade`,
  no unsafe), but the run cites only 2 of `[find_trades, search_logs, "Trade Exception
  Procedure §6.1"]`. A DUPLICATE_SUSPECT synthesis branch + a planner knowledge-retrieval
  step were added and did not move it — retrieval likely isn't surfacing §6.1 for the
  query the planner forms. Hill-climb with `make eval SCENARIO=8 N=3` (the CLI now dumps
  the worst run's Finding on failure): check what `ops.search_knowledge` returns for the
  duplicate case and whether the log line is being cited. Every other scenario passes
  n=3 (Sc. 12 excluded — needs process-global FAULT_INJECT).
- ~~W4: `span_payload` stored unredacted — `trace_store.redact()` is an identity seam.~~
  **Done (Phase G, 2026-09-09):** `trace_store.scrub()` / `redact()` is a real recursive
  scrubber (emails, 9+-digit runs, person-name keys); `record_span` stamps
  `finops.pii.redactions` (count only). Realised as a span **attribute**, not a separate
  `guardrail` span — the scrub runs inside `PostgresSpanProcessor.on_end` and emitting a
  span there would recurse.
- Still open from that entry (Phase G, later passes):
  - ~~**`schema_validation` guardrail span**~~ **DONE (2026-09-09, PR #25)** —
    `complete_structured_traced` emits a `guardrail` span
    (`finops.guardrail.name = schema_validation`, `result` ok/failed,
    `count` = retries used) on every structured-output call. `agent_core.spans` is
    imported lazily in a helper so `model_client` stays dependency-free at load; a tracing
    failure never breaks a model call. `tests/test_model_client.py` (+3).
  - ~~**`finops.tool.retries`**~~ **DONE (2026-09-09, PR #25)** — `_enterprise._request`
    records its in-call retry count in a `ContextVar`; `last_retries()` reads it back;
    `agents/base.py::_run_step` stamps `finops.tool.retries` on every `tool` span (0 for
    in-process fixture servers, which don't go through `_request`).
    `tests/test_mcp_errors.py` (+1).
  - **trace replay / diff "polish"** — **Closed (2026-09-09) — no concrete item.** The
    mechanism ships (`POST /traces/{id}/replay`, `GET /traces/diff`, portal Traces tab).
    "Polish" was never specified; reopen with a specific defect or want.
  - **Bedrock model-client swap** — **Closed (2026-09-09) — out of scope for the build.**
    `ModelClient` is an interface; a Bedrock impl is a deployment choice that needs AWS
    infra + creds + an owner decision, not a code gap. Reopen when a Bedrock deployment is
    actually on the table.
  - **memory loop** (agent writing back learned facts) — **Closed (2026-09-09) — research
    direction, not a build item.** Nothing in A–G depends on it. Reopen as its own scoped
    proposal if pursued.
- Build-phase policy (2026-09): the CI `eval` workflow is **manual-dispatch only** — the
  `pull_request` path trigger was removed to stop ~$2/35-min real-model runs firing on
  every PR (and every no-op re-push) during active development. This reverses the W3
  decision ("CI eval n=3 on every sensitive-path PR").
  **Updated (2026-09, owner decision): no eval sweeps for Phase C or any later phase
  during the build.** Phases C→G ship on `scripts/verify.sh` + unit/contract tests +
  design review, without a per-phase scenario sweep. A single full `workflow_dispatch`
  sweep + refreshed `evals/SCORECARD.md` is deferred to the **end of the project**; the
  `SCORECARD.md` on record stays the Phase A 8/9. Accepted risk: a model-behaviour
  regression in a specialist or the Supervisor would not be caught until that final sweep.
  To re-enable a standing pre-merge gate, re-add the `pull_request:` paths block to
  `.github/workflows/eval.yml` (it's in git history) — optionally label-gated
  (`if: contains(labels, 'run-eval')`) or at n=1 to keep it cheap.
- Sc. 8 (duplicate_trade): the `synthesis/finding.md` DUPLICATE_SUSPECT branch now names
  `{kind: log, ref: search_logs}` as required evidence (PR #11) — on the live deploy the
  agent calls `search_logs` 3× but omitted it from `evidence`, which is the one ref
  holding Sc. 8 at 2/3. **Blocked on the end-of-project eval sweep** (no sweeps for C+
  during the build — owner decision). This is a known item for that sweep, not open
  deferred depth: confirm 9/9 then; if still 8/9, the earlier hill-climb notes above apply.
- ~~Phase C PR 2 (Supervisor): the **Knowledge specialist is registered but not
  dispatched**~~ **DONE (2026-09-09)** — `agents/base.py::run_knowledge`: a degenerate
  runner (fixed `ops.search_knowledge` + `ops.find_incidents`, no planner, no model call,
  proposes nothing) → a `Finding` with cited `evidence` and a one-line relevance note per
  chunk in `checked`, `subject.type = "knowledge"`. `supervisor._decompose` `routable`
  set + `_dispatch` route it; `supervisor._business()` excludes a `knowledge` sub-finding
  from the client outcome reconciliation and the all-INSUFFICIENT incident recommendation
  (retrieval is background, not a verdict). `decompose.md` rewritten to cover all seven
  agents (this also closed the latent gap where `margin` / `corpactions` / `cash` were
  `routable` in code but never described in the prompt). `tests/test_specialists.py` (+2),
  `tests/test_supervisor.py` (+2). A scored eval still isn't run (no sweeps during build).
- Phase C closed 2026-09-09 (PRs #14, #16) **without an eval sweep** per the policy note
  above. If the deferred end-of-project sweep is ever run, Phase C's target set is
  scenarios 1–6, 8–10, 12 (specialists must reproduce the Investigator's Phase A results
  — every Phase A scenario is still a single-specialist Settlement run) plus the new
  client-subject Sc. 11 (`groups` scoring).
- Phase D (events): the **Kafka bus** (`platform_api/events/kafka.py`) is a lazy-import
  adapter — `aiokafka` is not a dependency and there is no broker in CI, so it is
  unexercised. The Postgres-outbox bus is the real, tested path. To use Kafka locally:
  `pip install aiokafka`, run Redpanda (Compose), set `EVENT_BUS=kafka` + `KAFKA_BOOTSTRAP`.
- Phase D: the consumer only routes **trade-subject FAILED settlement events**. Wire/HELD
  events and client-subject events are `OUT_OF_SCOPE` in the consumer — they land with the
  Wires module / a later phase. The `deadline` → HIGH-priority mechanism is built and
  tested; the wire-cutoff scenario that exercises it end-to-end ships with Wires.
- Phase D: `outbox_events` DDL is defined in **two** places — `platform_api/store.py`
  (authoritative) and `simulator/simulator/events.py` (`ensure_outbox`, idempotent). Keep
  the column list in sync by hand, same as `simulator/tables.py` mirrors the Flyway schema.
- Phase E core slice (2026-09-09, PR TBD): shipped **incident mode only**. Deferred, all
  from `docs/agent-plan.md` Phases 11–12:
  - ~~verification mode~~ **DONE (2026-09-09)** — `agent_core/developer.py::verify_change`
    (`POST /verify`): `apply_change_ticket` simulates the effect deterministically, re-checks
    the job run + topic lag, hands residual trades to the Settlement specialist as
    `sub_findings`, writes a retrievable `INC-3xxx` on a clean fix; a failed fix reports
    FAILED + "re-enter incident mode excluding <hypothesis>" and proposes nothing. Residual
    hand-off is direct to `run_specialist(SETTLEMENT)`, not yet via the Supervisor.
  - ~~PR-review mode~~ **DONE (2026-09-09)** — `repo` + `ci` in-process fixture servers,
    `agent_core/schemas/review.py` + `agent_core/review.py` (`POST /review`): surface
    classification, deterministic checks (security scan / tests / coverage / static), and
    the platform hard rules as code (write tool w/o `approval_id` → BLOCKER
    `security.md §4.1`; new `action_type` off every allowlist → MAJOR §5; PII into a model
    call → BLOCKER §7; `authored_by: agent` scenario → MAJOR + forced `REQUEST_CHANGES`).
    No `approve_pr` / `merge_pr` tool. **Deferred:** the model interpretation /
    prioritisation layer over the deterministic results (the slice is fully code);
    standards retrieval is a direct `docs/standards/*.md` § cite, not pgvector;
    `repo.get_source` dropped as redundant with `platform.get_source`.
  - ~~eval-authoring mode~~ **DONE (2026-09-09)** — `agent_core/eval_authoring.py::author_scenario`
    (`POST /author-scenario`): a **template per known failure code** →
    `AuthoredScenario` (planted-chain YAML + `expect:` block + `ci.run_eval` baseline),
    labelled `authored_by: agent` — which PR-review mode (`review._code_rules`) already
    forces `REQUEST_CHANGES` on until a human signs off. `tests/test_eval_authoring.py` (7).
    **Closed (2026-09-09) — accepted as-is:** the fixed 3-code template map covers every
    failure code the eval suite actually exercises. A model-driven "from any SOP section"
    version is a **feature**, not a gap — it would add model calls + a validation surface
    for marginal coverage; reopen if a new failure code needs authoring and no template
    fits. It does not open the draft PR itself by design (`open_pull_request` is
    approval-gated — a human raises it from the artifact).
  - ~~Supervisor hand-off~~ **BOUNDED VERSION DONE (2026-09-09)** —
    `supervisor._recommend_incident_review`: when *every* dispatched sub-finding is
    `INSUFFICIENT_EVIDENCE`, the client `Finding` gets an `open_questions` note
    recommending `POST /diagnose` with the suspected job / service.
    `tests/test_supervisor.py` (+2). **Closed (2026-09-09) — the recommendation is the
    resolution:** full auto-dispatch (the Supervisor calling `developer.investigate_incident`
    itself) has no safe default for "which platform subject" — synthesising a job id /
    service the client's sub-findings never named would violate rule 7 (never invent ids).
    The bounded note hands a human the exact next step. Reopen only with a concrete design
    for deriving the subject (e.g. from recent failed job runs / degraded `/connections`
    health) that a human still confirms.
  - ~~standards corpus~~ **Closed (2026-09-09) — accepted as-is:** `agent_core/review.py`
    cites `docs/standards/*.md` sections directly (`security.md §4.1` etc.) from code
    rules. Indexing them in pgvector for retrieval would add a dependency, a failure mode,
    and latency for no accuracy gain — the section refs are fixed, not discovered. Reopen
    if review mode ever needs to *find* an unknown-in-advance section.
  - `platform` server data is Python fixtures in `mcp_servers/platform/store.py` (not the
    simulator / Postgres) — fine for the slice; a fuller Phase E may move it to a seeded
    table with a `simulator` planter, like the enterprise tier.
- Phase F core slice (2026-09-09): shipped **Stock Loan only**, originally as in-process
  Python fixtures. All four domains later shipped, and (2026-09-09) all four stores moved
  onto seeded Postgres — see the "Seeded data + simulator planter" entry below. Deferred:
  - ~~Margin & collateral~~ **DONE (2026-09-09)** — `mcp_servers/margin/` (in-process
    fixture server: calls / status / collateral / eligibility), `MARGIN` spec,
    `agent_core/margin.py::investigate_margin_call`, `planner/margin.md` +
    `synthesis/margin.md`, **meet-vs-close-out hard rule in code**
    (`_enforce_call_window` on `due_by`), `POST /investigate {margin_call_id}`, Supervisor
    `margin` sub-task. `tests/test_margin.py` (5).
  - ~~corporate actions~~ **DONE (2026-09-09)** — `mcp_servers/corpactions/` (events /
    entitlements / elections), `CORPACTIONS` spec, `agent_core/corpactions.py::investigate_ca_event`,
    `planner/corpactions.md` + `synthesis/corpactions.md`, **record-date hard rules in
    code** (`_enforce_record_date`: cash dividend on a lent slice → `raise_claim` on the
    borrower; elective event past its deadline → `escalate_ca`), `POST /corpaction`,
    Supervisor `corpactions` sub-task. `tests/test_corpactions.py` (5).
  - ~~cash~~ **DONE (2026-09-09)** — `mcp_servers/cash/` (breaks / funding ladders /
    facilities), `CASH` spec, `agent_core/cash.py::investigate_cash_break`,
    `planner/cash.md` + `synthesis/cash.md`, **fund-vs-escalate hard rule in code**
    (`_enforce_funding_cutoff` on the currency `funding_cutoff`), `POST /investigate
    {cash_break_id}`, Supervisor `cash` sub-task. `tests/test_cash.py` (5). **All four
    prime-finance domains are now shipped** (stockloan / margin / corpactions / cash).
  - ~~Seeded data + simulator planter for the prime-finance domains~~ **DONE (2026-09-09)**
    — all four domain stores (`mcp_servers/{stockloan,margin,corpactions,cash}/store.py`)
    now sit on `mcp_servers/_finance_store.py`: a MEM mode (the old fixtures, byte-for-byte,
    for the unit suite) and a SQL mode over seeded Postgres. 14 platform-tier tables
    (`CREATE TABLE IF NOT EXISTS`, no Flyway), mirrored in `simulator/simulator/finance_tables.py`
    + populated by `simulator/simulator/finance_baseline.py` on `make seed`. New `loans` /
    `lending` planter keys; **`margin_calls` / `ca_events` / `ca_entitlements` /
    `cash_breaks` planter keys added too (2026-09-09)** — exercised by
    `simulator/tests/test_seed_integration.py::test_prime_finance_planter_handlers_are_idempotent`.
    `supervisor._open_loans` discovers a client's open loans from the accounts its FAILED
    trades touch and feeds them to `_decompose`. The Supervisor fan-out now runs the
    per-domain hard rule on each sub-finding — `supervisor._apply_domain_rule` calls
    `_enforce_recall_window` / `_enforce_call_window` / `_enforce_funding_cutoff` /
    `_enforce_record_date` after `run_specialist` (fixed 2026-09-09; `tests/test_supervisor.py`
    +2). All items on this line are done.
  - ~~Scenario 30~~ **SEEDED (2026-09-09)** — `simulator/scenarios/030_mixed_domain_client.yaml`:
    HF101 with one `COUNTERPARTY_SSI_MISMATCH` trade + one open loan `LN-5001`, `expect:`
    with two `groups`. Discovery + correlation covered by `tests/test_supervisor.py` and
    the DB-backed `simulator/tests/test_seed_integration.py`. The **scored** `make eval
    SCENARIO=30` run is deferred with the rest of the C+ sweep (owner decision). Wires are
    out (optional module).
  - ~~Portal affordance~~ **DONE (2026-09-09)** — `portal/src/PrimeFinanceView.tsx`, a
    single **Prime Finance** tab with a domain selector (Stock Loan / Margin / Cash /
    Corp Actions) → the right endpoint (`POST /investigate {loan_id|margin_call_id|
    cash_break_id}` or `POST /corpaction {event_id, account_id}`) → the shared `Finding`
    renderer (outcome / root cause / proposed / rejected / open questions / trace link).
    `api.primeFinance(kind, id)` + `api.corpaction(eventId, accountId)` in `api.ts`.
  - `market` / `position` are on the `stockloan` spec's scope but no test exercises a
    price move or a real position lookup. **Closed (2026-09-09) — test depth, not a gap:**
    the scope wiring is asserted by `tests/test_mcp_contract.py`; the planner can reach
    both servers. A scenario that turns on a buy-in cost or a delivery shortfall would add
    the coverage — reopen with that scenario, not on its own.
