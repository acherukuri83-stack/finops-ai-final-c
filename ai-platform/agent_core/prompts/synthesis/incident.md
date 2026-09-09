Write the `Finding` for this platform incident from the observations.

- `subject`: `{type: "job", id: <job_id>}` (or `{type: "service", id: <service>}` if there
  is no single job).
- `root_cause`: a short code in UPPER_SNAKE — `CONFIG_REGRESSION` (a deploy changed a
  config key that broke behaviour), `BAD_DEPLOY` (a code/deploy change with no config
  diff), `TOPIC_BACKLOG` (a stuck consumer, no bad change). Leave it null if the evidence
  does not support one.
- `blast_radius`: one `SubjectRef` per subject the fault took down — the trades from
  `trade.find_trades(status=FAILED)`. This is *impact*, not something you fix.
- `fix_strategy`:
  - **`revert`** when the causing deployment has **no `release_note`** (or a note that
    does not explain this change) — the change was unintended; roll it back.
  - **`fix_forward`** when the causing deployment's `release_note` explains the change as
    **intentional** (e.g. "PLANNED: … per RISK-2026-04 … do not roll back"). Quote the
    note. The fix is to remediate the data / config forward, not to revert.
  The caller re-checks this against the deployment record — but say which and why.
- `evidence`: one `EvidenceRef` (`kind: "tool"`) per fact you rely on — `get_deployments`
  for the change, `diff_config` for the key, `get_platform_logs` for the abort line,
  `find_trades` for the blast radius, `get_topic_lag` for the backlog size. `get_source`
  where you cite the line.
- `proposed_actions` — from the `developer` allowlist only:
  - `open_change_ticket` with `params`: `kind` = your `fix_strategy`, `target` = the
    causing `deployment_id`, and a one-line `summary`. Then
  - `rerun_job` with `params.job_id` = the failed job, to clear the backlog once the
    ticket is applied.
  Do **not** propose a deploy, a merge, an approval, or a config write — no such tool
  exists, and they are not yours to do.
- `rejected_alternatives`: name the strategy you did **not** choose. If `revert`, say
  `fix_forward` is rejected because no release note explains the change. If `fix_forward`,
  say `revert` is rejected and quote the release note.
- `confidence_basis`: one sentence — what the conclusion rests on.

Do not invent deployment ids, job ids, config keys, or file paths. Every id in the
Finding must appear in an observation.
