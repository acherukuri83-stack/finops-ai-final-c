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

# --- mutable: change tickets ------------------------------------------------

_CHANGE_TICKETS: list[dict[str, Any]] = []
_SEQ = 0


def reset() -> None:
    """Tests: clear the mutable change-ticket table."""
    global _SEQ
    _CHANGE_TICKETS.clear()
    _SEQ = 0


def services() -> list[dict[str, Any]]:
    return [dict(v) for v in _SERVICES.values()]


def service_health(service: str) -> dict[str, Any] | None:
    row = _SERVICES.get(service)
    return dict(row) if row else None


def job_runs(name: str | None) -> list[dict[str, Any]]:
    return [dict(r) for r in _JOB_RUNS if name is None or r["name"] == name]


def deployments(service: str | None) -> list[dict[str, Any]]:
    return [dict(d) for d in _DEPLOYMENTS if service is None or d["service"] == service]


def config_diff(deployment_id: str) -> list[dict[str, Any]] | None:
    diff = _CONFIG_DIFFS.get(deployment_id)
    return [dict(d) for d in diff] if diff is not None else None


def topic_lag(topic: str) -> dict[str, Any] | None:
    row = _TOPIC_LAG.get(topic)
    return dict(row) if row else None


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
