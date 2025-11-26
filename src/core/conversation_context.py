"""
Conversation Context Retriever for Elefante

Searches conversation history to provide context-aware memory retrieval.
Enables the system to understand pronouns and recent context.
"""

import asyncio
from typing import List, Optional, Set
from uuid import UUID
from datetime import datetime, timedelta

from src.models.conversation import Message, SearchCandidate
from src.models.memory import Memory, MemoryType
from src.core.vector_store import get_vector_store
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ConversationSearcher:
    """
    Searches conversation context for relevant messages
    
    Provides context-aware search by analyzing recent conversation history
    within a session. Scores candidates based on recency, keyword overlap,
    and message role.
    """
    
    def __init__(self, max_window: int = 50):
        """
        Initialize conversation searcher
        
        Args:
            max_window: Maximum number of recent messages to consider
        """
        self.max_window = max_window
        self.vector_store = get_vector_store()
        self.logger = get_logger(self.__class__.__name__)
    
    async def collect_candidates(
        self,
        query: str,
        session_id: UUID,
        limit: int = 10
    ) -> List[SearchCandidate]:
        """
        Retrieve and score conversation messages relevant to query
        
        This is the main entry point for conversation context search.
        It fetches recent messages from the session and scores them
        based on multiple factors.
        
        Args:
            query: Search query string
            session_id: Session UUID to filter messages
            limit: Maximum number of candidates to return
            
        Returns:
            List of SearchCandidate objects scored and ranked
        """
        self.logger.info(
            "Collecting conversation candidates",
            query=query[:100],
            session_id=str(session_id),
            limit=limit
        )
        
        try:
            # Fetch recent memories from this session
            memories = await self._fetch_session_memories(session_id)
            
            if not memories:
                self.logger.debug("No conversation history found for session")
                return []
            
            # Convert memories to candidates with scoring
            candidates = []
            query_terms = self._extract_keywords(query)
            now = datetime.utcnow()
            
            for memory in memories:
                # Calculate composite score
                recency_score = self._score_by_recency(memory.metadata.timestamp, now)
                keyword_score = self._score_by_keywords(memory.content, query_terms)
                role_score = self._score_by_role(memory.metadata.source)
                
                # Weighted combination
                final_score = (
                    recency_score * 0.5 +
                    keyword_score * 0.3 +
                    role_score * 0.2
                )
                
                candidate = SearchCandidate(
                    text=memory.content,
                    score=final_score,
                    source="conversation",
                    metadata={
                        "timestamp": memory.metadata.timestamp.isoformat(),
                        "role": memory.metadata.source,
                        "session_id": str(session_id),
                        "memory_type": memory.metadata.memory_type.value,
                        "recency_score": recency_score,
                        "keyword_score": keyword_score,
                        "role_score": role_score
                    },
                    memory_id=memory.id
                )
                
                candidates.append(candidate)
            
            # Sort by score and limit
            candidates.sort(key=lambda c: c.score, reverse=True)
            candidates = candidates[:limit]
            
            self.logger.info(
                "Conversation candidates collected",
                count=len(candidates),
                top_score=candidates[0].score if candidates else 0.0
            )
            
            return candidates
            
        except Exception as e:
            self.logger.error(f"Failed to collect conversation candidates: {e}", exc_info=True)
            return []
    
    async def _fetch_session_memories(self, session_id: UUID) -> List[Memory]:
        """
        Fetch recent memories from the session
        
        Queries the vector store for memories with matching session_id,
        limited to the most recent messages within the window.
        
        Args:
            session_id: Session UUID
            
        Returns:
            List of Memory objects from the session
        """
        try:
            # Use search to get conversation memories
            # Search with a generic query to retrieve recent conversation memories
            from src.models.query import SearchFilters
            
            # Create filters for conversation type only
            filters = SearchFilters(
                memory_type="conversation",
                min_importance=None,
                max_importance=None
            )
            
            # Search with generic query to get conversation memories
            # ChromaDB will return them sorted by relevance
            search_results = await self.vector_store.search(
                query="conversation message",  # Generic query
                limit=self.max_window * 2,  # Get more for filtering
                filters=filters,
                min_similarity=0.0  # Accept all results
            )
            
            # Extract memories and filter by session_id
            session_memories = [
                result.memory for result in search_results
                if result.memory.metadata.session_id == session_id
            ]
            
            # Sort by timestamp (newest first) and limit to window
            session_memories.sort(
                key=lambda m: m.metadata.timestamp,
                reverse=True
            )
            session_memories = session_memories[:self.max_window]
            
            self.logger.debug(
                f"Fetched {len(session_memories)} session memories",
                session_id=str(session_id)
            )
            
            return session_memories
            
        except Exception as e:
            self.logger.error(f"Failed to fetch session memories: {e}", exc_info=True)
            return []
    
    def _score_by_recency(self, timestamp: datetime, now: datetime) -> float:
        """
        Score based on message recency
        
        More recent messages get higher scores. Uses exponential decay
        with a half-life of 1 hour.
        
        Args:
            timestamp: Message timestamp
            now: Current time
            
        Returns:
            Score between 0.0 and 1.0
        """
        age_seconds = (now - timestamp).total_seconds()
        
        # Exponential decay with 1-hour half-life
        half_life_seconds = 3600  # 1 hour
        decay_factor = 0.5 ** (age_seconds / half_life_seconds)
        
        # Clamp to [0, 1]
        return max(0.0, min(1.0, decay_factor))
    
    def _score_by_keywords(self, content: str, query_terms: Set[str]) -> float:
        """
        Score based on keyword overlap
        
        Simple term matching - counts how many query terms appear
        in the content.
        
        Args:
            content: Message content
            query_terms: Set of query keywords
            
        Returns:
            Score between 0.0 and 1.0
        """
        if not query_terms:
            return 0.0
        
        content_lower = content.lower()
        matches = sum(1 for term in query_terms if term in content_lower)
        
        # Normalize by number of query terms
        return matches / len(query_terms)
    
    def _score_by_role(self, role: str) -> float:
        """
        Score based on message role
        
        User messages are prioritized over assistant messages,
        as they often contain the context we're looking for.
        
        Args:
            role: Message role (user, assistant, system)
            
        Returns:
            Score between 0.0 and 1.0
        """
        role_weights = {
            "user": 1.0,
            "assistant": 0.7,
            "system": 0.5
        }
        return role_weights.get(role, 0.5)
    
    def _extract_keywords(self, query: str) -> Set[str]:
        """
        Extract keywords from query
        
        Simple tokenization - splits on whitespace and removes
        common stop words.
        
        Args:
            query: Search query
            
        Returns:
            Set of lowercase keywords
        """
        # Common stop words to ignore
        stop_words = {
            "a", "an", "and", "are", "as", "at", "be", "by", "for",
            "from", "has", "he", "in", "is", "it", "its", "of", "on",
            "that", "the", "to", "was", "will", "with", "the", "this"
        }
        
        # Tokenize and filter
        tokens = query.lower().split()
        keywords = {
            token.strip(".,!?;:")
            for token in tokens
            if token.strip(".,!?;:") not in stop_words
            and len(token) > 2
        }
        
        return keywords


# Global singleton instance
_conversation_searcher: Optional[ConversationSearcher] = None


def get_conversation_searcher() -> ConversationSearcher:
    """
    Get or create global conversation searcher instance
    
    Returns:
        ConversationSearcher: Singleton instance
    """
    global _conversation_searcher
    if _conversation_searcher is None:
        _conversation_searcher = ConversationSearcher()
    return _conversation_searcher


# Made with Bob