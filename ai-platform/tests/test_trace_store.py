"""Unit tests for the trace store's pure logic and its best-effort guarantees.
The real Postgres round-trip is exercised by the `-m contract` suite.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from platform_api import store, trace_store
from platform_api.settings import settings


def test_scrub_redacts_emails_ids_and_person_keys_and_counts() -> None:
    obj = {
        "account": "ACC-88213",  # domain id — kept
        "updated_by": "ops.jsmith",  # person key — redacted
        "note": "raise with a.patel@example.com about SSN 123456789",
        "nested": [{"decided_by": "r.lee", "n": 42}],
    }
    scrubbed, n = trace_store.scrub(obj)
    assert n == 4  # updated_by, email, 9-digit run, decided_by
    assert scrubbed["account"] == "ACC-88213"
    assert scrubbed["updated_by"] == "[redacted]"
    assert "@example.com" not in scrubbed["note"] and "[redacted:email]" in scrubbed["note"]
    assert "123456789" not in scrubbed["note"]
    assert scrubbed["nested"][0] == {"decided_by": "[redacted]", "n": 42}
    # idempotent: a second pass finds nothing
    assert trace_store.scrub(scrubbed)[1] == 0


def test_redact_returns_the_scrubbed_copy() -> None:
    obj = {"contact": "d.patel", "clean": "no pii"}
    out = trace_store.redact(obj)
    assert out == {"contact": "[redacted]", "clean": "no pii"}
    assert obj["contact"] == "d.patel"  # original untouched


def test_cost_uses_the_model_price_table() -> None:
    assert trace_store._cost("claude-haiku-4-5", 1_000_000, 0) == pytest.approx(0.80)
    assert trace_store._cost("claude-sonnet-4-6", 0, 1_000_000) == pytest.approx(15.00)
    assert trace_store._cost("something-unknown", 1_000_000, 0) == pytest.approx(
        3.00
    )  # sonnet default


def test_maybe_json_parses_strings_and_passes_through_the_rest() -> None:
    assert trace_store._maybe_json('{"a": 1}') == {"a": 1}
    assert trace_store._maybe_json("not json") == "not json"
    assert trace_store._maybe_json({"already": "obj"}) == {"already": "obj"}
    assert trace_store._maybe_json(None) is None


def _fake_span() -> Any:
    ctx = SimpleNamespace(trace_id=1, span_id=2)
    return SimpleNamespace(
        context=ctx,
        parent=None,
        name="investigate",
        attributes={"finops.span.type": "agent"},
        start_time=1_000_000_000,
        end_time=2_000_000_000,
        status=SimpleNamespace(status_code=SimpleNamespace(name="OK")),
    )


def test_record_span_is_a_noop_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "traces_enabled", False)

    def _boom(*_a: object, **_k: object) -> None:
        raise AssertionError("store.connect must not be called when tracing is disabled")

    monkeypatch.setattr(store, "connect", _boom)
    trace_store.record_span(_fake_span())  # no raise


def test_writes_swallow_db_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "traces_enabled", True)

    def _raise(*_a: object, **_k: object) -> None:
        raise RuntimeError("no database here")

    monkeypatch.setattr(store, "connect", _raise)
    trace_store.record_span(_fake_span())  # logged, not raised
    trace_store.finalize_trace(
        "t1",
        request="r",
        subject_type="trade",
        subject_id="T1",
        scenario_id=None,
        case_id="",
        agent="investigator",
        outcome="RESOLVED_CAUSE",
        root_cause="X",
        status="COMPLETE",
        finding=None,
    )
    trace_store.record_approval_span(
        "t1", approval_id="ap_1", status="APPROVED", by="a.patel", role="OPS_ANALYST", elapsed_ms=10
    )
