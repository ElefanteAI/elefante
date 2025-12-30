"""
V5 Property Tests: Proactive Surfacing (Req-4)

Properties:
- P7: Trigger types - exactly 3 types (temporal, domain, recurring_concept)
- P8: Confidence bounds - always 0.0-1.0
"""
import pytest
from hypothesis import given, strategies as st, settings, assume

from src.core.retrieval import ProactiveSuggestion, ProactiveSurfacer


# ============================================================================
# PROPERTY 7: Trigger Type Coverage
# ============================================================================

class TestP7TriggerTypes:
    """Proactive surfacing has exactly 3 trigger types."""
    
    def test_temporal_trigger(self):
        """Temporal trigger fires on surfaces_when match."""
        surfacer = ProactiveSurfacer()
        
        suggestion = surfacer.check_temporal_trigger(
            memory_id="mem-1",
            memory_title="Standup Notes",
            surfaces_when="at standup meetings",
            current_context="Let's start the daily standup"
        )
        
        assert suggestion is not None
        assert suggestion.trigger == "temporal"
        assert "standup" in suggestion.reason.lower()
    
    def test_temporal_no_match(self):
        """Temporal trigger doesn't fire when no match."""
        surfacer = ProactiveSurfacer()
        
        suggestion = surfacer.check_temporal_trigger(
            memory_id="mem-1",
            memory_title="Standup Notes",
            surfaces_when="at standup meetings",
            current_context="Working on the database migration"
        )
        
        assert suggestion is None
    
    def test_temporal_none_surfaces_when(self):
        """Temporal returns None if surfaces_when is None."""
        surfacer = ProactiveSurfacer()
        
        suggestion = surfacer.check_temporal_trigger(
            memory_id="mem-1",
            memory_title="Random Memory",
            surfaces_when=None,
            current_context="Anything"
        )
        
        assert suggestion is None
    
    def test_domain_trigger(self):
        """Domain trigger fires on exact domain match."""
        surfacer = ProactiveSurfacer()
        
        suggestion = surfacer.check_domain_trigger(
            memory_id="mem-2",
            memory_title="Work Meeting Notes",
            memory_domain="work",
            conversation_domain="work"
        )
        
        assert suggestion is not None
        assert suggestion.trigger == "domain"
        assert "work" in suggestion.reason.lower()
    
    def test_domain_no_match(self):
        """Domain trigger doesn't fire on different domains."""
        surfacer = ProactiveSurfacer()
        
        suggestion = surfacer.check_domain_trigger(
            memory_id="mem-2",
            memory_title="Personal Note",
            memory_domain="personal",
            conversation_domain="work"
        )
        
        assert suggestion is None
    
    def test_concept_trigger(self):
        """Concept trigger fires on sufficient overlap."""
        surfacer = ProactiveSurfacer()
        
        suggestion = surfacer.check_concept_trigger(
            memory_id="mem-3",
            memory_title="Python Tips",
            memory_concepts=["python", "testing", "pytest"],
            recent_concepts=["python", "testing", "debugging"],
            min_overlap=2
        )
        
        assert suggestion is not None
        assert suggestion.trigger == "recurring_concept"
        assert "python" in suggestion.reason.lower() or "testing" in suggestion.reason.lower()
    
    def test_concept_insufficient_overlap(self):
        """Concept trigger doesn't fire if overlap below threshold."""
        surfacer = ProactiveSurfacer()
        
        suggestion = surfacer.check_concept_trigger(
            memory_id="mem-3",
            memory_title="Python Tips",
            memory_concepts=["python", "testing"],
            recent_concepts=["python", "react", "typescript"],  # Only 1 overlap
            min_overlap=2
        )
        
        assert suggestion is None
    
    @given(
        has_surfaces_when=st.booleans(),
        domain_match=st.booleans(),
        concept_overlap=st.integers(0, 5),
    )
    @settings(max_examples=100)
    def test_trigger_type_always_valid(self, has_surfaces_when, domain_match, concept_overlap):
        """Any suggestion has a valid trigger type."""
        surfacer = ProactiveSurfacer()
        
        memories = [{
            "id": "m1",
            "title": "Test",
            "domain": "work",
            "concepts": ["a", "b", "c"][:concept_overlap],
            "surfaces_when": "at standup" if has_surfaces_when else None,
        }]
        
        suggestions = surfacer.get_proactive_surfaces(
            memories=memories,
            current_context="standup meeting" if has_surfaces_when else "random context",
            conversation_domain="work" if domain_match else "personal",
            recent_concepts=["a", "b", "d", "e"]
        )
        
        for s in suggestions:
            assert s.trigger in {"temporal", "domain", "recurring_concept"}


# ============================================================================
# PROPERTY 8: Confidence Bounds
# ============================================================================

