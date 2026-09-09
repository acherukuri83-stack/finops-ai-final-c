"""Corpus chunking: section split, metadata, and no interpretive language in fixtures."""

from __future__ import annotations

from knowledge.chunking import chunk_file
from knowledge.ingest import CORPUS, gather

# same list the simulator's leak test uses (simulator/simulator/scenario.py LEAK_WORDS)
_LEAK_WORDS = ("stale", "wrong side", "never picked up", "root cause", "because", "should have")


def test_handbook_splits_into_numbered_sections() -> None:
    chunks = chunk_file(CORPUS / "settlement-handbook.md")
    by_section = {c.section: c for c in chunks}
    assert set(by_section) == {"8.1", "8.4", "8.6"}
    s84 = by_section["8.4"]
    assert s84.doc == "Settlement Handbook"
    assert s84.title == "Counterparty SSI mismatch"
    assert s84.kind == "sop"
    assert "re-affirmation" in s84.text
    assert s84.id == "Settlement Handbook §8.4"


def test_incident_is_one_chunk_with_fields() -> None:
    (inc,) = chunk_file(CORPUS / "incidents" / "INC-1001.md")
    assert inc.kind == "incident"
    assert inc.incident_id == "INC-1001"
    assert inc.summary and inc.root_cause and inc.resolution


def test_full_corpus_gathers_sops_incidents_and_the_named_fixture() -> None:
    without = {c.id for c in gather(set())}
    with_fixture = {c.id for c in gather({"CN-2026-081"})}
    assert "Custodian Notice CN-2026-081" not in without
    assert "Custodian Notice CN-2026-081" in with_fixture
    incidents = {c.id for c in gather(set()) if c.kind == "incident"}
    assert {f"INC-100{n}" for n in range(1, 9)} <= incidents  # Phase A settlement incidents
    assert {f"INC-200{n}" for n in range(1, 6)} <= incidents  # Phase B wire incidents


def test_wire_corpus_sections() -> None:
    guide = {c.section: c for c in chunk_file(CORPUS / "wire-processing-guide.md")}
    assert {"5.2", "9.1", "7.4"} <= set(guide)
    assert guide["5.2"].id == "Wire Processing Guide §5.2"
    sanctions = {c.section for c in chunk_file(CORPUS / "sanctions-procedure.md")}
    assert {"2.1", "2.4"} <= sanctions


def test_fixture_text_is_factual_only() -> None:
    for path in (CORPUS / "fixtures").glob("*.md"):
        for (chunk,) in [chunk_file(path)]:
            low = chunk.text.lower()
            hits = [w for w in _LEAK_WORDS if w in low]
            assert not hits, f"{path.name}: interpretive language {hits}"
