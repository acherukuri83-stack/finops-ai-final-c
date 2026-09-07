"""Retrieval quality against the real pgvector index.

Marked `contract`: CI ingests the corpus (`python -m knowledge.ingest --fixtures
CN-2026-081`) into the job's Postgres before running `-m contract`. Locally: `make ingest`
with the stack up.
"""

from __future__ import annotations

import pytest

from knowledge import retrieval

pytestmark = pytest.mark.contract


def _sections(results: list[dict[str, object]]) -> list[str]:
    return [f"{r['doc']} §{r['section']}" if r["section"] else str(r["doc"]) for r in results]


def test_ssi_mismatch_query_puts_handbook_8_4_in_the_top_3() -> None:
    top = _sections(retrieval.search_knowledge("counterparty SSI mismatch settlement failure", k=3))
    assert "Settlement Handbook §8.4" in top


def test_reference_data_query_finds_the_reference_procedure() -> None:
    top = _sections(
        retrieval.search_knowledge("security identifier CUSIP does not match master", k=3)
    )
    assert "Reference Data Procedure §3.2" in top


def test_restriction_query_finds_2_1() -> None:
    top = _sections(
        retrieval.search_knowledge("account settlement hold compliance restriction", k=3)
    )
    assert "Client Account Restrictions §2.1" in top


def test_incident_search_returns_the_matching_incident() -> None:
    hits = retrieval.find_incidents(
        "counterparty affirmed against a superseded DTC participant", k=3
    )
    assert hits and hits[0]["incident_id"] == "INC-1001"
    assert 0.0 <= hits[0]["similarity"] <= 1.0


def test_custodian_notice_fixture_is_retrievable_when_ingested() -> None:
    docs = [
        r["doc"] for r in retrieval.search_knowledge("custodian moved account to DTC 1234", k=5)
    ]
    assert "Custodian Notice CN-2026-081" in docs


def test_real_section_outranks_the_distractor() -> None:
    ranked = _sections(
        retrieval.search_knowledge("counterparty SSI mismatch settlement failure", k=8)
    )
    assert ranked[0] == "Settlement Handbook §8.4"
    if "SSI Policy §3.2" in ranked:  # the change-control distractor, if it surfaces at all
        assert ranked.index("SSI Policy §3.2") > ranked.index("Settlement Handbook §8.4")
