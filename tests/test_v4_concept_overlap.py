"""Tests for V4 cognitive retrieval concept overlap.

Focused regression coverage: concept labels are canonicalized and overlap is non-zero
when query and memory refer to the same concept with different surface forms.
"""

from src.core.retrieval import CognitiveRetriever
from src.utils.curation import canonicalize_concepts


def test_concept_overlap_nonzero_after_canonicalization() -> None:
    retriever = CognitiveRetriever()

    query_concepts = canonicalize_concepts(["Kiro", "R>D>T", "Vector DB"])
    memory_concepts = canonicalize_concepts(["kiro", "r > d > t", "vector db"])

    overlap = retriever.compute_concept_overlap(query_concepts, memory_concepts)

    assert overlap > 0.0
