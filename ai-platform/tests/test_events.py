"""Phase D — event-driven investigations.

`FakeBus` (in-memory) + `FakeModelClient` + the in-process fake enterprise. Covers:
publish → drain → one event-sourced case; a repeat event dedups onto that case with no
second investigation; a near deadline marks the case HIGH; `run_poller` drains and stops
cleanly.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from agent_core.reasoning.model_client import FakeModelClient, ModelResponse
from mcp_servers._fake_enterprise import FakeEnterpriseClient
from platform_api import cases
from platform_api.events import Event, drain_once, run_poller


def _plan(*steps: tuple[str, str, dict[str, str]]) -> str:
    return json.dumps(
        {
            "assumptions": [],
            "steps": [{"server": s, "tool": t, "args": a, "why": "x"} for s, t, a in steps],
        }
    )


_FINDING = json.dumps(
    {
        "subject": {"type": "trade", "id": "T100245"},
        "outcome": "RESOLVED_CAUSE",
        "root_cause": "COUNTERPARTY_INSTRUCTION_STALE",
        "evidence": [{"kind": "tool", "ref": "get_ssi_history", "cited": True}],
        "proposed_actions": [
            {"action_type": "resubmit_settlement", "rationale": "cpty re-affirms", "impact": []}
        ],
        "rejected_alternatives": [
            {"action_type": "update_ssi", "reason": "our SSI is current", "evidence": []}
        ],
        "confidence_basis": "SSI history plus the affirmation",
    }
)

_NO_ACTION_FINDING = json.dumps(
    {
        "subject": {"type": "trade", "id": "T100245"},
        "outcome": "INSUFFICIENT_EVIDENCE",
        "evidence": [],
        "proposed_actions": [],
        "rejected_alternatives": [],
        "confidence_basis": "nothing conclusive",
    }
)


def _one_investigation() -> list[ModelResponse]:
    return [
        ModelResponse(
            text=_plan(
                ("trade", "get_trade", {"trade_id": "T100245"}),
                ("trade", "get_settlement_status", {"trade_id": "T100245"}),
            )
        ),
        ModelResponse(text=_plan()),
        ModelResponse(text=_FINDING),
    ]


class FakeBus:
    def __init__(self) -> None:
        self._rows: list[dict[str, Any]] = []
        self._n = 0

    async def publish(self, event: Event) -> str:
        self._n += 1
        eid = str(self._n)
        self._rows.append(
            {"id": eid, "event": event.model_copy(update={"id": eid}), "acked": False}
        )
        return eid

    async def poll(self, limit: int) -> list[Event]:
        return [r["event"] for r in self._rows if not r["acked"]][:limit]

    async def ack(self, event_ids: list[str]) -> None:
        for r in self._rows:
            if r["id"] in event_ids:
                r["acked"] = True

    async def close(self) -> None:
        return None

    def pending(self) -> list[str]:
        return [r["id"] for r in self._rows if not r["acked"]]


def _event(**payload: Any) -> Event:
    return Event(type="FAILED", subject_id="T100245", payload=payload)


# --- tests -------------------------------------------------------------------


async def test_event_opens_one_case_with_source_event(
    fake_enterprise: FakeEnterpriseClient,
) -> None:
    bus = FakeBus()
    await bus.publish(_event(failure_code="COUNTERPARTY_SSI_MISMATCH"))
    fake = FakeModelClient(_one_investigation())

    handled = await drain_once(bus, client=fake)

    assert handled == 1
    assert bus.pending() == []  # acked
    rows = cases.list_cases()
    assert len(rows) == 1
    assert rows[0]["source"] == "event"
    assert rows[0]["priority"] == "NORMAL"
    assert rows[0]["dedup_key"] == "T100245:COUNTERPARTY_SSI_MISMATCH"
    audit = cases.get_case(rows[0]["case_id"])["audit"]
    assert any("opened from a FAILED event" in e["event"] for e in audit)


async def test_duplicate_event_folds_into_one_case(fake_enterprise: FakeEnterpriseClient) -> None:
    bus = FakeBus()
    await bus.publish(_event(failure_code="COUNTERPARTY_SSI_MISMATCH"))
    await bus.publish(_event(failure_code="COUNTERPARTY_SSI_MISMATCH"))  # same dedup key
    fake = FakeModelClient(_one_investigation())  # only ONE investigation queued

    await drain_once(bus, client=fake)

    assert len(cases.list_cases()) == 1
    assert len(fake.calls) == 3  # the second event did not start an investigation
    audit = cases.get_case(cases.list_cases()[0]["case_id"])["audit"]
    assert any("repeat FAILED event" in e["event"] for e in audit)


async def test_near_deadline_marks_case_high(fake_enterprise: FakeEnterpriseClient) -> None:
    soon = (datetime.now(UTC) + timedelta(minutes=20)).isoformat()
    bus = FakeBus()
    await bus.publish(_event(failure_code="COUNTERPARTY_SSI_MISMATCH", deadline=soon))
    fake = FakeModelClient(_one_investigation())

    await drain_once(bus, client=fake)

    case = cases.list_cases()[0]
    assert case["priority"] == "HIGH"
    audit = cases.get_case(case["case_id"])["audit"]
    assert any("prioritised HIGH" in e["event"] for e in audit)


async def test_no_action_finding_still_opens_a_tracking_case(
    fake_enterprise: FakeEnterpriseClient,
) -> None:
    bus = FakeBus()
    await bus.publish(_event(failure_code="UNKNOWN"))
    fake = FakeModelClient([ModelResponse(text=_plan()), ModelResponse(text=_NO_ACTION_FINDING)])

    await drain_once(bus, client=fake)

    rows = cases.list_cases()
    assert len(rows) == 1
    assert rows[0]["source"] == "event"
    assert rows[0]["dedup_key"] == "T100245:UNKNOWN"
    assert cases.get_case(rows[0]["case_id"])["approvals"] == []


async def test_run_poller_drains_then_stops(fake_enterprise: FakeEnterpriseClient) -> None:
    bus = FakeBus()
    await bus.publish(_event(failure_code="COUNTERPARTY_SSI_MISMATCH"))
    fake = FakeModelClient(_one_investigation())
    stop = asyncio.Event()

    task = asyncio.create_task(run_poller(bus, interval=0.05, stop=stop, client=fake))
    await asyncio.sleep(0.25)
    stop.set()
    await asyncio.wait_for(task, timeout=2)

    assert len(cases.list_cases()) == 1
    assert bus.pending() == []
