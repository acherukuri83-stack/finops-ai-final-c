"""In-process fixture store for the `platform` server (Phase E).

The platform tier — job scheduler, deploy pipeline, config service, message bus — is
*simulated* the same way the enterprise tier is, but small enough to live in Python (no
Java). These are planted **facts**: a job failed, a deploy changed a key, a topic has
lag. Nothing here states *why*. The Developer Agent derives the cause.

`change_tickets` is the one mutable table — `open_change_ticket` appends to it after an
APPROVED approval, mirroring how the enterprise write tools mutate their tier.
"""

from __future__ import annotations

from typing import Any

# --- planted fixtures --------------------------------------------------------

_SERVICES: dict[str, dict[str, Any]] = {
    "settlement-engine": {
        "service": "settlement-engine",
        "status": "DEGRADED",
        "version": "dep-88",
    },
    "affirmation-gateway": {
        "service": "affirmation-gateway",
        "status": "HEALTHY",
        "version": "dep-70",
    },
    "position-service": {"service": "position-service", "status": "HEALTHY", "version": "dep-81"},
}

_JOB_RUNS: list[dict[str, Any]] = [
    {
        "job_id": "job-4471",
        "name": "settlement-batch",
        "started_at": "2026-09-04T06:00:00",
        "finished_at": "2026-09-04T06:04:30",
        "result": "FAILED",
        "exit_code": 1,
        "trigger": "cron",
    },
    {
        "job_id": "job-4470",
        "name": "settlement-batch",
        "started_at": "2026-09-03T06:00:00",
        "finished_at": "2026-09-03T06:03:10",
        "result": "SUCCEEDED",
        "exit_code": 0,
        "trigger": "cron",
    },
]

_DEPLOYMENTS: list[dict[str, Any]] = [
    {
        "deployment_id": "dep-88",
        "service": "settlement-engine",
        "at": "2026-09-04T05:40:00",
        "by": "ci.pipeline",
        "commit": "a1b2c3d",
        "release_note": None,  # unexplained change -> revert
        "config_change": True,
    },
    {
        "deployment_id": "dep-70",
        "service": "settlement-engine",
        "at": "2026-08-20T05:40:00",
        "by": "ci.pipeline",
        "commit": "9f8e7d6",
        "release_note": "routine dependency bump",
        "config_change": False,
    },
    # Sc. 18 — an *intentional* change with a note that explains it -> fix_forward
    {
        "deployment_id": "dep-91",
        "service": "position-service",
        "at": "2026-09-04T05:45:00",
        "by": "ci.pipeline",
        "commit": "b2c3d4e",
        "release_note": (
            "PLANNED: enable strict lot-level position checks per RISK-2026-04. "
            "Ops to backfill the affected book; do not roll back."
        ),
        "config_change": True,
    },
]

_CONFIG_DIFFS: dict[str, list[dict[str, Any]]] = {
    "dep-88": [
        {"key": "ssi.match.strict", "from": "false", "to": "true"},
        {"key": "settlement.retry.max", "from": "3", "to": "3"},
    ],
    "dep-91": [
        {"key": "position.check.lotlevel", "from": "false", "to": "true"},
    ],
}

_TOPIC_LAG: dict[str, dict[str, Any]] = {
    "settlement.events": {"topic": "settlement.events", "lag": 47, "consumers": 1},
    "wire.events": {"topic": "wire.events", "lag": 0, "consumers": 1},
}

# platform logs (distinct from the enterprise `ops.search_logs` app logs)
_PLATFORM_LOGS: list[dict[str, Any]] = [
    {
        "ts": "2026-09-04T06:04:29",
        "service": "settlement-engine",
        "level": "ERROR",
        "msg": "job-4471 aborted: 47 records failed ssi.match.strict validation",
        "job_id": "job-4471",
    },
    {
        "ts": "2026-09-04T06:04:30",
        "service": "settlement-engine",
        "level": "ERROR",
        "msg": "batch exit 1 after 47 rejects; see match.py:88",
        "job_id": "job-4471",
    },
]

_SOURCE: dict[str, dict[str, Any]] = {
    "settlement-engine/match.py:88": {
        "path": "settlement-engine/match.py",
        "line": 88,
        "window": (
            "86  def matches(instruction, affirmation):\n"
            "87      if config.get('ssi.match.strict'):\n"
            "88          return instruction.dtc == affirmation.cpty_dtc  # exact only\n"
            "89      return _fuzzy(instruction, affirmation)\n"
        ),
        "last_changed_by": "dep-88",
    },
}

# --- mutable: change tickets, applied effects, incidents -------------------

_CHANGE_TICKETS: list[dict[str, Any]] = []
_INCIDENTS: list[dict[str, Any]] = []
_RESIDUAL_TRADES: list[str] = []
_EXTRA_JOB_RUNS: list[dict[str, Any]] = []  # a SUCCEEDED rerun, after a fix is applied
_LAG_OVERRIDE: dict[str, int] = {}  # topic -> new lag, after a fix is applied
_SEQ = 0
_INC_SEQ = 3011  # verification-written incidents start at INC-3012 (docs/agent-plan.md Sc. 22)


