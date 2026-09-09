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
- W4 (Trace screen): `span_payload` is stored **unredacted** — `platform_api/trace_store.redact()`
  is an identity seam. Phase A data is entirely fictional so nothing leaks, but the
  observability standard's "payloads stored post-scrub" line and the `pii_scrub` guardrail
  span are unmet. Phase G: implement `redact()` (drop/obfuscate emails, names, account
  numbers on the way into `span_payloads`) and emit a `guardrail` span reporting the
  redaction count. Same PR should add the `schema_validation` guardrail span from
  `complete_structured_traced`'s retry path (kept out of W4 to keep `model_client.py`
  dependency-free). `finops.tool.retries` is also not emitted — thread the retry count
  out of `mcp_servers/_enterprise._request` when it's wired.
- Build-phase policy (2026-09): the CI `eval` workflow is **manual-dispatch only** — the
  `pull_request` path trigger was removed to stop ~$2/35-min real-model runs firing on
  every PR (and every no-op re-push) during active development. This reverses the W3
  decision ("CI eval n=3 on every sensitive-path PR"). **Before declaring a phase or the
  project done**, run a full `workflow_dispatch` sweep and commit the `SCORECARD.md`. If a
  standing pre-merge gate is wanted again, re-add the `pull_request:` paths block to
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
- Phase C exit: run the manual `workflow_dispatch` eval sweep (scenarios 1–6, 8–10, 12 +
  the new client-subject Sc. 11) and commit `evals/SCORECARD.md` before moving
  `CLAUDE.md` to "C — complete · next mainline phase: D". The specialists must reproduce
  the Investigator's Phase A results at the split (low regression risk — every Phase A
  scenario is still a single-specialist Settlement run).
