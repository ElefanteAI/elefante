"""
Temporal Memory Consolidation Module
Handles archiving and consolidation of low-strength memories based on temporal decay.
"""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from uuid import UUID

from src.models.memory import Memory, MemoryMetadata, MemoryType
from src.core.vector_store import get_vector_store
from src.core.graph_store import get_graph_store
from src.utils.config import get_config
from src.utils.logger import get_logger


class TemporalConsolidator:
    """
    Manages memory lifecycle based on temporal decay strength.
    Archives or consolidates memories that have decayed below threshold.
    """
    
    def __init__(self):
        self.vector_store = get_vector_store()
        self.graph_store = get_graph_store()
        self.config = get_config()
        self.logger = get_logger(self.__class__.__name__)
        
        # Consolidation thresholds
        self.weak_threshold = 2.0  # Memories below this are candidates for archival
        self.archive_threshold = 1.0  # Memories below this are archived immediately
        
    def calculate_temporal_strength(self, memory: Memory) -> float:
        """
        Calculate current temporal strength of a memory.
        Same formula as used in search scoring.
        """
        temporal_config = self.config.elefante.temporal_decay
        now = datetime.utcnow()
        
        # Calculate age-based decay
        days_old = (now - memory.metadata.created_at).days
        recency = max(0.1, 1.0 - (days_old * temporal_config.default_decay_rate))
        
        # Calculate reinforcement from access patterns
        reinforcement = 1.0 + (memory.metadata.access_count * temporal_config.default_reinforcement_factor)
        
        # Calculate access recency boost
        days_since_access = (now - memory.metadata.last_accessed).days
        access_boost = max(0.5, 1.0 - (days_since_access * temporal_config.default_decay_rate))
        
        # Final strength calculation
        strength = memory.metadata.importance * recency * reinforcement * access_boost
        
        return strength
    
    async def find_weak_memories(self, limit: int = 100) -> List[tuple[Memory, float]]:
        """
        Find memories with low temporal strength.
        Returns list of (memory, strength) tuples.
        """
        self.logger.info("Scanning for weak memories...")
        
        # Get all memories from vector store using get_all method
        # get_all returns List[Memory] directly
        all_memories = await self.vector_store.get_all(limit=limit * 2)
        
        weak_memories = []
        for memory in all_memories:
            strength = self.calculate_temporal_strength(memory)
            if strength < self.weak_threshold:
                weak_memories.append((memory, strength))
        
        # Sort by strength (weakest first)
        weak_memories.sort(key=lambda x: x[1])
        
        self.logger.info(f"Found {len(weak_memories)} weak memories (strength < {self.weak_threshold})")
        return weak_memories[:limit]
    
    async def archive_memory(self, memory: Memory) -> bool:
        """
        Archive a memory by marking it as archived in metadata.
        Archived memories are excluded from normal searches.
        """
        try:
            # Update memory metadata
            memory.metadata.archived = True
            memory.metadata.last_modified = datetime.utcnow()
            
            # Update in vector store
            await self.vector_store.update_memory(
                memory.id,
                {"archived": True, "last_modified": memory.metadata.last_modified.isoformat()}
            )
            
            # Update in graph store
            cypher = f"""
            MATCH (m:Entity {{id: '{memory.id}'}})
            SET m.archived = true, m.last_modified = '{memory.metadata.last_modified.isoformat()}'
            RETURN m
            """
            await self.graph_store.execute_query(cypher)
            
            self.logger.info(f"Archived memory {memory.id}: {memory.content[:50]}...")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to archive memory {memory.id}: {e}")
            return False
    
    async def consolidate_weak_memories(self, force: bool = False) -> Dict[str, Any]:
        """
        Main consolidation process:
        1. Find weak memories
        2. Archive those below archive threshold
        3. Report statistics
        """
        self.logger.info("Starting temporal consolidation process...")
        
        stats = {
            "scanned": 0,
            "weak_found": 0,
            "archived": 0,
            "errors": 0,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Find weak memories
        weak_memories = await self.find_weak_memories(limit=100)
        stats["scanned"] = len(weak_memories)
        stats["weak_found"] = len(weak_memories)
        
        if not weak_memories:
            self.logger.info("No weak memories found")
            return stats
        
        # Process each weak memory
        for memory, strength in weak_memories:
            # Archive if below threshold
            if strength < self.archive_threshold or force:
                success = await self.archive_memory(memory)
                if success:
                    stats["archived"] += 1
                else:
                    stats["errors"] += 1
        
        self.logger.info(
            f"Consolidation complete: {stats['archived']} archived, "
            f"{stats['errors']} errors from {stats['weak_found']} weak memories"
        )
        
        return stats
    
    async def get_consolidation_stats(self) -> Dict[str, Any]:
        """
        Get statistics about memory strength distribution.
        """
        self.logger.info("Calculating consolidation statistics...")
        
        # Get sample of memories
        # get_all returns List[Memory] directly
        all_memories = await self.vector_store.get_all(limit=500)
        
        strengths = [self.calculate_temporal_strength(m) for m in all_memories]
        
        if not strengths:
            return {
                "total_memories": 0,
                "avg_strength": 0,
                "min_strength": 0,
                "max_strength": 0,
                "weak_count": 0,
                "archive_candidates": 0
            }
        
        stats = {
            "total_memories": len(strengths),
            "avg_strength": sum(strengths) / len(strengths),
            "min_strength": min(strengths),
            "max_strength": max(strengths),
            "weak_count": sum(1 for s in strengths if s < self.weak_threshold),
            "archive_candidates": sum(1 for s in strengths if s < self.archive_threshold)
        }
        
        return stats


# Singleton instance
_consolidator_instance: Optional[TemporalConsolidator] = None


def get_temporal_consolidator() -> TemporalConsolidator:
    """Get or create the temporal consolidator singleton."""
    global _consolidator_instance
    if _consolidator_instance is None:
        _consolidator_instance = TemporalConsolidator()
    return _consolidator_instance

