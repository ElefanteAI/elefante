"""
Tests for Conversation Context Retriever

Tests the conversation context search functionality that provides
context-aware memory retrieval from recent conversation history.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from uuid import uuid4

from src.core.conversation_context import ConversationSearcher, get_conversation_searcher
from src.models.conversation import SearchCandidate
from src.models.memory import Memory, MemoryMetadata, MemoryType


class TestConversationSearcher:
    """Test suite for ConversationSearcher class"""
    
    @pytest.fixture
    def searcher(self):
        """Create a conversation searcher instance"""
        return ConversationSearcher(max_window=50)
    
    @pytest.fixture
    def mock_vector_store(self):
        """Mock vector store"""
        store = MagicMock()
        store.search = AsyncMock()
        return store
    
    def test_extract_keywords_basic(self, searcher):
        """Test basic keyword extraction"""
        query = "What is the best way to configure this?"
        keywords = searcher._extract_keywords(query)
        
        # Should extract meaningful words
        assert "best" in keywords
        assert "way" in keywords
        assert "configure" in keywords
        assert "what" in keywords  # "what" is not in stop words list
        # Stop words should be excluded
        assert "is" not in keywords
        assert "the" not in keywords
        assert "to" not in keywords
        assert "this" not in keywords  # "this" is in stop words
    
    def test_extract_keywords_with_punctuation(self, searcher):
        """Test keyword extraction strips punctuation"""
        query = "Hello, world! How are you?"
        keywords = searcher._extract_keywords(query)
        
        assert "hello" in keywords
        assert "world" in keywords
        # Punctuation should be stripped
        assert "hello," not in keywords
        assert "world!" not in keywords
    
    def test_extract_keywords_empty_query(self, searcher):
        """Test keyword extraction with empty query"""
        keywords = searcher._extract_keywords("")
        assert len(keywords) == 0
    
    def test_extract_keywords_only_stop_words(self, searcher):
        """Test keyword extraction with only stop words"""
        query = "the and is it"
        keywords = searcher._extract_keywords(query)
        assert len(keywords) == 0
    
    def test_score_by_recency_recent_message(self, searcher):
        """Test recency scoring for recent message"""
        now = datetime.utcnow()
        recent = now - timedelta(minutes=5)
        
        score = searcher._score_by_recency(recent, now)
        
        # Recent message should have high score (close to 1.0)
        assert score > 0.9
    
    def test_score_by_recency_old_message(self, searcher):
        """Test recency scoring for old message"""
        now = datetime.utcnow()
        old = now - timedelta(hours=10)
        
        score = searcher._score_by_recency(old, now)
        
        # Old message should have low score
        assert score < 0.1
    
    def test_score_by_recency_one_hour_old(self, searcher):
        """Test recency scoring at half-life (1 hour)"""
        now = datetime.utcnow()
        one_hour_ago = now - timedelta(hours=1)
        
        score = searcher._score_by_recency(one_hour_ago, now)
        
        # At half-life, score should be around 0.5
        assert 0.4 < score < 0.6
    
    def test_score_by_keywords_full_match(self, searcher):
        """Test keyword scoring with full match"""
        content = "I need to configure the database settings"
        query_terms = {"configure", "database", "settings"}
        
        score = searcher._score_by_keywords(content, query_terms)
        
        # All keywords present = 1.0
        assert score == 1.0
    
    def test_score_by_keywords_partial_match(self, searcher):
        """Test keyword scoring with partial match"""
        content = "I need to configure the system"
        query_terms = {"configure", "database", "settings"}
        
        score = searcher._score_by_keywords(content, query_terms)
        
        # 1 out of 3 keywords = 0.33
        assert score == pytest.approx(0.333, abs=0.01)
    
    def test_score_by_keywords_no_match(self, searcher):
        """Test keyword scoring with no match"""
        content = "Something completely different"
        query_terms = {"configure", "database", "settings"}
        
        score = searcher._score_by_keywords(content, query_terms)
        
        assert score == 0.0
    
    def test_score_by_keywords_empty_terms(self, searcher):
        """Test keyword scoring with empty query terms"""
        content = "Some content"
        query_terms = set()
        
        score = searcher._score_by_keywords(content, query_terms)
        
        assert score == 0.0
    
    def test_score_by_role_user(self, searcher):
        """Test role scoring for user messages"""
        score = searcher._score_by_role("user")
        assert score == 1.0
    
    def test_score_by_role_assistant(self, searcher):
        """Test role scoring for assistant messages"""
        score = searcher._score_by_role("assistant")
        assert score == 0.7
    
    def test_score_by_role_system(self, searcher):
        """Test role scoring for system messages"""
        score = searcher._score_by_role("system")
        assert score == 0.5
    
    def test_score_by_role_unknown(self, searcher):
        """Test role scoring for unknown role"""
        score = searcher._score_by_role("unknown")
        assert score == 0.5  # Default
    
    @pytest.mark.asyncio
    async def test_collect_candidates_empty_session(self, searcher, mock_vector_store):
        """Test collecting candidates with no session history"""
        searcher.vector_store = mock_vector_store
        
        # Mock empty search results
        mock_vector_store.search.return_value = []
        
        session_id = uuid4()
        candidates = await searcher.collect_candidates(
            query="test query",
            session_id=session_id,
            limit=10
        )
        
        assert len(candidates) == 0
    
    @pytest.mark.asyncio
    async def test_collect_candidates_with_results(self, searcher, mock_vector_store):
        """Test collecting candidates with session history"""
        searcher.vector_store = mock_vector_store
        
        session_id = uuid4()
        now = datetime.utcnow()
        
        # Create mock memories
        mock_memory = Memory(
            id=uuid4(),
            content="I need to configure the database",
            metadata=MemoryMetadata(
                memory_type=MemoryType.CONVERSATION,
                source="user",
                timestamp=now - timedelta(minutes=5),
                session_id=session_id,
                importance=5
            )
        )
        
        # Mock search result
        mock_result = MagicMock()
        mock_result.memory = mock_memory
        mock_vector_store.search.return_value = [mock_result]
        
        candidates = await searcher.collect_candidates(
            query="configure database",
            session_id=session_id,
            limit=10
        )
        
        assert len(candidates) == 1
        assert candidates[0].source == "conversation"
        assert candidates[0].text == "I need to configure the database"
        assert 0.0 <= candidates[0].score <= 1.0
        assert "timestamp" in candidates[0].metadata
        assert "role" in candidates[0].metadata
    
    @pytest.mark.asyncio
    async def test_collect_candidates_scoring(self, searcher, mock_vector_store):
        """Test that candidates are properly scored and sorted"""
        searcher.vector_store = mock_vector_store
        
        session_id = uuid4()
        now = datetime.utcnow()
        
        # Create memories with different characteristics
        recent_relevant = Memory(
            id=uuid4(),
            content="configure database settings",
            metadata=MemoryMetadata(
                memory_type=MemoryType.CONVERSATION,
                source="user",
                timestamp=now - timedelta(minutes=1),  # Very recent
                session_id=session_id,
                importance=5
            )
        )
        
        old_relevant = Memory(
            id=uuid4(),
            content="configure database settings",
            metadata=MemoryMetadata(
                memory_type=MemoryType.CONVERSATION,
                source="user",
                timestamp=now - timedelta(hours=5),  # Old
                session_id=session_id,
                importance=5
            )
        )
        
        recent_irrelevant = Memory(
            id=uuid4(),
            content="something completely different",
            metadata=MemoryMetadata(
                memory_type=MemoryType.CONVERSATION,
                source="assistant",
                timestamp=now - timedelta(minutes=2),
                session_id=session_id,
                importance=5
            )
        )
        
        # Mock search results
        mock_results = [
            MagicMock(memory=recent_relevant),
            MagicMock(memory=old_relevant),
            MagicMock(memory=recent_irrelevant)
        ]
        mock_vector_store.search.return_value = mock_results
        
        candidates = await searcher.collect_candidates(
            query="configure database",
            session_id=session_id,
            limit=10
        )
        
        # Should have all 3 candidates
        assert len(candidates) == 3
        
        # Recent + relevant should score highest
        assert candidates[0].text == "configure database settings"
        assert candidates[0].metadata["timestamp"] == (now - timedelta(minutes=1)).isoformat()
        
        # Scores should be in descending order
        assert candidates[0].score >= candidates[1].score >= candidates[2].score
    
    @pytest.mark.asyncio
    async def test_collect_candidates_respects_limit(self, searcher, mock_vector_store):
        """Test that candidate collection respects limit"""
        searcher.vector_store = mock_vector_store
        
        session_id = uuid4()
        now = datetime.utcnow()
        
        # Create many mock memories
        mock_results = []
        for i in range(20):
            memory = Memory(
                id=uuid4(),
                content=f"Message {i}",
                metadata=MemoryMetadata(
                    memory_type=MemoryType.CONVERSATION,
                    source="user",
                    timestamp=now - timedelta(minutes=i),
                    session_id=session_id,
                    importance=5
                )
            )
            mock_results.append(MagicMock(memory=memory))
        
        mock_vector_store.search.return_value = mock_results
        
        candidates = await searcher.collect_candidates(
            query="test",
            session_id=session_id,
            limit=5
        )
        
        # Should respect limit
        assert len(candidates) == 5
    
    @pytest.mark.asyncio
    async def test_collect_candidates_filters_by_session(self, searcher, mock_vector_store):
        """Test that only memories from the specified session are included"""
        searcher.vector_store = mock_vector_store
        
        target_session = uuid4()
        other_session = uuid4()
        now = datetime.utcnow()
        
        # Create memories from different sessions
        target_memory = Memory(
            id=uuid4(),
            content="Target session message",
            metadata=MemoryMetadata(
                memory_type=MemoryType.CONVERSATION,
                source="user",
                timestamp=now,
                session_id=target_session,
                importance=5
            )
        )
        
        other_memory = Memory(
            id=uuid4(),
            content="Other session message",
            metadata=MemoryMetadata(
                memory_type=MemoryType.CONVERSATION,
                source="user",
                timestamp=now,
                session_id=other_session,
                importance=5
            )
        )
        
        mock_results = [
            MagicMock(memory=target_memory),
            MagicMock(memory=other_memory)
        ]
        mock_vector_store.search.return_value = mock_results
        
        candidates = await searcher.collect_candidates(
            query="test",
            session_id=target_session,
            limit=10
        )
        
        # Should only include target session
        assert len(candidates) == 1
        assert candidates[0].text == "Target session message"


class TestGetConversationSearcher:
    """Test the global conversation searcher singleton"""
    
    def test_get_conversation_searcher_creates_instance(self):
        """Test that get_conversation_searcher creates an instance"""
        searcher = get_conversation_searcher()
        assert isinstance(searcher, ConversationSearcher)
    
    def test_get_conversation_searcher_returns_singleton(self):
        """Test that get_conversation_searcher returns same instance"""
        searcher1 = get_conversation_searcher()
        searcher2 = get_conversation_searcher()
        assert searcher1 is searcher2


# Made with Bob