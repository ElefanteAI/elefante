"""
V5 Property Tests: Retrieval Explanation (Req-1)

Tests Properties 1 and 2 from design.md
"""

import pytest
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings

from src.core.retrieval import (
    CognitiveRetriever,
    MemoryCandidate,
    QueryAnalysis,
    RetrievalExplanation,
)


# =============================================================================
# STRATEGIES (generators for hypothesis)
# =============================================================================

@st.composite
def memory_candidates(draw):
    """Generate random MemoryCandidate objects."""
    concepts = draw(st.lists(
        st.sampled_from(['elefante', 'config', 'paths', 'python', 'api', 'database', 'test', 'memory', 'search', 'query']),
        min_size=0, max_size=5, unique=True
    ))
    
    return MemoryCandidate(
        id=draw(st.uuids()).hex,
        content=draw(st.text(min_size=10, max_size=200)),
        title=draw(st.text(min_size=5, max_size=50)),
        summary=draw(st.text(min_size=5, max_size=100)),
        concepts=concepts,
        domain=draw(st.sampled_from(['project:elefante', 'work', 'personal', 'general'])),
        importance=draw(st.integers(min_value=1, max_value=10)),
        access_count=draw(st.integers(min_value=0, max_value=100)),
        created_at=datetime.utcnow() - timedelta(days=draw(st.integers(min_value=0, max_value=365))),
        last_accessed=datetime.utcnow() - timedelta(days=draw(st.integers(min_value=0, max_value=90))),
        vector_score=draw(st.floats(min_value=0.0, max_value=1.0)),
    )


@st.composite
def query_analyses(draw):
    """Generate random QueryAnalysis objects."""
    concepts = draw(st.lists(
        st.sampled_from(['elefante', 'config', 'paths', 'python', 'api', 'database', 'test', 'memory', 'search', 'query']),
        min_size=0, max_size=5, unique=True
    ))
    
    return QueryAnalysis(
        raw_query=draw(st.text(min_size=5, max_size=100)),
        concepts=concepts,
        inferred_domain=draw(st.sampled_from([None, 'project:elefante', 'work', 'personal'])),
        inferred_intent=draw(st.sampled_from([None, 'troubleshoot', 'learn', 'decide', 'remember'])),
    )


# =============================================================================
# PROPERTY 1: Explanation Completeness
# =============================================================================

class TestProperty1ExplanationCompleteness:
    """
    Property 1: For any search result with a composite score, the explanation 
    SHALL contain exactly 6 signal entries and the sum of weighted_scores 
    SHALL equal composite_score ± 0.001.
    
    Validates: Req-1.1, Req-1.6
    """
    
    @given(candidate=memory_candidates(), query=query_analyses())
    @settings(max_examples=100)
    def test_explanation_has_exactly_6_signals(self, candidate, query):
        """Every explanation must have exactly 6 signals."""
        retriever = CognitiveRetriever()
        scored, explanation = retriever.score_candidate(candidate, query, [])
        
        assert explanation is not None, "Explanation should not be None"
        assert len(explanation.signals) == 6, f"Expected 6 signals, got {len(explanation.signals)}"
    
    @given(candidate=memory_candidates(), query=query_analyses())
    @settings(max_examples=100)
    def test_weighted_scores_sum_to_composite(self, candidate, query):
        """Sum of weighted scores must equal composite score."""
        retriever = CognitiveRetriever()
        scored, explanation = retriever.score_candidate(candidate, query, [])
        
        weighted_sum = sum(sig["weighted"] for sig in explanation.signals)
        
        assert abs(weighted_sum - explanation.composite_score) < 0.001, \
            f"Weighted sum {weighted_sum:.4f} != composite {explanation.composite_score:.4f}"
    
    @given(candidate=memory_candidates(), query=query_analyses())
    @settings(max_examples=100)
    def test_all_required_signal_names_present(self, candidate, query):
        """All 6 signal names must be present."""
        retriever = CognitiveRetriever()
        scored, explanation = retriever.score_candidate(candidate, query, [])
        
        expected_names = {
            "vector_similarity", "concept_overlap", "domain_match",
            "coactivation", "authority", "temporal"
        }
        actual_names = {sig["name"] for sig in explanation.signals}
        
        assert actual_names == expected_names, \
            f"Missing signals: {expected_names - actual_names}"
    
    @given(candidate=memory_candidates(), query=query_analyses())
    @settings(max_examples=100)
    def test_each_signal_has_required_fields(self, candidate, query):
        """Each signal must have name, score, weight, weighted, reason, details."""
        retriever = CognitiveRetriever()
        scored, explanation = retriever.score_candidate(candidate, query, [])
        
        required_fields = {"name", "score", "weight", "weighted", "reason", "details"}
        
        for sig in explanation.signals:
            actual_fields = set(sig.keys())
            missing = required_fields - actual_fields
            assert not missing, f"Signal {sig.get('name', '?')} missing fields: {missing}"


