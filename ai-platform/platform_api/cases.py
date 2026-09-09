"""Case lifecycle: open a case, register a proposed action for approval, record a human
decision, append audit events. The `case` MCP server and the platform API both call
straight in — no HTTP.

Two backends behind one facade: `SqlBackend` (Postgres, `platform_api.store`) in
production, `MemBackend` (dicts) for unit tests. Selected once by `CASES_INMEMORY=1`;
`set_backend(...)` overrides for a test.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

PENDING, APPROVED, REJECTED = "PENDING", "APPROVED", "REJECTED"


class Backend(Protocol):
    def create_case(
        self,
        subject_type: str,
        subject_id: str,
        summary: str,
        trace_id: str,
        *,
        source: str = "user",
        priority: str = "NORMAL",
        dedup_key: str | None = None,
    ) -> dict[str, Any]: ...
    def update_case(self, case_id: str, notes: str, status: str | None) -> dict[str, Any]: ...
    def set_meta(
        self,
        case_id: str,
        *,
        source: str | None = None,
        priority: str | None = None,
        dedup_key: str | None = None,
    ) -> dict[str, Any]: ...
    def find_open_by_dedup_key(self, dedup_key: str) -> dict[str, Any] | None: ...
    def propose_action(
        self,
        case_id: str,
        action_type: str,
        params: dict[str, str],
        rationale: str,
        impact: list[dict[str, str]],
        reversible: bool,
    ) -> dict[str, Any]: ...
    def get_approval(self, approval_id: str) -> dict[str, Any] | None: ...
    def decide(self, approval_id: str, decision: str, by: str, role: str) -> dict[str, Any]: ...
    def log_audit(self, case_id: str, event: str) -> None: ...
    def list_cases(self) -> list[dict[str, Any]]: ...
    def get_case(self, case_id: str) -> dict[str, Any]: ...


# --- in-memory backend (tests) -------------------------------------------------


class MemBackend:
    def __init__(self) -> None:
        self._cases: dict[str, dict[str, Any]] = {}
        self._approvals: dict[str, dict[str, Any]] = {}
        self._audit: list[dict[str, Any]] = []
        self._n = 0

    def create_case(
        self,
        subject_type: str,
        subject_id: str,
        summary: str,
        trace_id: str = "",
        *,
        source: str = "user",
        priority: str = "NORMAL",
        dedup_key: str | None = None,
    ) -> dict[str, Any]:
        self._n += 1
        case_id = f"CS-{self._n:04d}"
        self._cases[case_id] = {
            "case_id": case_id,
            "subject_type": subject_type,
            "subject_id": subject_id,
            "summary": summary,
            "status": "OPEN",
            "trace_id": trace_id,
            "source": source,
            "priority": priority,
            "dedup_key": dedup_key,
            "created_at": datetime.now(UTC),
        }
        self.log_audit(case_id, f"case opened for {subject_type} {subject_id}")
        return self.get_case(case_id)

    def update_case(self, case_id: str, notes: str, status: str | None) -> dict[str, Any]:
        if case_id not in self._cases:
            raise KeyError(case_id)
        if status:
            self._cases[case_id]["status"] = status
        self.log_audit(case_id, notes + (f" (status -> {status})" if status else ""))
        return self.get_case(case_id)

    def set_meta(
        self,
        case_id: str,
        *,
        source: str | None = None,
        priority: str | None = None,
        dedup_key: str | None = None,
    ) -> dict[str, Any]:
        if case_id not in self._cases:
            raise KeyError(case_id)
        row = self._cases[case_id]
        for k, v in (("source", source), ("priority", priority), ("dedup_key", dedup_key)):
            if v is not None:
                row[k] = v
        return self.get_case(case_id)

    def find_open_by_dedup_key(self, dedup_key: str) -> dict[str, Any] | None:
        for c in sorted(self._cases.values(), key=lambda c: c["created_at"], reverse=True):
            if c.get("dedup_key") == dedup_key and c["status"] not in ("CLOSED", "RESOLVED"):
                return self.get_case(c["case_id"])
        return None

    def propose_action(
        self,
        case_id: str,
        action_type: str,
        params: dict[str, str],
        rationale: str,
        impact: list[dict[str, str]],
        reversible: bool,
    ) -> dict[str, Any]:
        approval_id = f"ap_{uuid4().hex[:8]}"
        self._approvals[approval_id] = {
            "approval_id": approval_id,
            "case_id": case_id,
            "action_type": action_type,
            "params": params,
            "rationale": rationale,
            "impact": impact,
            "reversible": reversible,
            "status": PENDING,
            "decided_by": None,
            "role": None,
            "decided_at": None,
            "created_at": datetime.now(UTC),
        }
        self.log_audit(case_id, f"proposed {action_type} -> {approval_id} (PENDING)")
        return dict(self._approvals[approval_id])

    def get_approval(self, approval_id: str) -> dict[str, Any] | None:
        row = self._approvals.get(approval_id)
        return dict(row) if row else None

    def decide(self, approval_id: str, decision: str, by: str, role: str) -> dict[str, Any]:
        decision = decision.upper()
        if decision not in (APPROVED, REJECTED):
            raise ValueError(f"decision must be {APPROVED} or {REJECTED}, got {decision!r}")
        row = self._approvals.get(approval_id)
        if row is None:
            raise KeyError(approval_id)
        row.update(status=decision, decided_by=by, role=role, decided_at=datetime.now(UTC))
        self.log_audit(
            row["case_id"], f"{row['action_type']} {approval_id} {decision} by {by} ({role})"
        )
        return dict(row)

    def log_audit(self, case_id: str, event: str) -> None:
        self._audit.append({"case_id": case_id, "event": event, "at": datetime.now(UTC)})

    def list_cases(self) -> list[dict[str, Any]]:
        return sorted(
            (dict(c) for c in self._cases.values()), key=lambda c: c["created_at"], reverse=True
        )

    def get_case(self, case_id: str) -> dict[str, Any]:
        if case_id not in self._cases:
            raise KeyError(case_id)
        return {
            **self._cases[case_id],
            "approvals": [dict(a) for a in self._approvals.values() if a["case_id"] == case_id],
            "audit": [dict(e) for e in self._audit if e["case_id"] == case_id],
        }


# --- SQL backend (production) ------------------------------------------------


class SqlBackend:
    def create_case(
        self,
        subject_type: str,
        subject_id: str,
        summary: str,
        trace_id: str = "",
        *,
        source: str = "user",
        priority: str = "NORMAL",
        dedup_key: str | None = None,
    ) -> dict[str, Any]:
        from sqlalchemy import text

        from platform_api import store

        with store.connect() as conn:
            seq = conn.execute(text("select nextval('case_seq')")).scalar_one()
            case_id = f"CS-{int(seq):04d}"
            conn.execute(
                store.cases.insert().values(
                    case_id=case_id,
                    subject_type=subject_type,
                    subject_id=subject_id,
                    summary=summary,
                    trace_id=trace_id,
                    source=source,
                    priority=priority,
                    dedup_key=dedup_key,
                )
            )
            conn.execute(
                store.audit_events.insert().values(
                    case_id=case_id, event=f"case opened for {subject_type} {subject_id}"
                )
            )
        return self.get_case(case_id)

    def set_meta(
        self,
        case_id: str,
        *,
        source: str | None = None,
        priority: str | None = None,
        dedup_key: str | None = None,
    ) -> dict[str, Any]:
        from sqlalchemy import select, update

        from platform_api import store

        values = {
            k: v
            for k, v in (("source", source), ("priority", priority), ("dedup_key", dedup_key))
            if v is not None
        }
        with store.connect() as conn:
            if (
                conn.execute(
                    select(store.cases.c.case_id).where(store.cases.c.case_id == case_id)
                ).first()
                is None
            ):
                raise KeyError(case_id)
            if values:
                conn.execute(
                    update(store.cases).where(store.cases.c.case_id == case_id).values(**values)
                )
        return self.get_case(case_id)

    def find_open_by_dedup_key(self, dedup_key: str) -> dict[str, Any] | None:
        from sqlalchemy import select

        from platform_api import store

        with store.connect() as conn:
            row = (
                conn.execute(
                    select(store.cases.c.case_id)
                    .where(store.cases.c.dedup_key == dedup_key)
                    .where(store.cases.c.status.notin_(["CLOSED", "RESOLVED"]))
                    .order_by(store.cases.c.created_at.desc())
                )
                .scalars()
                .first()
            )
        return self.get_case(row) if row else None

    def update_case(self, case_id: str, notes: str, status: str | None) -> dict[str, Any]:
        from sqlalchemy import select, update

        from platform_api import store

        with store.connect() as conn:
            if (
                conn.execute(
                    select(store.cases.c.case_id).where(store.cases.c.case_id == case_id)
                ).first()
                is None
            ):
                raise KeyError(case_id)
            if status:
                conn.execute(
                    update(store.cases)
                    .where(store.cases.c.case_id == case_id)
                    .values(status=status)
                )
            conn.execute(
                store.audit_events.insert().values(
                    case_id=case_id, event=notes + (f" (status -> {status})" if status else "")
                )
            )
        return self.get_case(case_id)

    def propose_action(
        self,
        case_id: str,
        action_type: str,
        params: dict[str, str],
        rationale: str,
        impact: list[dict[str, str]],
        reversible: bool,
    ) -> dict[str, Any]:
        from platform_api import store

        approval_id = f"ap_{uuid4().hex[:8]}"
        with store.connect() as conn:
            conn.execute(
                store.approvals.insert().values(
                    approval_id=approval_id,
                    case_id=case_id,
                    action_type=action_type,
                    params=params,
                    rationale=rationale,
                    impact=impact,
                    reversible=reversible,
                    status=PENDING,
                )
            )
            conn.execute(
                store.audit_events.insert().values(
                    case_id=case_id, event=f"proposed {action_type} -> {approval_id} (PENDING)"
                )
            )
        return self.get_approval(approval_id) or {}

    def get_approval(self, approval_id: str) -> dict[str, Any] | None:
        from sqlalchemy import select

        from platform_api import store

        with store.connect() as conn:
            row = (
                conn.execute(
                    select(store.approvals).where(store.approvals.c.approval_id == approval_id)
                )
                .mappings()
                .first()
            )
        return dict(row) if row else None

    def decide(self, approval_id: str, decision: str, by: str, role: str) -> dict[str, Any]:
        from sqlalchemy import select, update

        from platform_api import store

        decision = decision.upper()
        if decision not in (APPROVED, REJECTED):
            raise ValueError(f"decision must be {APPROVED} or {REJECTED}, got {decision!r}")
        with store.connect() as conn:
            approval = (
                conn.execute(
                    select(store.approvals).where(store.approvals.c.approval_id == approval_id)
                )
                .mappings()
                .first()
            )
            if approval is None:
                raise KeyError(approval_id)
            conn.execute(
                update(store.approvals)
                .where(store.approvals.c.approval_id == approval_id)
                .values(status=decision, decided_by=by, role=role, decided_at=datetime.now(UTC))
            )
            conn.execute(
                store.audit_events.insert().values(
                    case_id=approval["case_id"],
                    event=f"{approval['action_type']} {approval_id} {decision} by {by} ({role})",
                )
            )
        return self.get_approval(approval_id) or {}

    def log_audit(self, case_id: str, event: str) -> None:
        from platform_api import store

        with store.connect() as conn:
            conn.execute(store.audit_events.insert().values(case_id=case_id, event=event))

    def list_cases(self) -> list[dict[str, Any]]:
        from sqlalchemy import select

        from platform_api import store

        with store.connect() as conn:
            rows = (
                conn.execute(select(store.cases).order_by(store.cases.c.created_at.desc()))
                .mappings()
                .all()
            )
        return [dict(r) for r in rows]

    def get_case(self, case_id: str) -> dict[str, Any]:
        from sqlalchemy import select

        from platform_api import store

        with store.connect() as conn:
            case = (
                conn.execute(select(store.cases).where(store.cases.c.case_id == case_id))
                .mappings()
                .first()
            )
            if case is None:
                raise KeyError(case_id)
            approvals = (
                conn.execute(
                    select(store.approvals)
                    .where(store.approvals.c.case_id == case_id)
                    .order_by(store.approvals.c.created_at)
                )
                .mappings()
                .all()
            )
            events = (
                conn.execute(
                    select(store.audit_events)
                    .where(store.audit_events.c.case_id == case_id)
                    .order_by(store.audit_events.c.at)
                )
                .mappings()
                .all()
            )
        return {
            **dict(case),
            "approvals": [dict(a) for a in approvals],
            "audit": [dict(e) for e in events],
        }


# --- facade ---------------------------------------------------------------------

_backend: Backend | None = None


def backend() -> Backend:
    global _backend
    if _backend is None:
        _backend = MemBackend() if os.environ.get("CASES_INMEMORY") == "1" else SqlBackend()
    return _backend


def set_backend(b: Backend | None) -> None:
    """Tests: install MemBackend, or reset with None."""
    global _backend
    _backend = b


def create_case(
    subject_type: str,
    subject_id: str,
    summary: str,
    trace_id: str = "",
    *,
    source: str = "user",
    priority: str = "NORMAL",
    dedup_key: str | None = None,
) -> dict[str, Any]:
    return backend().create_case(
        subject_type,
        subject_id,
        summary,
        trace_id,
        source=source,
        priority=priority,
        dedup_key=dedup_key,
    )


def update_case(case_id: str, notes: str, status: str | None = None) -> dict[str, Any]:
    return backend().update_case(case_id, notes, status)


def set_meta(
    case_id: str,
    *,
    source: str | None = None,
    priority: str | None = None,
    dedup_key: str | None = None,
) -> dict[str, Any]:
    return backend().set_meta(case_id, source=source, priority=priority, dedup_key=dedup_key)


def find_open_by_dedup_key(dedup_key: str) -> dict[str, Any] | None:
    return backend().find_open_by_dedup_key(dedup_key)


def propose_action(
    case_id: str,
    action_type: str,
    params: dict[str, str],
    rationale: str,
    impact: list[dict[str, str]],
    reversible: bool = True,
) -> dict[str, Any]:
    return backend().propose_action(case_id, action_type, params, rationale, impact, reversible)


def get_approval(approval_id: str) -> dict[str, Any] | None:
    return backend().get_approval(approval_id)


def decide(approval_id: str, decision: str, decided_by: str, role: str) -> dict[str, Any]:
    return backend().decide(approval_id, decision, decided_by, role)


def log_audit(case_id: str, event: str) -> None:
    backend().log_audit(case_id, event)


def list_cases() -> list[dict[str, Any]]:
    return backend().list_cases()


def get_case(case_id: str) -> dict[str, Any]:
    return backend().get_case(case_id)
