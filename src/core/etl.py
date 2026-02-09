"""
Elefante ETL Pipeline - Agent-Brain Architecture

Two-phase memory ingestion where PHASE 2 uses the AGENT's LLM brain:

1. INGEST (elefanteMemoryAdd): 
   - Fast, non-blocking raw storage
   - Returns immediately with processing_status="raw"
   
2. PROCESS (elefanteETLProcess + elefanteETLClassify):
   - elefanteETLProcess: Returns raw memories TO THE AGENT
   - Agent's LLM classifies (ring, knowledge_type, topic, summary)
   - elefanteETLClassify: Agent sends classification back, system updates memory

This architecture keeps Elefante LLM-FREE while leveraging agent intelligence.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
from uuid import UUID

from src.utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# PROCESSING STATUS
# =============================================================================

class ProcessingStatus:
    """Memory lifecycle states"""
    RAW = "raw"              # Just ingested, awaiting agent classification
    PROCESSING = "processing" # Handed to agent for classification
    PROCESSED = "processed"   # Agent classified, fully placed in topology
    FAILED = "failed"         # Classification failed


# =============================================================================
# ETL PROCESSOR (Agent-Driven)
# =============================================================================

class ETLProcessor:
    """
    ETL Processor that delegates classification to the agent's brain.
    
    Flow:
    1. get_raw_memories() → Returns unclassified memories for agent
    2. Agent analyzes and classifies using its LLM
    3. apply_classification() → Agent sends classification, we persist
    """
    
    def __init__(self, vector_store=None, graph_store=None):
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.logger = get_logger(self.__class__.__name__)
    
    async def get_raw_memories(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get raw/unclassified memories for agent to classify.
        
        Returns simplified dict format for agent processing.
        Sets status to PROCESSING to prevent double-processing.
        """
        if not self.vector_store:
            from src.core.vector_store import get_vector_store
            self.vector_store = get_vector_store()
        
        # Get all memories and filter for raw status
        all_memories = await self.vector_store.get_all(limit=500)
        
        raw_memories = []
        for memory in all_memories:
            cm = memory.metadata.custom_metadata or {}
            status = cm.get("processing_status", ProcessingStatus.RAW)
            
            # Include raw or missing status
            if status in (ProcessingStatus.RAW, None, ""):
                raw_memories.append(memory)
                
            if len(raw_memories) >= limit:
                break
        
        # Mark as PROCESSING and return simplified format
        result = []
        for memory in raw_memories:
            # Update status to prevent duplicate processing
            cm = memory.metadata.custom_metadata or {}
            cm["processing_status"] = ProcessingStatus.PROCESSING
            memory.metadata.custom_metadata = cm
            
            try:
                await self.vector_store.replace_memory(memory)
            except Exception as e:
                self.logger.warning(f"Could not mark processing: {e}")
            
            # Return simplified format for agent
            result.append({
                "id": str(memory.id),
                "content": memory.content,
                "title": cm.get("title", ""),
                "score": memory.metadata.score,
                "memory_type": memory.metadata.memory_type.value if hasattr(memory.metadata.memory_type, "value") else str(memory.metadata.memory_type),
                "tags": memory.metadata.tags or [],
                "created_at": memory.metadata.created_at.isoformat() if memory.metadata.created_at else None,
            })
        
        return result
    
    async def apply_classification(
        self,
        memory_id: str,
        ring: str,
        knowledge_type: str,
        topic: str,
        summary: str,
        owner_id: str = "owner-jay"
    ) -> Dict[str, Any]:
        """
        Apply agent's classification to a memory.
        
        Called by agent after it classifies the memory using its LLM.
        """
        if not self.vector_store:
            from src.core.vector_store import get_vector_store
            self.vector_store = get_vector_store()
        
        # Fetch memory
        mem_uuid = UUID(memory_id)
        memory = await self.vector_store.get_by_id(mem_uuid)
        
        if not memory:
            return {
                "success": False,
                "error": f"Memory {memory_id} not found"
            }
        
        # Update metadata with agent's classification
        cm = memory.metadata.custom_metadata or {}
        cm["ring"] = ring
        cm["knowledge_type"] = knowledge_type
        cm["topic"] = topic
        cm["summary"] = summary
        cm["owner_id"] = owner_id
        cm["processing_status"] = ProcessingStatus.PROCESSED
        cm["processed_at"] = datetime.utcnow().isoformat()
        cm["classified_by"] = "agent"  # Track that agent did classification
        
        memory.metadata.custom_metadata = cm
        
        # Persist
        await self.vector_store.replace_memory(memory)
        
        self.logger.info(
            "memory_classified",
            memory_id=memory_id,
            ring=ring,
            knowledge_type=knowledge_type,
            topic=topic,
            classified_by="agent"
        )
        
        return {
            "success": True,
            "memory_id": memory_id,
            "ring": ring,
            "knowledge_type": knowledge_type,
            "topic": topic,
            "summary": summary,
        }
    
    async def mark_failed(self, memory_id: str, error: str) -> Dict[str, Any]:
        """Mark a memory as failed classification."""
        if not self.vector_store:
            from src.core.vector_store import get_vector_store
            self.vector_store = get_vector_store()
        
        memory = await self.vector_store.get_by_id(UUID(memory_id))
        if not memory:
            return {"success": False, "error": "Memory not found"}
        
        cm = memory.metadata.custom_metadata or {}
        cm["processing_status"] = ProcessingStatus.FAILED
        cm["processing_error"] = error
        memory.metadata.custom_metadata = cm
        
        await self.vector_store.replace_memory(memory)
        
        return {"success": True, "memory_id": memory_id, "status": "failed"}
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get ETL processing statistics."""
        if not self.vector_store:
            from src.core.vector_store import get_vector_store
            self.vector_store = get_vector_store()
        
        all_memories = await self.vector_store.get_all(limit=1000)
        
        stats = {
            "total": len(all_memories),
            "raw": 0,
            "processing": 0,
            "processed": 0,
            "failed": 0,
            "unclassified": 0,  # No status field at all
        }
        
        for memory in all_memories:
            cm = memory.metadata.custom_metadata or {}
            status = cm.get("processing_status")
            
            if status == ProcessingStatus.RAW:
                stats["raw"] += 1
            elif status == ProcessingStatus.PROCESSING:
                stats["processing"] += 1
            elif status == ProcessingStatus.PROCESSED:
                stats["processed"] += 1
            elif status == ProcessingStatus.FAILED:
                stats["failed"] += 1
            else:
                stats["unclassified"] += 1
        
        return stats


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_etl_instance: Optional[ETLProcessor] = None


def get_etl_processor() -> ETLProcessor:
    """Get singleton ETL processor instance."""
    global _etl_instance
    if _etl_instance is None:
        _etl_instance = ETLProcessor()
    return _etl_instance
