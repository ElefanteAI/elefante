"""
Tests for Result Deduplication Module

Tests the deduplication logic that removes near-duplicate results
from hybrid search using embedding similarity.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.core.deduplication import ResultDeduplicator, get_deduplicator
from src.models.conversation import SearchCandidate


class TestResultDeduplicator:
    """Test suite for ResultDeduplicator class"""
    
    @pytest.fixture
    def deduplicator(self):
        """Create a deduplicator instance for testing"""
        return ResultDeduplicator(threshold=0.95)
    
    @pytest.fixture
    def mock_embedding_service(self):
        """Mock embedding service"""
        service = MagicMock()
        service.generate_embedding = AsyncMock()
        return service
    
    def test_cosine_similarity_identical(self, deduplicator):
        """Test cosine similarity with identical vectors"""
        vec = [1.0, 2.0, 3.0]
        similarity = deduplicator._cosine_similarity(vec, vec)
        assert similarity == pytest.approx(1.0)
    
    def test_cosine_similarity_orthogonal(self, deduplicator):
        """Test cosine similarity with orthogonal vectors"""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        similarity = deduplicator._cosine_similarity(vec1, vec2)
        assert similarity == pytest.approx(0.0)
    
    def test_cosine_similarity_opposite(self, deduplicator):
        """Test cosine similarity with opposite vectors"""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [-1.0, -2.0, -3.0]
        similarity = deduplicator._cosine_similarity(vec1, vec2)
        # Opposite vectors should give 0.0 (clamped from -1.0)
        assert similarity == pytest.approx(0.0)
    
    def test_cosine_similarity_empty_vectors(self, deduplicator):
        """Test cosine similarity with empty vectors"""
        similarity = deduplicator._cosine_similarity([], [])
        assert similarity == 0.0
    
    def test_cosine_similarity_mismatched_dimensions(self, deduplicator):
        """Test cosine similarity with different dimension vectors"""
        vec1 = [1.0, 2.0]
        vec2 = [1.0, 2.0, 3.0]
        similarity = deduplicator._cosine_similarity(vec1, vec2)
        assert similarity == 0.0
    
    def test_cosine_similarity_zero_magnitude(self, deduplicator):
        """Test cosine similarity with zero magnitude vector"""
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [1.0, 2.0, 3.0]
        similarity = deduplicator._cosine_similarity(vec1, vec2)
        assert similarity == 0.0
    
    def test_merge_candidates_single(self, deduplicator):
        """Test merging a single candidate (no-op)"""
        candidate = SearchCandidate(
            text="Test content",
            score=0.9,
            source="conversation",
            metadata={"key": "value"}
        )
        
        merged = deduplicator._merge_candidates([candidate])
        
        assert merged.text == candidate.text
        assert merged.score == candidate.score
        assert merged.source == candidate.source
    
    def test_merge_candidates_multiple_same_source(self, deduplicator):
        """Test merging multiple candidates from same source"""
        candidates = [
            SearchCandidate(
                text="Content A",
                score=0.9,
                source="semantic",
                metadata={"key": "value1"}
            ),
            SearchCandidate(
                text="Content A",
                score=0.8,
                source="semantic",
                metadata={"key": "value2"}
            )
        ]
        
        merged = deduplicator._merge_candidates(candidates)
        
        # Should keep highest score
        assert merged.score == 0.9
        assert merged.text == "Content A"
        # Same source, so source stays the same
        assert merged.source == "semantic"
        # Should have merged metadata
        assert "sources" in merged.metadata
        assert "merged_from" in merged.metadata
        assert merged.metadata["merged_from"] == 2
    
    def test_merge_candidates_multiple_different_sources(self, deduplicator):
        """Test merging candidates from different sources"""
        candidates = [
            SearchCandidate(
                text="Content",
                score=0.9,
                source="conversation",
                metadata={}
            ),
            SearchCandidate(
                text="Content",
                score=0.85,
                source="semantic",
                metadata={}
            ),
            SearchCandidate(
                text="Content",
                score=0.8,
                source="graph",
                metadata={}
            )
        ]
        
        merged = deduplicator._merge_candidates(candidates)
        
        # Should keep highest score
        assert merged.score == 0.9
        # Different sources should result in "hybrid"
        assert merged.source == "hybrid"
        # Should list all sources
        assert set(merged.metadata["sources"]) == {"conversation", "semantic", "graph"}
        assert merged.metadata["merged_from"] == 3
    
    @pytest.mark.asyncio
    async def test_deduplicate_empty_list(self, deduplicator):
        """Test deduplication with empty list"""
        result = await deduplicator.deduplicate([])
        assert result == []
    
    @pytest.mark.asyncio
    async def test_deduplicate_single_candidate(self, deduplicator):
        """Test deduplication with single candidate"""
        candidate = SearchCandidate(
            text="Test",
            score=0.9,
            source="semantic",
            metadata={},
            embedding=[1.0, 2.0, 3.0]
        )
        
        result = await deduplicator.deduplicate([candidate])
        
        assert len(result) == 1
        assert result[0] == candidate
    
    @pytest.mark.asyncio
    async def test_deduplicate_no_duplicates(self, deduplicator):
        """Test deduplication with no duplicates"""
        candidates = [
            SearchCandidate(
                text="Content A",
                score=0.9,
                source="semantic",
                metadata={},
                embedding=[1.0, 0.0, 0.0]
            ),
            SearchCandidate(
                text="Content B",
                score=0.8,
                source="semantic",
                metadata={},
                embedding=[0.0, 1.0, 0.0]
            )
        ]
        
        result = await deduplicator.deduplicate(candidates)
        
        # No duplicates, should return all
        assert len(result) == 2
    
    @pytest.mark.asyncio
    async def test_deduplicate_with_duplicates(self, deduplicator):
        """Test deduplication with actual duplicates"""
        # Create nearly identical embeddings (>95% similar)
        candidates = [
            SearchCandidate(
                text="Content A",
                score=0.9,
                source="conversation",
                metadata={},
                embedding=[1.0, 0.0, 0.0]
            ),
            SearchCandidate(
                text="Content A (duplicate)",
                score=0.85,
                source="semantic",
                metadata={},
                embedding=[0.99, 0.01, 0.0]  # Very similar to first
            )
        ]
        
        result = await deduplicator.deduplicate(candidates)
        
        # Should merge duplicates
        assert len(result) == 1
        # Should keep highest score
        assert result[0].score == 0.9
        # Should mark as hybrid
        assert result[0].source == "hybrid"
        assert "sources" in result[0].metadata
    
    @pytest.mark.asyncio
    async def test_ensure_embeddings_generates_missing(self, deduplicator, mock_embedding_service):
        """Test that missing embeddings are generated"""
        deduplicator.embedding_service = mock_embedding_service
        mock_embedding_service.generate_embedding.return_value = [1.0, 2.0, 3.0]
        
        candidates = [
            SearchCandidate(
                text="Content A",
                score=0.9,
                source="semantic",
                metadata={},
                embedding=None  # Missing embedding
            ),
            SearchCandidate(
                text="Content B",
                score=0.8,
                source="semantic",
                metadata={},
                embedding=[4.0, 5.0, 6.0]  # Has embedding
            )
        ]
        
        result = await deduplicator._ensure_embeddings(candidates)
        
        # Should generate embedding for first candidate only
        assert mock_embedding_service.generate_embedding.call_count == 1
        assert result[0].embedding == [1.0, 2.0, 3.0]
        assert result[1].embedding == [4.0, 5.0, 6.0]
    
    @pytest.mark.asyncio
    async def test_find_duplicate_groups(self, deduplicator):
        """Test finding duplicate groups"""
        candidates = [
            SearchCandidate(
                text="A",
                score=0.9,
                source="semantic",
                metadata={},
                embedding=[1.0, 0.0, 0.0]
            ),
            SearchCandidate(
                text="A duplicate",
                score=0.85,
                source="semantic",
                metadata={},
                embedding=[0.99, 0.01, 0.0]  # Similar to first
            ),
            SearchCandidate(
                text="B",
                score=0.8,
                source="semantic",
                metadata={},
                embedding=[0.0, 1.0, 0.0]  # Different
            )
        ]
        
        groups = await deduplicator._find_duplicate_groups(candidates)
        
        # Should have 2 groups: [0,1] and [2]
        assert len(groups) == 2
        # First group should have indices 0 and 1
        assert any(len(g) == 2 and 0 in g and 1 in g for g in groups)
        # Second group should have index 2
        assert any(len(g) == 1 and 2 in g for g in groups)


class TestGetDeduplicator:
    """Test the global deduplicator singleton"""
    
    def test_get_deduplicator_creates_instance(self):
        """Test that get_deduplicator creates an instance"""
        dedup = get_deduplicator()
        assert isinstance(dedup, ResultDeduplicator)
        assert dedup.threshold == 0.95
    
    def test_get_deduplicator_returns_same_instance(self):
        """Test that get_deduplicator returns singleton"""
        dedup1 = get_deduplicator()
        dedup2 = get_deduplicator()
        assert dedup1 is dedup2
    
    def test_get_deduplicator_different_threshold(self):
        """Test that different threshold creates new instance"""
        dedup1 = get_deduplicator(threshold=0.95)
        dedup2 = get_deduplicator(threshold=0.90)
        assert dedup1 is not dedup2
        assert dedup2.threshold == 0.90


# Made with Bob