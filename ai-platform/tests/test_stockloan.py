"""Phase F core slice — the StockLoan specialist.

FakeModelClient + the in-process `stockloan` fixture store + the fake enterprise. Covers:
`investigate_loan` reproduces a `RECALL_REQUIRED` Finding proposing `initiate_recall`;
the recall-vs-buy-in decision is a hard rule in code (a missed notice window converts
`initiate_recall` → `book_buy_in`); the specialist's allowlist; the write tools honour the
approval gate.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest

from agent_core import policy
from agent_core.agents import STOCKLOAN, spec_for
from agent_core.reasoning.model_client import FakeModelClient, ModelResponse
from agent_core.schemas.finding import Outcome
from agent_core.stockloan import investigate_loan
from mcp_servers._fake_enterprise import FakeEnterpriseClient
from mcp_servers.stockloan import store as sl_store
from mcp_servers.stockloan.tools import initiate_recall
from platform_api import cases


@pytest.fixture(autouse=True)
def _reset_stockloan() -> Iterator[None]:
    sl_store.reset()
    yield
    sl_store.reset()


def _plan(*steps: tuple[str, str, dict[str, str]]) -> str:
    return json.dumps(
        {
            "assumptions": [],
            "steps": [{"server": s, "tool": t, "args": a, "why": "x"} for s, t, a in steps],
        }
    )


def _loan_finding(*, loan_id: str, root_cause: str, action: str, qty: str = "30000") -> str:
    return json.dumps(
        {
            "subject": {"type": "loan", "id": loan_id},
            "outcome": "RESOLVED_CAUSE",
            "root_cause": root_cause,
            "evidence": [
                {"kind": "tool", "ref": "get_loan", "cited": True},
                {"kind": "tool", "ref": "get_lending_availability", "cited": True},
            ],
            "proposed_actions": [
                {
                    "action_type": action,
                    "params": {"loan_id": loan_id, "qty": qty, "reason": "account short to settle"},
                    "rationale": "the shares are out on this loan",
                    "impact": [],
                }
            ],
            "rejected_alternatives": [
                {"action_type": "book_buy_in", "reason": "recall should still work", "evidence": []}
            ],
            "confidence_basis": "the loan, the shortfall, and the GC rate",
        }
    )


_PLAN_STEPS = _plan(
    ("stockloan", "get_loan", {"loan_id": "LN-5001"}),
    ("stockloan", "get_recall", {"loan_id": "LN-5001"}),
    ("stockloan", "get_lending_availability", {"security_id": "NVDA"}),
)


def test_stockloan_spec_and_allowlist() -> None:
    assert STOCKLOAN.allowlist_key == "stockloan"
    assert {"stockloan", "market"} <= STOCKLOAN.tool_servers
    assert STOCKLOAN.subject_type == "loan"
    assert spec_for("stockloan") is STOCKLOAN
    assert policy.allowed("stockloan", "initiate_recall") is True
    assert policy.allowed("stockloan", "book_buy_in") is True
    assert policy.allowed("stockloan", "update_ssi") is False
    assert policy.allowed("stockloan", "resubmit_settlement") is False


async def test_recall_still_open_reproduces_a_recall_finding(
    fake_enterprise: FakeEnterpriseClient,
) -> None:
    fake = FakeModelClient(
        [
            ModelResponse(text=_PLAN_STEPS),
            ModelResponse(text=_plan()),
            ModelResponse(
                text=_loan_finding(
                    loan_id="LN-5001", root_cause="RECALL_REQUIRED", action="initiate_recall"
                )
            ),
        ]
    )
    finding = await investigate_loan(
        "LN-5001", request="does HF101 need these NVDA back?", client=fake
    )

    assert finding.outcome is Outcome.RESOLVED_CAUSE
    assert finding.root_cause == "RECALL_REQUIRED"
    assert [a.action_type for a in finding.proposed_actions] == ["initiate_recall"]
    assert finding.proposed_actions[0].proposed_by == "stockloan"
    assert finding.case_id


async def test_missed_recall_window_converts_to_buy_in_in_code(
    fake_enterprise: FakeEnterpriseClient,
) -> None:
    # synthesis proposes initiate_recall for LN-5002, whose notice window has passed.
    fake = FakeModelClient(
        [
            ModelResponse(text=_plan(("stockloan", "get_loan", {"loan_id": "LN-5002"}))),
            ModelResponse(text=_plan()),
            ModelResponse(
                text=_loan_finding(
                    loan_id="LN-5002",
                    root_cause="RECALL_REQUIRED",
                    action="initiate_recall",
                    qty="12000",
                )
            ),
        ]
    )
    finding = await investigate_loan("LN-5002", request="recall?", client=fake)

    assert [a.action_type for a in finding.proposed_actions] == ["book_buy_in"]
    assert finding.root_cause == "RECALL_WINDOW_MISSED"
    assert any("book_buy_in in code" in q for q in finding.open_questions)


async def test_recall_write_refuses_a_forged_approval(
    fake_enterprise: FakeEnterpriseClient,
) -> None:
    result = await initiate_recall("LN-5001", "30000", "x", approval_id="ap_forged9")
    assert result["code"] == "ApprovalError"
    assert sl_store.actions() == []


async def test_approved_recall_records_and_audits(fake_enterprise: FakeEnterpriseClient) -> None:
    case = cases.create_case("loan", "LN-5001", "recall")
    approval = cases.propose_action(
        case["case_id"],
        "initiate_recall",
        {"loan_id": "LN-5001", "qty": "30000"},
        "account short to settle",
        [{"type": "loan", "id": "LN-5001"}],
        True,
    )
    cases.decide(approval["approval_id"], "APPROVED", "s.desk", "OPS_ANALYST")

    row = await initiate_recall(
        "LN-5001", "30000", "cover the delivery", approval_id=approval["approval_id"]
    )

    assert row["kind"] == "recall" and row["loan_id"] == "LN-5001"
    assert len(sl_store.actions()) == 1
    audit = cases.get_case(case["case_id"])["audit"]
    assert any("initiated recall" in e["event"] for e in audit)
