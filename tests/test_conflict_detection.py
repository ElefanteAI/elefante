# ─────────────────────────────────────────────────────────────────────────────
# TEST    : tests/test_conflict_detection.py
# PROVES  : Pure, deterministic, high-confidence conflict assessment and its
#           non-repairing write-path boundary.
# RUN     : pytest tests/test_conflict_detection.py -v
# WHEN    : After changes to src/core/conflict_detection.py or its orchestrator
#           integration.
# ─────────────────────────────────────────────────────────────────────────────
"""Focused tests for conservative semantic conflict detection."""

import pytest

from src.core.conflict_detection import (
    ConflictAssessment,
    ConflictOutcome,
    assess_conflict,
)
from src.models.memory import MemoryStatus
from src.models.query import SearchResult


@pytest.mark.parametrize(
    ("incoming", "existing"),
    [
        (
            "The local daemon does not store memory decisions.",
            "The local daemon stores memory decisions.",
        ),
        ("The service is not healthy.", "The service is healthy."),
        ("The daemon cannot use SQLite.", "The daemon can use SQLite."),
        (
            "The product launch banner must not be blue.",
            "The product launch banner must be blue.",
        ),
        ("The daemon must not use SQLite.", "The daemon must use SQLite."),
    ],
)
def test_opposite_explicit_polarity_is_conflict(incoming, existing):
    assessment = assess_conflict(incoming, existing)

    assert assessment.outcome is ConflictOutcome.CONFLICT
    assert assessment.reason == "same normalized proposition with opposite explicit polarity"


@pytest.mark.parametrize(
    ("incoming", "existing"),
    [
        (
            "The default vector store is ChromaDB.",
            "The default vector store is SQLite.",
        ),
        (
            "The server listens on port 8000.",
            "The server listens on port 8765.",
        ),
        ("The feature is disabled.", "The feature is enabled."),
    ],
)
def test_competing_explicit_values_are_conflict(incoming, existing):
    assessment = assess_conflict(incoming, existing)

    assert assessment.outcome is ConflictOutcome.CONFLICT
    assert assessment.reason == "same explicit subject/predicate with incompatible explicit values"


def test_same_normalized_proposition_is_no_conflict():
    assessment = assess_conflict(
        "  The DEFAULT vector store is SQLite.  ",
        "the default vector store is sqlite",
    )

    assert assessment == ConflictAssessment(
        outcome=ConflictOutcome.NO_CONFLICT,
        reason="same normalized proposition with matching explicit polarity",
    )


@pytest.mark.parametrize(
    ("incoming", "existing"),
    [
        (
            "The service stores memory decisions.",
            "The service stores graph relationships.",
        ),
        ("The service supports SQLite.", "The service supports Kuzu."),
        ("The service is healthy.", "The service is fast."),
        (
            "The daemon does not store memory decisions.",
            "The website does not store memory decisions.",
        ),
        ("not healthy", "healthy"),
        ("The daemon and service share memory.", "The daemon stores memory."),
    ],
)
def test_ambiguous_shared_keyword_or_loose_negation_abstains(incoming, existing):
    assessment = assess_conflict(incoming, existing)

    assert assessment.outcome is ConflictOutcome.ABSTAIN
    assert assessment.reason


def test_assessment_is_deterministic_and_symmetric():
    incoming = "The default vector store is ChromaDB."
    existing = "The default vector store is SQLite."
    expected = assess_conflict(incoming, existing)

    assert set(ConflictOutcome) == {
        ConflictOutcome.CONFLICT,
        ConflictOutcome.NO_CONFLICT,
        ConflictOutcome.ABSTAIN,
    }
    for _ in range(10):
        assert assess_conflict(incoming, existing) == expected
    assert assess_conflict(existing, incoming) == expected


@pytest.mark.asyncio
async def test_write_path_marks_only_conflict_and_leaves_prior_memory_untouched(
    isolated_orchestrator, monkeypatch
):
    class FixedEmbedding:
        async def generate_embedding(self, _text):
            return [1.0, 0.0, 0.0]

    embedding = FixedEmbedding()
    isolated_orchestrator.embedding_service = embedding
    isolated_orchestrator.vector_store._embedding_service = embedding

    existing = await isolated_orchestrator.add_memory(
        content="The local daemon stores memory decisions.",
        memory_type="fact",
        metadata={"title": "Existing daemon storage"},
    )
    assert existing is not None
    prior_content = existing.content
    prior_status = existing.metadata.status
    prior_conflicts = list(existing.metadata.conflict_ids)

    async def no_title_match(_title):
        return None

    async def high_similarity_match(**_kwargs):
        return [
            SearchResult(
                memory=existing,
                score=0.80,
                vector_score=0.80,
                source="vector",
            )
        ]

    monkeypatch.setattr(
        isolated_orchestrator.vector_store,
        "find_by_title",
        no_title_match,
    )
    monkeypatch.setattr(
        isolated_orchestrator.vector_store,
        "search",
        high_similarity_match,
    )

    incoming = await isolated_orchestrator.add_memory(
        content="The local daemon does not store memory decisions.",
        memory_type="fact",
        metadata={"title": "Incoming daemon storage"},
    )

    assert incoming is not None
    assert incoming.metadata.status == MemoryStatus.CONTRADICTORY.value
    assert incoming.metadata.conflict_ids == [existing.id]

    prior = await isolated_orchestrator.vector_store.get_memory(existing.id)
    assert prior is not None
    assert prior.content == prior_content
    assert prior.metadata.status == prior_status
    assert prior.metadata.conflict_ids == prior_conflicts


@pytest.mark.asyncio
async def test_write_path_abstention_does_not_mark_ambiguous_match_contradictory(
    isolated_orchestrator, monkeypatch
):
    class FixedEmbedding:
        async def generate_embedding(self, _text):
            return [1.0, 0.0, 0.0]

    embedding = FixedEmbedding()
    isolated_orchestrator.embedding_service = embedding
    isolated_orchestrator.vector_store._embedding_service = embedding

    existing = await isolated_orchestrator.add_memory(
        content="The service stores memory decisions.",
        memory_type="fact",
        metadata={"title": "Existing service storage"},
    )
    assert existing is not None

    async def no_title_match(_title):
        return None

    async def high_similarity_match(**_kwargs):
        return [
            SearchResult(
                memory=existing,
                score=0.80,
                vector_score=0.80,
                source="vector",
            )
        ]

    monkeypatch.setattr(
        isolated_orchestrator.vector_store,
        "find_by_title",
        no_title_match,
    )
    monkeypatch.setattr(
        isolated_orchestrator.vector_store,
        "search",
        high_similarity_match,
    )

    incoming = await isolated_orchestrator.add_memory(
        content="The service stores graph relationships.",
        memory_type="fact",
        metadata={"title": "Incoming service storage"},
    )

    assert incoming is not None
    assert incoming.metadata.status == MemoryStatus.RELATED.value
    assert incoming.metadata.conflict_ids == []
