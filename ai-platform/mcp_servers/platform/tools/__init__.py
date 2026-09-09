"""platform-server tools (Phase E). Docstrings are the exposed descriptions.

Reads over the simulated platform tier (`mcp_servers.platform.store`). The three writes
validate an APPROVED `approval_id` in the tool (ADR-0001) before touching the change-ticket
table — the same gate the enterprise write tools use. **No deploy / merge / config-write
tool exists** (a test asserts this).
"""

from __future__ import annotations

from typing import Any

from mcp_servers._common import check_approval
from mcp_servers.platform import store


async def get_service_health(service: str = "") -> Any:
    """Health of one platform service (status HEALTHY/DEGRADED/DOWN, running version) or all of them if `service` is omitted."""
    if not service:
        return store.services()
    row = store.service_health(service)
    return row or {
        "code": "NOT_FOUND",
        "message": f"no service {service}",
        "retryable": False,
        "tool": "get_service_health",
    }


async def get_job_runs(name: str = "") -> Any:
    """Recent batch-job runs (job_id, result SUCCEEDED/FAILED, exit_code, timestamps). Filter by job `name`; newest first."""
    return store.job_runs(name or None)


async def get_deployments(service: str = "") -> Any:
    """Deployments in reverse-chronological order (deployment_id, service, at, by, commit, release_note, config_change). A non-null `release_note` explaining a change means it was intentional."""
    return store.deployments(service or None)


async def diff_config(deployment_id: str) -> Any:
    """The config keys a deployment changed: [{key, from, to}]. A key whose `from` == `to` was untouched."""
    diff = store.config_diff(deployment_id)
    if diff is None:
        return {
            "code": "NOT_FOUND",
            "message": f"no config diff for {deployment_id}",
            "retryable": False,
            "tool": "diff_config",
        }
    return diff


async def get_topic_lag(topic: str) -> Any:
    """Consumer lag on a message-bus topic: {topic, lag, consumers}. Lag > 0 means unprocessed events are piling up."""
    row = store.topic_lag(topic)
    return row or {
        "code": "NOT_FOUND",
        "message": f"no topic {topic}",
        "retryable": False,
        "tool": "get_topic_lag",
    }


async def get_platform_logs(job_id: str = "") -> Any:
    """Platform-tier log lines (scheduler / engine), optionally scoped to a `job_id`. Distinct from ops.search_logs (which is enterprise app logs)."""
    return store.platform_logs(job_id or None)


async def get_source(ref: str) -> Any:
    """A source window around a `file:line` ref (e.g. `settlement-engine/match.py:88`): {path, line, window, last_changed_by}."""
    row = store.source_at(ref)
    return row or {
        "code": "NOT_FOUND",
        "message": f"no source at {ref}",
        "retryable": False,
        "tool": "get_source",
    }


async def get_incident(incident_id: str = "") -> Any:
    """A platform incident written by verification (symptom / cause / fix / verification), or all of them if `incident_id` is omitted."""
    if not incident_id:
        return store.incidents()
    row = store.get_incident(incident_id)
    return row or {
        "code": "NOT_FOUND",
        "message": f"no incident {incident_id}",
        "retryable": False,
        "tool": "get_incident",
    }


async def open_change_ticket(kind: str, target: str, summary: str, approval_id: str) -> Any:
    """Open a change ticket (`kind`: revert | fix_forward | rerun; `target`: a deployment_id or job_id). Requires an APPROVED approval_id. Does NOT deploy — a human executes the ticket."""
    denied = check_approval("open_change_ticket", target, approval_id)
    if denied:
        return denied
    ticket = store.add_change_ticket(kind, target, summary, approval_id)
    _audit(approval_id, f"opened change ticket {ticket['ticket_id']} ({kind} {target})")
    return ticket


async def rerun_job(job_id: str, approval_id: str) -> Any:
    """Re-queue a failed batch job. Requires an APPROVED approval_id. Records the request; a human/scheduler runs it."""
    denied = check_approval("rerun_job", job_id, approval_id)
    if denied:
        return denied
    _audit(approval_id, f"queued rerun of {job_id}")
    return {"job_id": job_id, "queued": True, "approval_id": approval_id}


async def replay_message(topic: str, key: str, approval_id: str) -> Any:
    """Replay a stuck message on a bus topic by key. Requires an APPROVED approval_id."""
    denied = check_approval("replay_message", key, approval_id)
    if denied:
        return denied
    _audit(approval_id, f"replayed {topic} key {key}")
    return {"topic": topic, "key": key, "replayed": True, "approval_id": approval_id}


def _audit(approval_id: str, event: str) -> None:
    from platform_api import cases

    approval = cases.get_approval(approval_id)
    if approval:
        cases.log_audit(approval["case_id"], f"executed {event} via {approval_id}")
