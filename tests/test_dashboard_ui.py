"""Regression checks for the dashboard retrieval-evidence presentation."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI_SRC = ROOT / "src" / "dashboard" / "ui" / "src"


def _read(relative_path: str) -> str:
    return (UI_SRC / relative_path).read_text(encoding="utf-8")


def test_retrieval_explanation_uses_only_dashboard_search_evidence() -> None:
    explanation = _read("components/RetrievalExplanation.tsx")

    assert "result.similarity" in explanation
    assert "metadata.source" in explanation
    assert "metadata.health_status" in explanation
    assert "metadata.health_reason" in explanation
    assert "metadata.connection_count" in explanation
    assert "edgeEndpoints(edge)" in explanation
    assert "Snapshot search ratio" in explanation
    assert "The dashboard API does not expose the MCP retriever" in explanation
    assert "result.vector_score" not in explanation
    assert "result.concept_score" not in explanation


def test_search_selection_wires_rank_and_snapshot_relationships_to_detail_panel() -> None:
    memories = _read("components/MemoriesTab.tsx")
    detail_panel = _read("components/MemoryDetailPanel.tsx")

    assert "selectedSearchResultIndex" in memories
    assert "rank: selectedSearchResultIndex + 1" in memories
    assert "total: results.length" in memories
    assert "edges: snapshot?.edges || []" in memories
    assert "retrievalEvidence={selectedSearchResult ?" in memories
    assert "retrievalEvidence?: RetrievalEvidence" in detail_panel
    assert "<RetrievalExplanation memory={memory} evidence={retrievalEvidence}" in detail_panel


def test_search_rows_keep_snapshot_vitality_separate_from_lexical_match() -> None:
    memories = _read("components/MemoriesTab.tsx")

    assert "score: Number.isFinite(Number(r.metadata?.score))" in memories
    assert "score: r.similarity" not in memories
