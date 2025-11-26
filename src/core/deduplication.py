"""
Result Deduplication for Hybrid Search

Removes near-duplicate results using embedding similarity to prevent
redundant results from appearing when the same content exists in
multiple sources (conversation + stored memory).
"""

import asyncio
from typing import List, Set, Dict, Optional
from uuid import UUID

from src.models.conversation import SearchCandidate
from src.core.embeddings import get_embedding_service
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ResultDeduplicator:
    """
    Deduplicates search results using embedding similarity
    
    When the same content appears in both conversation context and
    stored memories, we want to show it only once with merged metadata.
    """
    
    def __init__(self, threshold: float = 0.95):
        """
        Initialize deduplicator
        
        Args:
            threshold: Cosine similarity threshold for considering duplicates (0-1)
                      Default 0.95 means 95% similar = duplicate
        """
        self.threshold = threshold
        self.embedding_service = get_embedding_service()
        self.logger = get_logger(self.__class__.__name__)
    
    async def deduplicate(
        self,
        candidates: List[SearchCandidate]
    ) -> List[SearchCandidate]:
        """
        Remove near-duplicate candidates
        
        Process:
        1. Generate embeddings for all candidates (if not present)
        2. Compute pairwise cosine similarity
        3. Group candidates with similarity > threshold
        4. Keep highest-scored candidate from each group
        5. Merge metadata (sources array)
        
        Args:
            candidates: List of search candidates
        
        Returns:
            Deduplicated list of candidates
        """
        if not candidates:
            return []
        
        if len(candidates) == 1:
            return candidates
        
        self.logger.info(
            "Starting deduplication",
            count=len(candidates),
            threshold=self.threshold
        )
        
        try:
            # Ensure all candidates have embeddings
            candidates = await self._ensure_embeddings(candidates)
            
            # Find duplicate groups
            duplicate_groups = await self._find_duplicate_groups(candidates)
            
            # Keep best from each group
            deduplicated = self._merge_groups(duplicate_groups, candidates)
            
            removed_count = len(candidates) - len(deduplicated)
            self.logger.info(
                "Deduplication completed",
                original_count=len(candidates),
                final_count=len(deduplicated),
                removed=removed_count
            )
            
            return deduplicated
            
        except Exception as e:
            self.logger.error(f"Deduplication failed: {e}", exc_info=True)
            # Return original candidates if deduplication fails
            return candidates
    
    async def _ensure_embeddings(
        self,
        candidates: List[SearchCandidate]
    ) -> List[SearchCandidate]:
        """
        Generate embeddings for candidates that don't have them
        
        Args:
            candidates: List of candidates
        
        Returns:
            Candidates with embeddings populated
        """
        tasks = []
        indices_needing_embeddings = []
        
        for i, candidate in enumerate(candidates):
            if candidate.embedding is None:
                indices_needing_embeddings.append(i)
                tasks.append(
                    self.embedding_service.generate_embedding(candidate.text)
                )
        
        if tasks:
            self.logger.debug(f"Generating {len(tasks)} embeddings for deduplication")
            embeddings = await asyncio.gather(*tasks)
            
            # Assign embeddings back to candidates
            for idx, embedding in zip(indices_needing_embeddings, embeddings):
                candidates[idx].embedding = embedding
        
        return candidates
    
    async def _find_duplicate_groups(
        self,
        candidates: List[SearchCandidate]
    ) -> List[Set[int]]:
        """
        Find groups of duplicate candidates using embedding similarity
        
        Args:
            candidates: List of candidates with embeddings
        
        Returns:
            List of sets, each containing indices of duplicate candidates
        """
        n = len(candidates)
        visited = [False] * n
        groups = []
        
        for i in range(n):
            if visited[i]:
                continue
            
            # Start new group with current candidate
            group = {i}
            visited[i] = True
            
            # Find all candidates similar to this one
            for j in range(i + 1, n):
                if visited[j]:
                    continue
                
                # Skip if either embedding is None (shouldn't happen after _ensure_embeddings)
                emb_i = candidates[i].embedding
                emb_j = candidates[j].embedding
                
                if emb_i is None or emb_j is None:
                    continue
                
                similarity = self._cosine_similarity(emb_i, emb_j)
                
                if similarity >= self.threshold:
                    group.add(j)
                    visited[j] = True
            
            groups.append(group)
        
        # Log duplicate groups found
        duplicate_groups = [g for g in groups if len(g) > 1]
        if duplicate_groups:
            self.logger.debug(
                f"Found {len(duplicate_groups)} duplicate groups",
                group_sizes=[len(g) for g in duplicate_groups]
            )
        
        return groups
    
    def _merge_groups(
        self,
        groups: List[Set[int]],
        candidates: List[SearchCandidate]
    ) -> List[SearchCandidate]:
        """
        Merge duplicate groups, keeping the best candidate from each
        
        Args:
            groups: List of index sets representing duplicate groups
            candidates: Original candidates
        
        Returns:
            Deduplicated candidates with merged metadata
        """
        result = []
        
        for group in groups:
            if len(group) == 1:
                # No duplicates, keep as-is
                idx = next(iter(group))
                result.append(candidates[idx])
            else:
                # Multiple duplicates, merge them
                group_candidates = [candidates[i] for i in group]
                merged = self._merge_candidates(group_candidates)
                result.append(merged)
        
        return result
    
    def _merge_candidates(
        self,
        candidates: List[SearchCandidate]
    ) -> SearchCandidate:
        """
        Merge multiple duplicate candidates into one
        
        Strategy:
        - Keep the candidate with highest score
        - Merge sources in metadata
        - Combine other metadata fields
        
        Args:
            candidates: List of duplicate candidates
        
        Returns:
            Single merged candidate
        """
        # Sort by score (highest first)
        candidates.sort(key=lambda c: c.score, reverse=True)
        best = candidates[0]
        
        # Collect all sources
        sources = set()
        all_metadata = {}
        
        for candidate in candidates:
            sources.add(candidate.source)
            
            # Merge metadata
            for key, value in candidate.metadata.items():
                if key == "sources":
                    # Already handled above
                    continue
                elif key not in all_metadata:
                    all_metadata[key] = value
                elif isinstance(value, list):
                    # Merge lists
                    if isinstance(all_metadata[key], list):
                        all_metadata[key].extend(value)
                    else:
                        all_metadata[key] = [all_metadata[key]] + value
        
        # Create merged candidate
        merged = SearchCandidate(
            text=best.text,
            score=best.score,  # Keep highest score
            source="hybrid" if len(sources) > 1 else best.source,
            metadata={
                **all_metadata,
                "sources": list(sources),
                "merged_from": len(candidates)
            },
            embedding=best.embedding,
            memory_id=best.memory_id
        )
        
        self.logger.debug(
            f"Merged {len(candidates)} candidates",
            sources=list(sources),
            final_score=merged.score
        )
        
        return merged
    
    def _cosine_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float]
    ) -> float:
        """
        Calculate cosine similarity between two embeddings
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
        
        Returns:
            Cosine similarity (0-1, where 1 = identical)
        """
        if not embedding1 or not embedding2:
            return 0.0
        
        if len(embedding1) != len(embedding2):
            self.logger.warning("Embedding dimension mismatch")
            return 0.0
        
        # Dot product
        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
        
        # Magnitudes
        magnitude1 = sum(a * a for a in embedding1) ** 0.5
        magnitude2 = sum(b * b for b in embedding2) ** 0.5
        
        if magnitude1 == 0.0 or magnitude2 == 0.0:
            return 0.0
        
        # Cosine similarity
        similarity = dot_product / (magnitude1 * magnitude2)
        
        # Clamp to [0, 1] (should already be in [-1, 1])
        return max(0.0, min(1.0, similarity))


# Global singleton instance
_deduplicator: Optional[ResultDeduplicator] = None


def get_deduplicator(threshold: float = 0.95) -> ResultDeduplicator:
    """
    Get or create global deduplicator instance
    
    Args:
        threshold: Similarity threshold for duplicates
    
    Returns:
        ResultDeduplicator: Singleton instance
    """
    global _deduplicator
    if _deduplicator is None or _deduplicator.threshold != threshold:
        _deduplicator = ResultDeduplicator(threshold)
    return _deduplicator


# Made with Bob