class TestP8ConfidenceBounds:
    """Confidence scores are always in [0.0, 1.0]."""
    
    @given(
        temporal_conf=st.floats(0.0, 1.0),
        domain_conf=st.floats(0.0, 1.0),
        concept_conf=st.floats(0.0, 1.0),
    )
    @settings(max_examples=100)
    def test_confidence_within_bounds(self, temporal_conf, domain_conf, concept_conf):
        """Configured confidences are used correctly."""
        surfacer = ProactiveSurfacer(
            temporal_confidence=temporal_conf,
            domain_confidence=domain_conf,
            concept_confidence=concept_conf,
        )
        
        # Force all trigger types
        temporal = surfacer.check_temporal_trigger(
            "m1", "T1", "at standup", "standup meeting"
        )
        domain = surfacer.check_domain_trigger(
            "m2", "T2", "work", "work"
        )
        concept = surfacer.check_concept_trigger(
            "m3", "T3", ["a", "b", "c"], ["a", "b", "d"]
        )
        
        if temporal:
            assert 0.0 <= temporal.confidence <= 1.0
            assert temporal.confidence == temporal_conf
        
        if domain:
            assert 0.0 <= domain.confidence <= 1.0
            assert domain.confidence == domain_conf
        
        if concept:
            assert 0.0 <= concept.confidence <= 1.0
            assert concept.confidence == concept_conf
    
    def test_default_confidences(self):
        """Default confidence values are sensible."""
        surfacer = ProactiveSurfacer()
        
        # Defaults: temporal=0.7, domain=0.6, concept=0.5
        temporal = surfacer.check_temporal_trigger(
            "m1", "T1", "at standup", "standup meeting"
        )
        domain = surfacer.check_domain_trigger(
            "m2", "T2", "work", "work"
        )
        concept = surfacer.check_concept_trigger(
            "m3", "T3", ["a", "b", "c"], ["a", "b", "d"]
        )
        
        assert temporal.confidence == 0.7
        assert domain.confidence == 0.6
        assert concept.confidence == 0.5
        
        # Temporal > Domain > Concept (priority order)
        assert temporal.confidence > domain.confidence > concept.confidence


# ============================================================================
# INTEGRATION: get_proactive_surfaces()
# ============================================================================

class TestProactiveSurfacesIntegration:
    """Test batch proactive surfacing."""
    
    def test_returns_sorted_by_confidence(self):
        """Suggestions sorted by confidence descending."""
        surfacer = ProactiveSurfacer()
        
        memories = [
            {"id": "m1", "title": "T1", "domain": "work", "concepts": ["a", "b"], "surfaces_when": None},
            {"id": "m2", "title": "T2", "domain": "work", "concepts": ["c", "d"], "surfaces_when": "at standup"},
        ]
        
        suggestions = surfacer.get_proactive_surfaces(
            memories=memories,
            current_context="standup meeting",
            conversation_domain="work",
            recent_concepts=["a", "b"]
        )
        
        assert len(suggestions) == 2
        # Temporal has higher confidence than domain
        assert suggestions[0].trigger == "temporal"
        assert suggestions[0].confidence >= suggestions[1].confidence
    
    def test_deduplication(self):
        """Each memory suggested at most once."""
        surfacer = ProactiveSurfacer()
        
        memories = [
            {
                "id": "m1",
                "title": "Multi-trigger",
                "domain": "work",
                "concepts": ["a", "b", "c"],
                "surfaces_when": "at standup"
            },
        ]
        
        suggestions = surfacer.get_proactive_surfaces(
            memories=memories,
            current_context="standup meeting about work",
            conversation_domain="work",
            recent_concepts=["a", "b", "x"]
        )
        
        # Should only appear once (temporal takes priority)
        assert len(suggestions) == 1
        assert suggestions[0].memory_id == "m1"
        assert suggestions[0].trigger == "temporal"
    
    def test_limit_to_five(self):
        """Returns at most 5 suggestions."""
        surfacer = ProactiveSurfacer()
        
        memories = [
            {"id": f"m{i}", "title": f"T{i}", "domain": "work", "concepts": [], "surfaces_when": None}
            for i in range(10)
        ]
        
        suggestions = surfacer.get_proactive_surfaces(
            memories=memories,
            current_context="work stuff",
            conversation_domain="work",
            recent_concepts=[]
        )
        
        assert len(suggestions) <= 5
    
    def test_empty_memories(self):
        """Empty memories list returns empty suggestions."""
        surfacer = ProactiveSurfacer()
        
        suggestions = surfacer.get_proactive_surfaces(
            memories=[],
            current_context="anything",
            conversation_domain="work",
            recent_concepts=["a", "b"]
        )
        
        assert suggestions == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
