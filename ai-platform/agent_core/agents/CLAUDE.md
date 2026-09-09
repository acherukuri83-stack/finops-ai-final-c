# agent_core/agents — conventions (Phase C)

- One runner. `base.run_specialist(spec, *, subject, request, client, ...)` is the plan →
  tool loop → synthesize → `outcomes.classify` → `policy.apply` → `Finding` core, lifted
  out of `loop.py`. Specialists differ only by their `SpecialistSpec`, never by a forked
  loop.
- `SpecialistSpec` is the whole difference between agents: `planner_prompt`,
  `synthesis_prompt`, `tool_servers` (MCP scope — the planner only ever sees these),
  `allowlist_key` (policy), `subject_type`, `budget`, `required_tools`.
- Structural separation, not prompt separation. Settlement reads `client`/SSI but
  `update_ssi` is **not** on its allowlist — only Risk/Client's. A specialist proposing
  an action outside its key gets it dropped with a REJECTED `policy` span and a note in
  `open_questions` (`policy/allowlists.yaml`).
- `registry.py` holds the specs. `spec_for(name)` looks one up by `name`.
- `loop.investigate()` stays the single-trade entry point → `run_specialist(SETTLEMENT, …)`
  nested inside its own `investigate` span so guardrail + specialist share one trace.
- The Supervisor (`agent_core/supervisor.py`, PR 2) fans out `run_specialist(...)` calls
  with `open_case=False` and owns the single client-level case.
- `proposed_by` is stamped on every `ProposedAction` (the spec's `name`); the Supervisor
  re-checks each grouped action against the *proposing* specialist's allowlist.