# =============================================================================
# PROPERTY 2: Explanation Accuracy
# =============================================================================

class TestProperty2ExplanationAccuracy:
    """
    Property 2: For any search result where concept_score > 0, the explanation 
    details SHALL list at least one matching concept that exists in both query 
    and memory.
    
    Validates: Req-1.2
    """
    
    @given(candidate=memory_candidates(), query=query_analyses())
    @settings(max_examples=100)
    def test_concept_overlap_lists_matched_concepts(self, candidate, query):
        """If concept_score > 0, matched concepts must be listed."""
        retriever = CognitiveRetriever()
        scored, explanation = retriever.score_candidate(candidate, query, [])
        
        # Find concept_overlap signal
        concept_signal = next(
            (sig for sig in explanation.signals if sig["name"] == "concept_overlap"),
            None
        )
        
        assert concept_signal is not None, "concept_overlap signal not found"
        
        if concept_signal["score"] > 0:
            matched = concept_signal["details"].get("matched", [])
            assert len(matched) > 0, \
                f"concept_score={concept_signal['score']:.3f} but no matched concepts listed"
            
            # Verify matched concepts actually exist in both
            query_set = set(query.concepts)
            memory_set = set(candidate.concepts)
            
            for concept in matched:
                assert concept in query_set, f"Matched concept '{concept}' not in query"
                assert concept in memory_set, f"Matched concept '{concept}' not in memory"
    
    def test_specific_concept_match(self):
        """Verify specific known overlap is reported correctly."""
        retriever = CognitiveRetriever()
        
        candidate = MemoryCandidate(
            id="test-1",
            content="Test",
            title="Test",
            summary="Test",
            concepts=["elefante", "config", "paths"],
            domain="project:elefante",
            importance=5,
            access_count=1,
            created_at=datetime.utcnow(),
            last_accessed=datetime.utcnow(),
            vector_score=0.5,
        )
        
        query = QueryAnalysis(
            raw_query="configure elefante",
            concepts=["elefante", "configure"],
            inferred_domain="project:elefante",
        )
        
        scored, explanation = retriever.score_candidate(candidate, query, [])
        
        concept_signal = next(
            sig for sig in explanation.signals if sig["name"] == "concept_overlap"
        )
        
        matched = concept_signal["details"]["matched"]
        assert "elefante" in matched, "Expected 'elefante' in matched concepts"


# =============================================================================
# BONUS: to_dict() serialization test
# =============================================================================

class TestExplanationSerialization:
    """Test that explanation serializes correctly for MCP response."""
    
    def test_to_dict_produces_valid_structure(self):
        """to_dict() must produce JSON-serializable structure."""
        retriever = CognitiveRetriever()
        
        candidate = MemoryCandidate(
            id="test-1",
            content="Test content",
            title="Test Title",
            summary="Test summary",
            concepts=["test"],
            domain="general",
            importance=5,
            access_count=1,
            created_at=datetime.utcnow(),
            last_accessed=datetime.utcnow(),
            vector_score=0.75,
        )
        
        query = QueryAnalysis(raw_query="test query", concepts=["test"])
        scored, explanation = retriever.score_candidate(candidate, query, [])
        
        result = explanation.to_dict()
        
        assert "composite_score" in result
        assert "signals" in result
        assert isinstance(result["composite_score"], float)
        assert isinstance(result["signals"], list)
        assert len(result["signals"]) == 6
        
        # Verify it's JSON-serializable
        import json
        json_str = json.dumps(result)
        assert len(json_str) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
