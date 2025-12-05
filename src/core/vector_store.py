"""
Vector store implementation using ChromaDB

Provides semantic memory storage and retrieval using vector embeddings.
"""

import asyncio
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from pathlib import Path

from src.models.memory import Memory, MemoryMetadata
from src.models.query import SearchResult, SearchFilters
from src.core.embeddings import get_embedding_service
from src.utils.config import get_config
from src.utils.logger import get_logger
from src.utils.validators import validate_memory_content, validate_limit

logger = get_logger(__name__)


class VectorStore:
    """
    Vector store for semantic memory using ChromaDB
    
    Stores memories with their vector embeddings and provides
    similarity-based search capabilities.
    """
    
    def __init__(self, collection_name: Optional[str] = None, persist_directory: Optional[str] = None):
        """
        Initialize vector store
        
        Args:
            collection_name: Name of the ChromaDB collection
            persist_directory: Directory for persistent storage
        """
        self.config = get_config()
        self.collection_name = collection_name or self.config.elefante.vector_store.collection_name
        self.persist_directory = persist_directory or self.config.elefante.vector_store.persist_directory
        self.distance_metric = self.config.elefante.vector_store.distance_metric
        
        self._client = None
        self._collection = None
        self._embedding_service = get_embedding_service()
        
        logger.info(
            "initializing_vector_store",
            collection=self.collection_name,
            persist_dir=self.persist_directory
        )
    
    def _initialize_client(self):
        """Initialize ChromaDB client (lazy loading)"""
        if self._client is not None:
            return
        
        try:
            import chromadb
            from chromadb.config import Settings
            
            # Create persist directory if it doesn't exist
            Path(self.persist_directory).mkdir(parents=True, exist_ok=True)
            
            # Initialize client with persistent storage
            self._client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(
                    anonymized_telemetry=self.config.elefante.anonymized_telemetry,
                    allow_reset=True
                )
            )
            
            # Get or create collection
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": self.distance_metric}
            )
            
            logger.info(
                "chromadb_initialized",
                collection=self.collection_name,
                count=self._collection.count()
            )
            
        except ImportError:
            logger.error("chromadb_not_installed")
            raise ImportError(
                "chromadb not installed. "
                "Install with: pip install chromadb"
            )
        except Exception as e:
            logger.error("failed_to_initialize_chromadb", error=str(e))
            raise
    
    async def add_memory(self, memory: Memory) -> str:
        """
        Add a memory to the vector store
        
        Args:
            memory: Memory object to store
            
        Returns:
            Memory ID as string
        """
        self._initialize_client()
        
        # Validate content
        validate_memory_content(memory.content)
        
        # Generate embedding if not provided
        if memory.embedding is None:
            logger.debug("generating_embedding", memory_id=str(memory.id))
            memory.embedding = await self._embedding_service.generate_embedding(memory.content)
        
        # Prepare metadata for ChromaDB (V2.0 Schema)
        metadata = {
            # Layer 1: Core Identity
            "created_at": memory.metadata.created_at.isoformat(),
            "created_by": memory.metadata.created_by,
            
            # Layer 2: Classification (3-level taxonomy)
            "domain": memory.metadata.domain.value if hasattr(memory.metadata.domain, 'value') else str(memory.metadata.domain),
            "category": memory.metadata.category,
            "memory_type": memory.metadata.memory_type.value if hasattr(memory.metadata.memory_type, 'value') else str(memory.metadata.memory_type),
            "subcategory": memory.metadata.subcategory or "",
            
            # Layer 3: Semantic Metadata
            "intent": memory.metadata.intent.value if hasattr(memory.metadata.intent, 'value') else str(memory.metadata.intent),
            "importance": memory.metadata.importance,
            "urgency": memory.metadata.urgency,
            "confidence": memory.metadata.confidence,
            "tags": ",".join(memory.metadata.tags) if memory.metadata.tags else "",
            "keywords": ",".join(memory.metadata.keywords) if memory.metadata.keywords else "",
            
            # Layer 4: Relationships (IDs only, graph stores full relationships)
            "status": memory.metadata.status.value if hasattr(memory.metadata.status, 'value') else str(memory.metadata.status),
            "parent_id": str(memory.metadata.parent_id) if memory.metadata.parent_id else "",
            
            # Layer 5: Source Attribution
            "source": memory.metadata.source.value if hasattr(memory.metadata.source, 'value') else str(memory.metadata.source),
            "source_reliability": memory.metadata.source_reliability,
            "verified": memory.metadata.verified,
            
            # Layer 6: Context Anchoring
            "project": memory.metadata.project or "",
            "file_path": memory.metadata.file_path or "",
            "session_id": str(memory.metadata.session_id) if memory.metadata.session_id else "",
            
            # Layer 7: Temporal Intelligence
            "last_accessed": memory.metadata.last_accessed.isoformat(),
            "access_count": memory.metadata.access_count,
            
            # Layer 8: Quality & Lifecycle
            "version": memory.metadata.version,
            "deprecated": memory.metadata.deprecated,
        }
        
        # Add to collection
        try:
            await asyncio.to_thread(
                self._collection.add,
                ids=[str(memory.id)],
                embeddings=[memory.embedding],
                documents=[memory.content],
                metadatas=[metadata]
            )
            
            # Handle both enum and string types for memory_type
            mem_type = memory.metadata.memory_type
            if hasattr(mem_type, 'value'):
                mem_type = mem_type.value
            
            logger.info(
                "memory_added",
                memory_id=str(memory.id),
                type=mem_type
            )
            
            return str(memory.id)
            
        except Exception as e:
            logger.error("failed_to_add_memory", memory_id=str(memory.id), error=str(e))
            raise
    
    async def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[SearchFilters] = None,
        min_similarity: Optional[float] = None,
        apply_temporal_decay: bool = True
    ) -> List[SearchResult]:
        """
        Search for similar memories with optional temporal decay
        
        Args:
            query: Search query text
            limit: Maximum number of results
            filters: Optional filters to apply
            min_similarity: Minimum similarity threshold (0-1)
            apply_temporal_decay: Apply temporal strength scoring (default: True)
            
        Returns:
            List of search results with scores
        """
        self._initialize_client()
        
        # Validate inputs
        limit = validate_limit(limit)
        min_similarity = min_similarity or self.config.elefante.orchestrator.min_similarity
        
        # Check if temporal decay is enabled in config
        temporal_enabled = (
            apply_temporal_decay and
            hasattr(self.config.elefante, 'temporal_decay') and
            self.config.elefante.temporal_decay.enabled
        )
        
        # Get more results if temporal decay is enabled (for re-ranking)
        search_limit = limit * 2 if temporal_enabled else limit
        
        # Generate query embedding
        logger.debug("searching_memories", query=query[:50], limit=limit, temporal_decay=temporal_enabled)
        query_embedding = await self._embedding_service.generate_embedding(query)
        
        # Build where clause from filters
        where_clause = self._build_where_clause(filters) if filters else None
        
        # Perform search
        try:
            results = await asyncio.to_thread(
                self._collection.query,
                query_embeddings=[query_embedding],
                n_results=search_limit,
                where=where_clause,
                include=["documents", "metadatas", "distances"]
            )
            
            # Convert to SearchResult objects
            search_results = []
            current_time = datetime.utcnow()
            
            if results and results['ids'] and len(results['ids'][0]) > 0:
                for i in range(len(results['ids'][0])):
                    memory_id = results['ids'][0][i]
                    content = results['documents'][0][i]
                    metadata_dict = results['metadatas'][0][i]
                    distance = results['distances'][0][i]
                    
                    # Convert distance to similarity score (0-1)
                    # For cosine distance: similarity = 1 - distance
                    similarity = 1.0 - distance
                    
                    # Clamp similarity to [0.0, 1.0] to handle floating-point precision issues
                    similarity = max(0.0, min(1.0, similarity))
                    
                    # Filter by minimum similarity
                    if similarity < min_similarity:
                        continue
                    
                    # Reconstruct memory object
                    memory = self._reconstruct_memory(memory_id, content, metadata_dict)
                    memory.similarity_score = similarity
                    
                    # Apply temporal decay if enabled
                    final_score = similarity
                    if temporal_enabled:
                        # Calculate temporal strength
                        temporal_score = memory.calculate_relevance_score(current_time)
                        
                        # Blend semantic and temporal scores
                        semantic_weight = self.config.elefante.temporal_decay.semantic_weight
                        temporal_weight = self.config.elefante.temporal_decay.temporal_weight
                        final_score = (semantic_weight * similarity) + (temporal_weight * temporal_score)
                        
                        # Update access tracking
                        memory.record_access()
                        # Note: Access count update will be persisted by orchestrator
                    
                    # Create search result
                    result = SearchResult(
                        memory=memory,
                        score=final_score,
                        source="vector",
                        vector_score=similarity
                    )
                    
                    search_results.append(result)
            
            # Re-sort by final score if temporal decay was applied
            if temporal_enabled:
                search_results.sort(key=lambda x: x.score, reverse=True)
                search_results = search_results[:limit]
            
            logger.info(
                "search_completed",
                query=query[:50],
                results_count=len(search_results),
                temporal_decay=temporal_enabled
            )
            
            return search_results
            
        except Exception as e:
            logger.error("search_failed", query=query[:50], error=str(e))
            raise
    
    def _build_where_clause(self, filters: SearchFilters) -> Dict[str, Any]:
        """Build ChromaDB where clause from filters"""
        where = {}
        
        if filters.memory_type:
            where["memory_type"] = filters.memory_type
        
        if filters.source:
            where["source"] = filters.source
        
        if filters.project:
            where["project"] = filters.project
        
        if filters.min_importance is not None:
            where["importance"] = {"$gte": filters.min_importance}
        
        # Note: ChromaDB has limited filtering capabilities
        # Complex filters (tags, dates) may need post-processing
        
        return where if where else None
    
    def _reconstruct_memory(self, memory_id: str, content: str, metadata: Dict[str, Any]) -> Memory:
        """Reconstruct Memory object from ChromaDB data (V2.0 Schema)"""
        from src.models.memory import DomainType, MemoryType, IntentType, MemoryStatus, SourceType
        
        # Helper to safely get enum value
        def get_enum_value(enum_class, value, default):
            if not value:
                return default
            try:
                return enum_class(value)
            except (ValueError, KeyError):
                return default
        
        # Parse V2 metadata with backward compatibility for V1
        memory_metadata = MemoryMetadata(
            # Layer 1: Core Identity
            created_at=datetime.fromisoformat(metadata.get("created_at", metadata.get("timestamp", datetime.utcnow().isoformat()))),
            created_by=metadata.get("created_by", "user"),
            
            # Layer 2: Classification
            domain=get_enum_value(DomainType, metadata.get("domain"), DomainType.REFERENCE),
            category=metadata.get("category", "general"),
            memory_type=get_enum_value(MemoryType, metadata.get("memory_type"), MemoryType.CONVERSATION),
            subcategory=metadata.get("subcategory") or None,
            
            # Layer 3: Semantic
            intent=get_enum_value(IntentType, metadata.get("intent"), IntentType.REFERENCE),
            importance=metadata.get("importance", 5),
            urgency=metadata.get("urgency", 5),
            confidence=metadata.get("confidence", 0.7),
            tags=metadata.get("tags", "").split(",") if metadata.get("tags") else [],
            keywords=metadata.get("keywords", "").split(",") if metadata.get("keywords") else [],
            
            # Layer 4: Relationships
            status=get_enum_value(MemoryStatus, metadata.get("status"), MemoryStatus.NEW),
            parent_id=UUID(metadata["parent_id"]) if metadata.get("parent_id") else None,
            
            # Layer 5: Source
            source=get_enum_value(SourceType, metadata.get("source"), SourceType.USER_INPUT),
            source_reliability=metadata.get("source_reliability", 0.9),
            verified=metadata.get("verified", False),
            
            # Layer 6: Context
            project=metadata.get("project") or None,
            file_path=metadata.get("file_path") or None,
            session_id=UUID(metadata["session_id"]) if metadata.get("session_id") else None,
            
            # Layer 7: Temporal
            last_accessed=datetime.fromisoformat(metadata.get("last_accessed", datetime.utcnow().isoformat())),
            access_count=metadata.get("access_count", 0),
            
            # Layer 8: Quality
            version=metadata.get("version", 1),
            deprecated=metadata.get("deprecated", False),
        )
        
        # Create memory object
        memory = Memory(
            id=UUID(memory_id),
            content=content,
            metadata=memory_metadata
        )
        
        return memory
    
    async def get_memory(self, memory_id: UUID) -> Optional[Memory]:
        """
        Get a specific memory by ID
        
        Args:
            memory_id: Memory UUID
            
        Returns:
            Memory object or None if not found
        """
        self._initialize_client()
        
        try:
            result = await asyncio.to_thread(
                self._collection.get,
                ids=[str(memory_id)],
                include=["documents", "metadatas", "embeddings"]
            )
            
            if result and result['ids'] and len(result['ids']) > 0:
                memory = self._reconstruct_memory(
                    result['ids'][0],
                    result['documents'][0],
                    result['metadatas'][0]
                )
                memory.embedding = result['embeddings'][0] if result['embeddings'] else None
                
                return memory
            
            return None
            
        except Exception as e:
            logger.error("failed_to_get_memory", memory_id=str(memory_id), error=str(e))
            return None
    
    async def update_memory(self, memory_id: UUID, updates: Dict[str, Any]) -> bool:
        """
        Update a memory's metadata or content
        
        Args:
            memory_id: Memory UUID
            updates: Dictionary of fields to update
            
        Returns:
            True if successful, False otherwise
        """
        self._initialize_client()
        
        try:
            # Get existing memory
            memory = await self.get_memory(memory_id)
            if not memory:
                logger.warning("memory_not_found_for_update", memory_id=str(memory_id))
                return False
            
            # Update fields
            if "content" in updates:
                memory.content = updates["content"]
                # Regenerate embedding
                memory.embedding = await self._embedding_service.generate_embedding(memory.content)
            
            if "importance" in updates:
                memory.metadata.importance = updates["importance"]
            
            if "tags" in updates:
                memory.metadata.tags = updates["tags"]
            
            # Update temporal fields
            if "last_accessed" in updates:
                memory.metadata.last_accessed = updates["last_accessed"]
            
            if "access_count" in updates:
                memory.metadata.access_count = updates["access_count"]
            
            # Delete old and add updated
            await self.delete_memory(memory_id)
            await self.add_memory(memory)
            
            logger.info("memory_updated", memory_id=str(memory_id))
            return True
            
        except Exception as e:
            logger.error("failed_to_update_memory", memory_id=str(memory_id), error=str(e))
            return False
    
    async def update_memory_access(self, memory: Memory) -> bool:
        """
        Update memory access tracking (lightweight update for temporal decay)
        
        Args:
            memory: Memory object with updated access metadata
            
        Returns:
            True if successful, False otherwise
        """
        return await self.update_memory(
            memory.id,
            {
                "last_accessed": memory.metadata.last_accessed,
                "access_count": memory.metadata.access_count
            }
        )
    
    async def delete_memory(self, memory_id: UUID) -> bool:
        """
        Delete a memory from the vector store
        
        Args:
            memory_id: Memory UUID
            
        Returns:
            True if successful, False otherwise
        """
        self._initialize_client()
        
        try:
            await asyncio.to_thread(
                self._collection.delete,
                ids=[str(memory_id)]
            )
            
            logger.info("memory_deleted", memory_id=str(memory_id))
            return True
            
        except Exception as e:
            logger.error("failed_to_delete_memory", memory_id=str(memory_id), error=str(e))
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get vector store statistics
        
        Returns:
            Dictionary with statistics
        """
        self._initialize_client()
        
        try:
            count = await asyncio.to_thread(self._collection.count)
            
            return {
                "collection_name": self.collection_name,
                "total_memories": count,
                "persist_directory": self.persist_directory,
                "distance_metric": self.distance_metric,
                "embedding_dimension": self._embedding_service.get_embedding_dimension()
            }
            
        except Exception as e:
            logger.error("failed_to_get_stats", error=str(e))
            return {}
    
    async def get_all(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: Optional[SearchFilters] = None
    ) -> List[Memory]:
        """
        Retrieve all memories without semantic search filtering
        
        This method bypasses semantic search and returns memories directly
        from ChromaDB. Useful for database inspection, debugging, or when
        you need a complete memory dump.
        
        Args:
            limit: Maximum number of memories to return
            offset: Number of memories to skip (for pagination)
            filters: Optional filters to apply
            
        Returns:
            List of Memory objects
        """
        self._initialize_client()
        
        try:
            # Build where clause from filters if provided
            where_clause = self._build_where_clause(filters) if filters else None
            
            # Get all IDs first to support pagination
            all_results = await asyncio.to_thread(
                self._collection.get,
                where=where_clause,
                include=["documents", "metadatas"]
            )
            
            if not all_results or not all_results['ids']:
                logger.info("no_memories_found")
                return []
            
            # Apply pagination
            total_count = len(all_results['ids'])
            start_idx = offset
            end_idx = min(offset + limit, total_count)
            
            if start_idx >= total_count:
                logger.info("offset_exceeds_total", offset=offset, total=total_count)
                return []
            
            # Slice results for pagination
            paginated_ids = all_results['ids'][start_idx:end_idx]
            paginated_docs = all_results['documents'][start_idx:end_idx]
            paginated_metadata = all_results['metadatas'][start_idx:end_idx]
            
            # Reconstruct memory objects
            memories = []
            for i, memory_id in enumerate(paginated_ids):
                memory = self._reconstruct_memory(
                    memory_id,
                    paginated_docs[i],
                    paginated_metadata[i]
                )
                memories.append(memory)
            
            logger.info(
                "retrieved_all_memories",
                count=len(memories),
                total=total_count,
                offset=offset,
                limit=limit
            )
            
            return memories
            
        except Exception as e:
            logger.error("failed_to_get_all_memories", error=str(e))
            raise
    
    async def clear(self) -> bool:
        """
        Clear all memories from the vector store
        
        WARNING: This deletes all data!
        
        Returns:
            True if successful
        """
        self._initialize_client()
        
        try:
            # Delete collection and recreate
            await asyncio.to_thread(self._client.delete_collection, self.collection_name)
            self._collection = await asyncio.to_thread(
                self._client.create_collection,
                name=self.collection_name,
                metadata={"hnsw:space": self.distance_metric}
            )
            
            logger.warning("vector_store_cleared", collection=self.collection_name)
            return True
            
        except Exception as e:
            logger.error("failed_to_clear_vector_store", error=str(e))
            return False
    
    def __repr__(self) -> str:
        return f"VectorStore(collection={self.collection_name}, persist_dir={self.persist_directory})"


# Global vector store instance
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """
    Get global vector store instance
    
    Returns:
        VectorStore: Global vector store
    """
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


def reset_vector_store():
    """Reset global vector store (useful for testing)"""
    global _vector_store
    _vector_store = None

# Made with Bob
