"""
Score Normalization and Weighting for Hybrid Search

Provides utilities to normalize scores across heterogeneous sources
(conversation, semantic, graph) and apply adaptive weighting based
on query characteristics.
"""

from typing import List, Dict, Set
from src.models.conversation import SearchCandidate
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ScoreNormalizer:
    """
    Normalizes and combines scores from multiple search sources
    
    Handles the challenge of comparing scores from different systems:
    - Conversation: recency + keyword overlap (0-1)
    - Semantic (ChromaDB): cosine similarity (0-1)
    - Graph (Kuzu): importance/10 (0-1)
    """
    
    @staticmethod
    def normalize_scores(
        candidates: List[SearchCandidate],
        weights: Dict[str, float]
    ) -> List[SearchCandidate]:
        """
        Apply weighted scoring across sources
        
        Takes candidates from multiple sources and applies source-specific
        weights to produce normalized final scores.
        
        Args:
            candidates: List of search candidates from all sources
            weights: Dict mapping source names to weights (must sum to 1.0)
                    e.g., {"conversation": 0.3, "semantic": 0.4, "graph": 0.3}
        
        Returns:
            List of candidates with normalized scores
        """
        if not candidates:
            return []
        
        # Validate weights
        total_weight = sum(weights.values())
        if abs(total_weight - 1.0) > 0.01:
            logger.warning(
                f"Weights don't sum to 1.0 (sum={total_weight}), normalizing",
                weights=weights
            )
            # Normalize weights
            weights = {k: v / total_weight for k, v in weights.items()}
        
        # Group candidates by source
        by_source: Dict[str, List[SearchCandidate]] = {}
        for candidate in candidates:
            source = candidate.source
            if source not in by_source:
                by_source[source] = []
            by_source[source].append(candidate)
        
        # Apply weights to each source
        normalized_candidates = []
        for source, source_candidates in by_source.items():
            weight = weights.get(source, 0.0)
            
            if weight == 0.0:
                logger.debug(f"Skipping source {source} with zero weight")
                continue
            
            for candidate in source_candidates:
                # Apply weight to score
                candidate.score = candidate.score * weight
                normalized_candidates.append(candidate)
        
        logger.debug(
            "Scores normalized",
            total_candidates=len(normalized_candidates),
            weights=weights
        )
        
        return normalized_candidates
    
    @staticmethod
    def adaptive_weights(
        query: str,
        has_session: bool,
        mode: str = "hybrid"
    ) -> Dict[str, float]:
        """
        Determine optimal weights based on query characteristics
        
        Analyzes the query to decide how much to trust each source.
        Uses heuristics to detect query intent.
        
        Args:
            query: Search query string
            has_session: Whether a session_id is provided
            mode: Search mode (semantic, structured, hybrid)
        
        Returns:
            Dict of source weights that sum to 1.0
        """
        query_lower = query.lower()
        
        # Default weights for hybrid mode
        weights = {
            "conversation": 0.3,
            "semantic": 0.4,
            "graph": 0.3
        }
        
        # Adjust based on mode
        if mode == "semantic":
            weights = {"conversation": 0.0, "semantic": 1.0, "graph": 0.0}
        elif mode == "structured":
            weights = {"conversation": 0.0, "semantic": 0.0, "graph": 1.0}
        else:  # hybrid mode - apply heuristics
            
            # Priority order: pronouns > specific terms > questions > session
            # This ensures pronouns (context-dependent) take precedence
            
            # Strip punctuation for word matching
            import string
            query_words = query_lower.translate(str.maketrans('', '', string.punctuation)).split()
            
            # Detect pronouns - HIGHEST PRIORITY (boost conversation)
            pronouns = {"it", "that", "this", "these", "those", "he", "she", "they"}
            has_pronouns = any(pronoun in query_words for pronoun in pronouns)
            
            # Detect specific identifiers - HIGH PRIORITY (boost graph)
            specific_terms = {"uuid", "id", "named", "called", "entity"}
            has_specific = any(term in query_lower for term in specific_terms)
            
            # Detect questions - MEDIUM PRIORITY (boost semantic)
            question_words = {"what", "how", "why", "when", "where", "who", "which"}
            has_question = any(q in query_words for q in question_words)
            
            # Apply weights based on priority
            if has_pronouns:
                # Pronouns indicate context dependency - prioritize conversation
                weights["conversation"] = 0.6
                weights["semantic"] = 0.25
                weights["graph"] = 0.15
                logger.debug("Detected pronouns, boosting conversation weight")
            elif has_specific:
                # Specific identifiers - prioritize graph
                weights["conversation"] = 0.2
                weights["semantic"] = 0.3
                weights["graph"] = 0.5
                logger.debug("Detected specific terms, boosting graph weight")
            elif has_question:
                # Questions - prioritize semantic
                weights["conversation"] = 0.25
                weights["semantic"] = 0.5
                weights["graph"] = 0.25
                logger.debug("Detected question, boosting semantic weight")
            elif has_session:
                # Session provided but no special terms - moderate conversation boost
                weights["conversation"] = 0.4
                weights["semantic"] = 0.35
                weights["graph"] = 0.25
        
        # Normalize to ensure sum = 1.0
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}
        
        logger.info(
            "Adaptive weights calculated",
            query=query[:50],
            has_session=has_session,
            weights=weights
        )
        
        return weights
    
    @staticmethod
    def combine_scores(
        conversation_score: float,
        semantic_score: float,
        graph_score: float,
        weights: Dict[str, float]
    ) -> float:
        """
        Combine individual scores using weights
        
        Simple weighted linear combination.
        
        Args:
            conversation_score: Score from conversation context (0-1)
            semantic_score: Score from semantic search (0-1)
            graph_score: Score from graph traversal (0-1)
            weights: Source weights
        
        Returns:
            Combined score (0-1)
        """
        combined = (
            conversation_score * weights.get("conversation", 0.0) +
            semantic_score * weights.get("semantic", 0.0) +
            graph_score * weights.get("graph", 0.0)
        )
        
        # Clamp to [0, 1]
        return max(0.0, min(1.0, combined))


# Made with Bob