def reset() -> None:
    """Tests: clear the mutable tables and any applied-change effects."""
    global _SEQ, _INC_SEQ
    _CHANGE_TICKETS.clear()
    _INCIDENTS.clear()
    _RESIDUAL_TRADES.clear()
    _EXTRA_JOB_RUNS.clear()
    _LAG_OVERRIDE.clear()
    _SEQ = 0
    _INC_SEQ = 3011


def services() -> list[dict[str, Any]]:
    return [dict(v) for v in _SERVICES.values()]


def service_health(service: str) -> dict[str, Any] | None:
    row = _SERVICES.get(service)
    return dict(row) if row else None


def job_runs(name: str | None) -> list[dict[str, Any]]:
    rows = _EXTRA_JOB_RUNS + _JOB_RUNS  # extras first == newest first
    return [dict(r) for r in rows if name is None or r["name"] == name]


def deployments(service: str | None) -> list[dict[str, Any]]:
    return [dict(d) for d in _DEPLOYMENTS if service is None or d["service"] == service]


def config_diff(deployment_id: str) -> list[dict[str, Any]] | None:
    diff = _CONFIG_DIFFS.get(deployment_id)
    return [dict(d) for d in diff] if diff is not None else None


def topic_lag(topic: str) -> dict[str, Any] | None:
    row = _TOPIC_LAG.get(topic)
    if row is None:
        return None
    row = dict(row)
    if topic in _LAG_OVERRIDE:
        row["lag"] = _LAG_OVERRIDE[topic]
    return row


def platform_logs(job_id: str | None) -> list[dict[str, Any]]:
    return [dict(r) for r in _PLATFORM_LOGS if job_id is None or r["job_id"] == job_id]


def source_at(ref: str) -> dict[str, Any] | None:
    row = _SOURCE.get(ref)
    return dict(row) if row else None


def add_change_ticket(kind: str, target: str, summary: str, approval_id: str) -> dict[str, Any]:
    global _SEQ
    _SEQ += 1
    ticket = {
        "ticket_id": f"CHG-{_SEQ:04d}",
        "kind": kind,  # revert | fix_forward | rerun
        "target": target,
        "summary": summary,
        "status": "OPEN",
        "approval_id": approval_id,
    }
    _CHANGE_TICKETS.append(ticket)
    return dict(ticket)


def change_tickets() -> list[dict[str, Any]]:
    return [dict(t) for t in _CHANGE_TICKETS]


def get_change_ticket(ticket_id: str) -> dict[str, Any] | None:
    return next((dict(t) for t in _CHANGE_TICKETS if t["ticket_id"] == ticket_id), None)


def apply_change_ticket(ticket_id: str) -> dict[str, Any] | None:
    """Simulate a human executing an approved change ticket. The effect is deterministic
    from the ticket's target so verification has all three paths to check:
      - a `revert` of dep-88 (the real cause) fully clears the incident;
      - a `fix_forward` on dep-88 clears the signals but leaves one residual trade;
      - anything else does nothing (the fix missed).
    """
    ticket = next((t for t in _CHANGE_TICKETS if t["ticket_id"] == ticket_id), None)
    if ticket is None:
        return None
    ticket["status"] = "APPLIED"
    if ticket["target"] == "dep-88" and ticket["kind"] in ("revert", "fix_forward"):
        _EXTRA_JOB_RUNS.insert(
            0,
            {
                "job_id": "job-4471b",
                "name": "settlement-batch",
                "started_at": "2026-09-06T09:00:00",
                "finished_at": "2026-09-06T09:03:00",
                "result": "SUCCEEDED",
                "exit_code": 0,
                "trigger": "manual",
            },
        )
        _LAG_OVERRIDE["settlement.events"] = 0
        _RESIDUAL_TRADES[:] = [] if ticket["kind"] == "revert" else ["T100301"]
    return dict(ticket)


def residual_trades() -> list[str]:
    return list(_RESIDUAL_TRADES)


def create_incident(symptom: str, cause: str, fix: str, verification: str) -> dict[str, Any]:
    global _INC_SEQ
    _INC_SEQ += 1
    inc = {
        "incident_id": f"INC-{_INC_SEQ}",
        "symptom": symptom,
        "cause": cause,
        "fix": fix,
        "verification": verification,
        "status": "CLOSED",
    }
    _INCIDENTS.append(inc)
    return dict(inc)


def incidents() -> list[dict[str, Any]]:
    return [dict(i) for i in _INCIDENTS]


def get_incident(incident_id: str) -> dict[str, Any] | None:
    return next((dict(i) for i in _INCIDENTS if i["incident_id"] == incident_id), None)
