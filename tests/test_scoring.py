"""
Unit tests for scoring normalization

Tests the ScoreNormalizer class and adaptive weight calculation.
"""

import pytest
from src.core.scoring import ScoreNormalizer
from src.models.conversation import SearchCandidate


class TestScoreNormalizer:
    """Test ScoreNormalizer class"""
    
    def test_normalize_scores_with_valid_weights(self):
        """Test score normalization with weights that sum to 1.0"""
        candidates = [
            SearchCandidate(text="Test 1", score=0.8, source="conversation"),
            SearchCandidate(text="Test 2", score=0.9, source="semantic"),
            SearchCandidate(text="Test 3", score=0.7, source="graph")
        ]
        
        weights = {
            "conversation": 0.3,
            "semantic": 0.4,
            "graph": 0.3
        }
        
        normalized = ScoreNormalizer.normalize_scores(candidates, weights)
        
        assert len(normalized) == 3
        # Check that scores were weighted
        assert normalized[0].score == pytest.approx(0.8 * 0.3)
        assert normalized[1].score == pytest.approx(0.9 * 0.4)
        assert normalized[2].score == pytest.approx(0.7 * 0.3)
    
    def test_normalize_scores_with_invalid_weights(self):
        """Test that weights are auto-normalized if they don't sum to 1.0"""
        candidates = [
            SearchCandidate(text="Test", score=0.5, source="conversation")
        ]
        
        # Weights sum to 2.0 (should be normalized to 0.5 each)
        weights = {
            "conversation": 1.0,
            "semantic": 1.0
        }
        
        normalized = ScoreNormalizer.normalize_scores(candidates, weights)
        
        # Score should be 0.5 * 0.5 = 0.25 (weight was normalized)
        assert normalized[0].score == pytest.approx(0.5 * 0.5)
    
    def test_normalize_scores_with_zero_weight(self):
        """Test that sources with zero weight are skipped"""
        candidates = [
            SearchCandidate(text="Test 1", score=0.8, source="conversation"),
            SearchCandidate(text="Test 2", score=0.9, source="semantic")
        ]
        
        weights = {
            "conversation": 0.0,  # Zero weight
            "semantic": 1.0
        }
        
        normalized = ScoreNormalizer.normalize_scores(candidates, weights)
        
        # Only semantic candidate should remain
        assert len(normalized) == 1
        assert normalized[0].source == "semantic"
    
    def test_normalize_scores_empty_list(self):
        """Test normalization with empty candidate list"""
        candidates = []
        weights = {"conversation": 0.5, "semantic": 0.5}
        
        normalized = ScoreNormalizer.normalize_scores(candidates, weights)
        
        assert normalized == []
    
    def test_adaptive_weights_with_pronouns(self):
        """Test that pronouns boost conversation weight"""
        query = "How do I install it?"
        weights = ScoreNormalizer.adaptive_weights(query, has_session=True, mode="hybrid")
        
        # Conversation should have highest weight due to pronoun "it"
        assert weights["conversation"] > weights["semantic"]
        assert weights["conversation"] > weights["graph"]
        assert sum(weights.values()) == pytest.approx(1.0)
    
    def test_adaptive_weights_with_specific_terms(self):
        """Test that specific terms boost graph weight"""
        query = "Find entity named Bob with UUID 12345"
        weights = ScoreNormalizer.adaptive_weights(query, has_session=False, mode="hybrid")
        
        # Graph should have highest weight due to "named" and "UUID"
        assert weights["graph"] > weights["conversation"]
        assert weights["graph"] > weights["semantic"]
        assert sum(weights.values()) == pytest.approx(1.0)
    
    def test_adaptive_weights_with_questions(self):
        """Test that questions boost semantic weight"""
        query = "What is the best way to configure the system?"
        weights = ScoreNormalizer.adaptive_weights(query, has_session=False, mode="hybrid")
        
        # Semantic should have highest weight due to "What" (no pronouns in query)
        assert weights["semantic"] >= weights["conversation"]
        assert weights["semantic"] >= weights["graph"]
        assert sum(weights.values()) == pytest.approx(1.0)
    
    def test_adaptive_weights_with_session(self):
        """Test that having a session boosts conversation weight"""
        query = "Tell me about the project"
        
        # Without session
        weights_no_session = ScoreNormalizer.adaptive_weights(query, has_session=False, mode="hybrid")
        
        # With session
        weights_with_session = ScoreNormalizer.adaptive_weights(query, has_session=True, mode="hybrid")
        
        # Conversation weight should be higher with session
        assert weights_with_session["conversation"] > weights_no_session["conversation"]
        assert sum(weights_with_session.values()) == pytest.approx(1.0)
    
    def test_adaptive_weights_semantic_mode(self):
        """Test that semantic mode gives all weight to semantic"""
        query = "Test query"
        weights = ScoreNormalizer.adaptive_weights(query, has_session=True, mode="semantic")
        
        assert weights["semantic"] == 1.0
        assert weights["conversation"] == 0.0
        assert weights["graph"] == 0.0
    
    def test_adaptive_weights_structured_mode(self):
        """Test that structured mode gives all weight to graph"""
        query = "Test query"
        weights = ScoreNormalizer.adaptive_weights(query, has_session=True, mode="structured")
        
        assert weights["graph"] == 1.0
        assert weights["conversation"] == 0.0
        assert weights["semantic"] == 0.0
    
    def test_combine_scores(self):
        """Test combining individual scores with weights"""
        weights = {
            "conversation": 0.3,
            "semantic": 0.5,
            "graph": 0.2
        }
        
        combined = ScoreNormalizer.combine_scores(
            conversation_score=0.8,
            semantic_score=0.9,
            graph_score=0.7,
            weights=weights
        )
        
        expected = (0.8 * 0.3) + (0.9 * 0.5) + (0.7 * 0.2)
        assert combined == pytest.approx(expected)
    
    def test_combine_scores_clamped(self):
        """Test that combined scores are clamped to [0, 1]"""
        weights = {"conversation": 1.0, "semantic": 0.0, "graph": 0.0}
        
        # Test upper bound
        combined = ScoreNormalizer.combine_scores(
            conversation_score=1.5,  # Invalid, but should be clamped
            semantic_score=0.0,
            graph_score=0.0,
            weights=weights
        )
        assert combined <= 1.0
        
        # Test lower bound
        combined = ScoreNormalizer.combine_scores(
            conversation_score=-0.5,  # Invalid, but should be clamped
            semantic_score=0.0,
            graph_score=0.0,
            weights=weights
        )
        assert combined >= 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Made with Bob
