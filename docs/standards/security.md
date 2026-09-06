# Security Policy

- §1 Write tools are any MCP tool that mutates enterprise or case state.
- §2 Every write tool takes `approval_id` and calls `case.get_approval` **before** any side effect.
- §3 A write tool proceeds only when status is APPROVED and the approval's `action_type` and target subject match the call. Anything else raises `ApprovalError` and executes nothing.
- §4 Enforcement is in the tool. The UI, the agent, and the orchestrator are not trusted to gate writes. §4.1 A write tool that can execute without §2–§3 is a BLOCKER in review.
- §5 Every proposed action passes `agent_core/policy` against the calling agent's allowlist before `propose_action`. Out-of-allowlist → `PolicyError`, POLICY span, action dropped.
- §6 Agents discover tools through MCP; there is no direct DB or HTTP access from agent code to the enterprise tier.
- §7 Log payloads are scrubbed for PII-shaped fields before entering a model prompt (Phase A: names and emails in log lines). The guardrail span records counts, never the values.
- §8 Roles: `OPS_ANALYST` may approve settlement actions. Later phases add `WIRE_REVIEWER`, `CHANGE_APPROVER`. An approval records role, user, timestamp.
- §9 No real institution names, product names, or conventions anywhere in code, data, or docs.
- §10 Model provider keys and DB credentials come from the environment; never committed.
