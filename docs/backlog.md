# Backlog

Ideas that are out of the current phase's scope. Append; don't build.

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
  - **`schema_validation` guardrail span** — `complete_structured_traced` retries JSON
    validation up to twice and reports neither the attempt count nor a span. Add it
    without pulling `agent_core.spans` into `model_client.py`: have
    `complete_structured_traced` return `(obj, resp, attempts)` and let the callers in
    `agent_core/agents/base.py` (`_plan`, `_synthesize`) + `guardrails/input_classification.py`
    + `agent_core/supervisor.py` emit a `guardrail` span (`name = schema_validation`,
    `result`, `count = attempts - 1`).
  - **`finops.tool.retries`** — `_enterprise._request` retries a 5xx / transport error
    once but the count is local. Thread it out (a `retries` field on the returned dict, or
    a contextvar the tool span reads) and set it in `agents/base.py::_run_step`. Today
    `_run_step` could stamp a constant `0` to satisfy the "attribute present" letter of
    the standard, but the real per-call value needs this plumbing.
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
  holding Sc. 8 at 2/3. **Not yet eval-validated** (run was cancelled). Confirm 9/9 on the
  next manual sweep; if still 8/9, the earlier hill-climb notes above apply.
- Phase C PR 2 (Supervisor): the **Knowledge specialist is registered but not dispatched**
  — `agent_core/prompts/supervisor/decompose.md` only emits `settlement` / `risk_client`
  sub-tasks, and `supervisor._decompose` filters to those two. Wiring Knowledge means a
  degenerate `run_knowledge` (a fixed `ops.search_knowledge` + `ops.find_incidents` call,
  no planner, read-only, returns cited evidence + a one-line relevance note per chunk) in
  `agent_core/agents/base.py` and a `knowledge` branch in the decompose prompt. Left out
  of PR 2 to keep it reviewable; Scenario 11 does not need it.
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
  - **eval-authoring mode** — SOP section → scenario YAML + `expect:` + fixtures →
    baseline `run_eval` → draft PR labelled `authored_by: agent` (blocked from merge
    without a human reviewer).
  - **Supervisor hand-off** — `agent_core/supervisor.py` should route to
    `developer.investigate_incident` when every business sub-finding is
    `INSUFFICIENT_EVIDENCE`. Today `investigate_incident` is only reachable via
    `POST /diagnose`.
  - **standards corpus** — `docs/standards/` indexed for review-mode retrieval.
  - `platform` server data is Python fixtures in `mcp_servers/platform/store.py` (not the
    simulator / Postgres) — fine for the slice; a fuller Phase E may move it to a seeded
    table with a `simulator` planter, like the enterprise tier.
- Phase F core slice (2026-09-09, PR TBD): shipped **Stock Loan only** as in-process
  Python fixtures (`mcp_servers/stockloan/store.py`), not a seeded table. Deferred:
  - **Margin & collateral**, **corporate actions**, **cash** domains — each its own MCP
    server + specialist + allowlist + prompts + hard rules (call windows, record-date
    logic, funding ladders), one at a time (`docs/agent-plan.md` Phase 13).
  - **Seeded data + simulator planter** for stock loan (loans/recalls against real
    positions), replacing the fixture store — like the enterprise tier.
  - ~~Scenario 30~~ **mechanism DONE (2026-09-09)** — the Supervisor correlating a
    `settlement` + `stockloan` sub-finding into one mixed-domain client answer is exercised
    by `tests/test_supervisor.py::test_correlates_a_mixed_domain_client` (+ the re-policy
    drop test). A **scored** Sc. 30 YAML still waits on stock-loan data being seeded so
    `investigate_client` can *discover* the loan the way it discovers failed trades (today
    `supervisor._failed_trades` only queries `find_trades`). Wires are out (optional module).
  - **Portal affordance** — `investigate_loan` is reachable only via
    `POST /investigate {loan_id}`; no Stock Loan tab.
  - `market` / `position` are on the `stockloan` spec's scope but the slice's fixtures /
    tests don't exercise a price move or a real position lookup.
