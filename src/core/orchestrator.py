"""
Hybrid Query Orchestrator - Routes queries between Vector and Graph stores

This is the central intelligence layer that:
1. Analyzes queries to determine optimal routing strategy
2. Executes searches across both databases
3. Merges and ranks results with weighted scoring
4. Provides unified API for memory operations
"""

import asyncio
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID, uuid4
from datetime import datetime

from src.models.memory import Memory, MemoryType, MemoryMetadata
from src.models.entity import Entity, EntityType, Relationship, RelationshipType
from src.models.query import QueryMode, QueryPlan, SearchResult, SearchFilters
from src.core.vector_store import VectorStore, get_vector_store
from src.core.graph_store import GraphStore, get_graph_store
from src.core.embeddings import EmbeddingService, get_embedding_service
from src.utils.logger import get_logger
from src.utils.validators import validate_memory_content, validate_uuid

logger = get_logger(__name__)


class MemoryOrchestrator:
    """
    Orchestrates memory operations across vector and graph databases
    
    This class provides the main API for:
    - Adding memories (stores in both databases)
    - Searching memories (hybrid search across both)
    - Managing entities and relationships
    - Retrieving context for sessions/tasks
    """
    
    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        graph_store: Optional[GraphStore] = None,
        embedding_service: Optional[EmbeddingService] = None
    ):
        """
        Initialize orchestrator with database connections
        
        Args:
            vector_store: ChromaDB vector store instance
            graph_store: Kuzu graph store instance
            embedding_service: Embedding generation service
        """
        self.vector_store = vector_store or get_vector_store()
        self.graph_store = graph_store or get_graph_store()
        self.embedding_service = embedding_service or get_embedding_service()
        self.logger = get_logger(self.__class__.__name__)
        
        self.logger.info("Memory orchestrator initialized")
    
    async def add_memory(
        self,
        content: str,
        memory_type: str = "conversation",
        importance: int = 5,
        tags: Optional[List[str]] = None,
        entities: Optional[List[Dict[str, str]]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Memory:
        """
        Add a new memory to both vector and graph stores
        
        This is the primary method for storing memories. It:
        1. Validates input
        2. Generates embedding
        3. Creates Memory object
        4. Stores in vector database
        5. Creates graph nodes and relationships
        
        Args:
            content: The memory content to store
            memory_type: Type of memory (conversation, fact, insight, code, decision)
            importance: Importance score 1-10
            tags: Optional list of tags
            entities: Optional list of entities to link ({"name": "X", "type": "Y"})
            metadata: Additional metadata
            
        Returns:
            Memory: The created memory object
            
        Raises:
            ValueError: If validation fails
        """
        # Validate input
        validate_memory_content(content, min_length=1, max_length=10000)
        if importance < 1 or importance > 10:
            raise ValueError(f"Importance must be 1-10, got {importance}")
        
        self.logger.info(
            "Adding memory",
            memory_type=memory_type,
            importance=importance,
            content_length=len(content),
            num_tags=len(tags) if tags else 0,
            num_entities=len(entities) if entities else 0
        )
        
        try:
            # Generate embedding
            embedding = await self.embedding_service.generate_embedding(content)
            
            # Create memory object with proper metadata structure
            memory_metadata = MemoryMetadata(
                memory_type=MemoryType(memory_type),
                importance=importance,
                tags=tags or []
            )
            
            # Add custom metadata if provided
            if metadata:
                for key, value in metadata.items():
                    memory_metadata.custom[key] = value
            
            memory = Memory(
                content=content,
                metadata=memory_metadata,
                embedding=embedding
            )
            
            # Store in vector database
            await self.vector_store.add_memory(memory)
            self.logger.debug(f"Memory stored in vector DB: {memory.id}")
            
            # Create graph node for memory
            memory_entity = Entity(
                name=f"memory_{memory.id}",
                type=EntityType.CUSTOM,
                properties={
                    "content": content[:200],  # Store truncated content
                    "memory_type": memory_type,
                    "importance": importance,
                    "timestamp": memory.metadata.timestamp,  # Pass datetime object directly
                    "entity_subtype": "memory"
                }
            )
            await self.graph_store.create_entity(memory_entity)
            self.logger.debug(f"Memory node created in graph: {memory_entity.id}")
            
            # Create entity nodes and relationships if provided
            if entities:
                for entity_data in entities:
                    # Parse entity type
                    entity_type_str = entity_data.get("type", "concept")
                    try:
                        entity_type = EntityType(entity_type_str)
                    except ValueError:
                        entity_type = EntityType.CUSTOM
                    
                    # Get properties safely
                    props = entity_data.get("properties", {})
                    if not isinstance(props, dict):
                        props = {}
                    
                    entity = Entity(
                        name=entity_data["name"],
                        type=entity_type,
                        properties=props
                    )
                    
                    # Create or update entity
                    await self.graph_store.create_entity(entity)
                    
                    # Create relationship: Memory -> Entity
                    relationship = Relationship(
                        from_entity_id=memory_entity.id,
                        to_entity_id=entity.id,
                        relationship_type=RelationshipType.RELATES_TO,
                        properties={"created_at": datetime.utcnow()}  # Pass datetime object directly
                    )
                    await self.graph_store.create_relationship(relationship)
                    
                    self.logger.debug(
                        f"Linked memory to entity",
                        entity_name=entity.name,
                        entity_type=entity.type
                    )
            
            self.logger.info(f"Memory added successfully: {memory.id}")
            return memory
            
        except Exception as e:
            self.logger.error(f"Failed to add memory: {e}", exc_info=True)
            raise
    
    async def search_memories(
        self,
        query: str,
        mode: QueryMode = QueryMode.HYBRID,
        limit: int = 10,
        filters: Optional[SearchFilters] = None,
        min_similarity: float = 0.3,
        # NEW: Conversation context parameters
        include_conversation: bool = True,
        include_stored: bool = True,
        session_id: Optional[UUID] = None,
        return_debug: bool = False
    ) -> List[SearchResult]:
        """
        Search memories using semantic, structured, and/or conversation context
        
        This implements enhanced hybrid search with conversation awareness:
        - SEMANTIC: Vector similarity search only
        - STRUCTURED: Graph traversal only
        - HYBRID: Combined search with weighted scoring
        - CONVERSATION: Recent session messages (when session_id provided)
        
        Args:
            query: Search query string
            mode: Search mode (semantic, structured, hybrid)
            limit: Maximum number of results
            filters: Optional search filters
            min_similarity: Minimum similarity threshold (0.0-1.0)
            include_conversation: Include conversation context in search
            include_stored: Include stored memories in search
            session_id: Session UUID for conversation context
            return_debug: Return debug statistics with results
            
        Returns:
            List[SearchResult]: Ranked search results
        """
        validate_memory_content(query, min_length=1, max_length=1000)
        
        # Extract conversation settings from filters if provided
        if filters:
            include_conversation = filters.include_conversation if filters.include_conversation is not None else include_conversation
            include_stored = filters.include_stored if filters.include_stored is not None else include_stored
            session_id = filters.session_id if filters.session_id else session_id
        
        self.logger.info(
            "Searching memories (enhanced)",
            query=query[:100],
            mode=mode.value,
            limit=limit,
            include_conversation=include_conversation,
            include_stored=include_stored,
            has_session=session_id is not None
        )
        
        try:
            # Create query plan
            plan = self._create_query_plan(query, mode, limit, filters, min_similarity)
            
            # Execute searches based on flags
            results = []
            
            if include_stored:
                # Execute traditional search (semantic/structured/hybrid)
                if mode == QueryMode.SEMANTIC:
                    stored_results = await self._search_semantic(query, plan)
                elif mode == QueryMode.STRUCTURED:
                    stored_results = await self._search_structured(query, plan)
                else:  # HYBRID
                    stored_results = await self._search_hybrid(query, plan)
                results.extend(stored_results)
            
            if include_conversation and session_id:
                # Execute conversation context search
                conversation_results = await self._search_conversation(query, session_id, limit)
                results.extend(conversation_results)
            
            # Merge, normalize, and deduplicate results
            if include_conversation and include_stored and session_id:
                results = await self._merge_and_deduplicate(results, query, session_id is not None, mode.value)
            
            # Sort by score and limit
            results.sort(key=lambda r: r.score, reverse=True)
            results = results[:limit]
            
            self.logger.info(
                "Search completed (enhanced)",
                num_results=len(results),
                top_score=results[0].score if results else 0.0
            )
            
            return results
            
        except Exception as e:
            self.logger.error(f"Search failed: {e}", exc_info=True)
            raise
    
    def _create_query_plan(
        self,
        query: str,
        mode: QueryMode,
        limit: int,
        filters: Optional[SearchFilters],
        min_similarity: float
    ) -> QueryPlan:
        """
        Create execution plan for query
        
        Analyzes query to determine optimal weights and parameters
        """
        # Determine weights based on query characteristics
        if mode == QueryMode.SEMANTIC:
            vector_weight, graph_weight = 1.0, 0.0
        elif mode == QueryMode.STRUCTURED:
            vector_weight, graph_weight = 0.0, 1.0
        else:  # HYBRID
            # Analyze query to determine weights
            # Questions/concepts favor semantic, facts favor structured
            has_question = any(q in query.lower() for q in ["what", "how", "why", "when", "where", "who"])
            has_specific = any(s in query.lower() for s in ["named", "called", "id", "uuid"])
            
            if has_specific:
                vector_weight, graph_weight = 0.3, 0.7
            elif has_question:
                vector_weight, graph_weight = 0.7, 0.3
            else:
                vector_weight, graph_weight = 0.5, 0.5
        
        return QueryPlan(
            mode=mode,
            vector_weight=vector_weight,
            graph_weight=graph_weight,
            limit=limit,
            min_similarity=min_similarity,
            memory_types=[filters.memory_type] if filters and filters.memory_type else None,
            tags=filters.tags if filters else None,
            min_importance=filters.min_importance if filters else None,
            date_range={
                "start": filters.start_date if filters.start_date else datetime.min,
                "end": filters.end_date if filters.end_date else datetime.max
            } if filters and (filters.start_date or filters.end_date) else None
        )
    
    async def _search_semantic(
        self,
        query: str,
        plan: QueryPlan
    ) -> List[SearchResult]:
        """Execute semantic search via vector store"""
        # Build metadata filters
        metadata_filter = {}
        if plan.memory_types:
            metadata_filter["memory_type"] = plan.memory_types
        if plan.tags:
            metadata_filter["tags"] = {"$in": plan.tags}
        if plan.min_importance:
            metadata_filter["importance"] = {"$gte": plan.min_importance}
        
        # Search vector store - returns List[SearchResult]
        results = await self.vector_store.search(
            query=query,
            limit=plan.limit * 2  # Get more for filtering
        )
        
        # Filter by minimum similarity
        filtered_results = [
            result for result in results
            if result.score >= plan.min_similarity
        ]
        
        return filtered_results
    
    async def _search_structured(
        self,
        query: str,
        plan: QueryPlan
    ) -> List[SearchResult]:
        """Execute structured search via graph store"""
        # Build Cypher query based on filters
        cypher_parts = ["MATCH (m:Entity {type: 'memory'})"]
        where_clauses = []
        
        if plan.memory_types:
            where_clauses.append(f"m.memory_type IN {plan.memory_types}")
        if plan.min_importance:
            where_clauses.append(f"m.importance >= {plan.min_importance}")
        
        if where_clauses:
            cypher_parts.append("WHERE " + " AND ".join(where_clauses))
        
        cypher_parts.append(f"RETURN m LIMIT {plan.limit}")
        cypher_query = " ".join(cypher_parts)
        
        # Execute query
        graph_results = await self.graph_store.execute_query(cypher_query)
        
        # Convert to SearchResult objects
        # Note: Graph results don't have similarity scores, so we use importance
        results = []
        for row in graph_results:
            entity = row.get("m")
            if entity:
                # Reconstruct memory from graph data
                # In production, we'd fetch full memory from vector store
                score = entity.properties.get("importance", 5) / 10.0
                
                # Create minimal memory object
                memory_type_str = entity.properties.get("memory_type", "conversation")
                try:
                    mem_type = MemoryType(memory_type_str)
                except ValueError:
                    mem_type = MemoryType.CONVERSATION
                
                memory_metadata = MemoryMetadata(
                    memory_type=mem_type,
                    importance=entity.properties.get("importance", 5)
                )
                
                memory = Memory(
                    content=entity.properties.get("content", ""),
                    metadata=memory_metadata
                )
                
                results.append(SearchResult(
                    memory=memory,
                    score=score,
                    source="graph",
                    vector_score=None,
                    graph_score=score
                ))
        
        return results
    
    async def _search_hybrid(
        self,
        query: str,
        plan: QueryPlan
    ) -> List[SearchResult]:
        """
        Execute hybrid search combining vector and graph results
        
        This is the most powerful search mode:
        1. Run semantic and structured searches in parallel
        2. Merge results by memory ID
        3. Calculate weighted scores
        4. Deduplicate and rank
        """
        # Execute both searches in parallel
        semantic_task = self._search_semantic(query, plan)
        structured_task = self._search_structured(query, plan)
        
        semantic_results, structured_results = await asyncio.gather(
            semantic_task,
            structured_task,
            return_exceptions=True
        )
        
        # Handle exceptions and ensure we have lists
        if isinstance(semantic_results, Exception):
            self.logger.warning(f"Semantic search failed: {semantic_results}")
            semantic_results = []
        elif not isinstance(semantic_results, list):
            semantic_results = []
            
        if isinstance(structured_results, Exception):
            self.logger.warning(f"Structured search failed: {structured_results}")
            structured_results = []
        elif not isinstance(structured_results, list):
            structured_results = []
        
        # Merge results by memory ID
        merged: Dict[UUID, SearchResult] = {}
        
        # Add semantic results
        for result in semantic_results:
            merged[result.memory.id] = result
        
        # Merge with structured results
        for result in structured_results:
            memory_id = result.memory.id
            if memory_id in merged:
                # Combine scores with weights
                existing = merged[memory_id]
                combined_score = (
                    (existing.vector_score or 0) * plan.vector_weight +
                    (result.graph_score or 0) * plan.graph_weight
                )
                
                # Update result
                existing.score = combined_score
                existing.source = "hybrid"
                existing.graph_score = result.graph_score
            else:
                # Add new result with weighted score
                result.score = (result.graph_score or 0) * plan.graph_weight
                result.source = "hybrid"
                merged[memory_id] = result
        
        return list(merged.values())
    
    async def _search_conversation(
        self,
        query: str,
        session_id: UUID,
        limit: int
    ) -> List[SearchResult]:
        """
        Search conversation context for relevant messages
        
        Args:
            query: Search query
            session_id: Session UUID
            limit: Maximum results
            
        Returns:
            List of SearchResult objects from conversation
        """
        from src.core.conversation_context import get_conversation_searcher
        from src.models.conversation import SearchCandidate
        
        try:
            searcher = get_conversation_searcher()
            candidates = await searcher.collect_candidates(query, session_id, limit)
            
            # Convert SearchCandidates to SearchResults
            results = []
            for candidate in candidates:
                # Create a minimal Memory object for the result
                from src.models.memory import Memory, MemoryMetadata, MemoryType
                
                memory_metadata = MemoryMetadata(
                    memory_type=MemoryType.CONVERSATION,
                    importance=5,
                    source=candidate.metadata.get("role", "user"),
                    session_id=session_id
                )
                
                memory = Memory(
                    id=candidate.memory_id if candidate.memory_id else uuid4(),
                    content=candidate.text,
                    metadata=memory_metadata
                )
                
                result = SearchResult(
                    memory=memory,
                    score=candidate.score,
                    source="conversation",
                    vector_score=None,
                    graph_score=None
                )
                
                results.append(result)
            
            self.logger.debug(
                f"Conversation search completed",
                session_id=str(session_id),
                count=len(results)
            )
            
            return results
            
        except Exception as e:
            self.logger.error(f"Conversation search failed: {e}", exc_info=True)
            return []
    
    async def _merge_and_deduplicate(
        self,
        results: List[SearchResult],
        query: str,
        has_session: bool,
        mode: str
    ) -> List[SearchResult]:
        """
        Merge results from multiple sources and remove duplicates
        
        Args:
            results: Combined results from all sources
            query: Original search query
            has_session: Whether session context was used
            mode: Search mode
            
        Returns:
            Deduplicated and normalized results
        """
        from src.core.scoring import ScoreNormalizer
        from src.core.deduplication import get_deduplicator
        from src.models.conversation import SearchCandidate
        
        try:
            # Convert SearchResults to SearchCandidates for processing
            candidates = []
            for result in results:
                candidate = SearchCandidate(
                    text=result.memory.content,
                    score=result.score,
                    source=result.source,
                    metadata={
                        "memory_id": str(result.memory.id),
                        "timestamp": result.memory.metadata.timestamp.isoformat(),
                        "memory_type": result.memory.metadata.memory_type.value
                    },
                    embedding=result.memory.embedding,
                    memory_id=result.memory.id
                )
                candidates.append(candidate)
            
            # Calculate adaptive weights
            weights = ScoreNormalizer.adaptive_weights(query, has_session, mode)
            
            # Normalize scores
            candidates = ScoreNormalizer.normalize_scores(candidates, weights)
            
            # Deduplicate
            deduplicator = get_deduplicator(threshold=0.95)
            candidates = await deduplicator.deduplicate(candidates)
            
            # Convert back to SearchResults
            final_results = []
            for candidate in candidates:
                # Find original result to preserve full memory object
                original = next(
                    (r for r in results if r.memory.id == candidate.memory_id),
                    None
                )
                
                if original:
                    # Update score with normalized value
                    original.score = candidate.score
                    # Update source if merged
                    if "sources" in candidate.metadata:
                        original.source = "hybrid"
                    final_results.append(original)
            
            self.logger.debug(
                "Merge and deduplication completed",
                original_count=len(results),
                final_count=len(final_results),
                weights=weights
            )
            
            return final_results
            
        except Exception as e:
            self.logger.error(f"Merge and deduplication failed: {e}", exc_info=True)
            # Return original results if processing fails
            return results
    
    async def get_context(
        self,
        session_id: Optional[UUID] = None,
        depth: int = 2,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Retrieve full context for a session or task
        
        This assembles a comprehensive context by:
        1. Finding all memories in the session
        2. Traversing relationships to depth N
        3. Collecting related entities and facts
        
        Args:
            session_id: Optional session UUID to filter by
            depth: Relationship traversal depth (1-5)
            limit: Maximum memories to retrieve
            
        Returns:
            Dict containing memories, entities, and relationships
        """
        self.logger.info(
            "Retrieving context",
            session_id=str(session_id) if session_id else None,
            depth=depth,
            limit=limit
        )
        
        try:
            context = {
                "memories": [],
                "entities": [],
                "relationships": [],
                "stats": {}
            }
            
            # Build query for session memories
            if session_id:
                validate_uuid(str(session_id))
                cypher = f"""
                MATCH (m:Entity {{type: 'memory'}})
                WHERE m.session_id = '{session_id}'
                RETURN m
                LIMIT {limit}
                """
            else:
                # FIX: Entity schema has 'created_at' property, not 'timestamp'
                # Must match the schema defined in graph_store.py
                cypher = f"""
                MATCH (m:Entity {{type: 'memory'}})
                RETURN m
                ORDER BY m.created_at DESC
                LIMIT {limit}
                """
            
            # Get memories from graph
            results = await self.graph_store.execute_query(cypher)
            
            memory_ids = []
            for row in results:
                entity = row.get("m")
                if entity:
                    memory_ids.append(entity.id)
                    context["entities"].append({
                        "id": str(entity.id),
                        "name": entity.name,
                        "type": entity.type,
                        "properties": entity.properties
                    })
            
            # Get full memory content from vector store
            for memory_id in memory_ids:
                try:
                    memory = await self.vector_store.get_memory(memory_id)
                    if memory:
                        context["memories"].append(memory.to_dict())
                except Exception as e:
                    self.logger.warning(f"Failed to fetch memory {memory_id}: {e}")
            
            # Traverse relationships to specified depth
            if memory_ids and depth > 0:
                for memory_id in memory_ids:
                    # Build Cypher query to find related entities
                    cypher = f"""
                    MATCH (m:Entity {{id: '{memory_id}'}})-[*1..{depth}]-(related:Entity)
                    WHERE related.id <> '{memory_id}'
                    RETURN DISTINCT related
                    LIMIT 50
                    """
                    try:
                        related_results = await self.graph_store.execute_query(cypher)
                        for row in related_results:
                            entity = row.get("related")
                            if entity and entity.id not in [e["id"] for e in context["entities"]]:
                                context["entities"].append({
                                    "id": str(entity.id),
                                    "name": entity.name,
                                    "type": entity.type,
                                    "properties": entity.properties
                                })
                    except Exception as e:
                        self.logger.warning(f"Failed to traverse relationships for {memory_id}: {e}")
            
            # Add stats
            context["stats"] = {
                "num_memories": len(context["memories"]),
                "num_entities": len(context["entities"]),
                "depth": depth,
                "session_id": str(session_id) if session_id else None
            }
            
            self.logger.info(
                "Context retrieved",
                num_memories=context["stats"]["num_memories"],
                num_entities=context["stats"]["num_entities"]
            )
            
            return context
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve context: {e}", exc_info=True)
            raise
    
    async def create_entity(
        self,
        name: str,
        entity_type: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> Entity:
        """
        Create a new entity in the knowledge graph
        
        Args:
            name: Entity name
            entity_type: Entity type (person, project, file, concept, etc.)
            properties: Additional properties
            
        Returns:
            Entity: Created entity
        """
        # Parse entity type
        try:
            parsed_type = EntityType(entity_type)
        except ValueError:
            parsed_type = EntityType.CUSTOM
        
        entity = Entity(
            name=name,
            type=parsed_type,
            properties=properties or {}
        )
        
        await self.graph_store.create_entity(entity)
        self.logger.info(f"Entity created: {name} ({entity_type})")
        
        return entity
    
    async def create_relationship(
        self,
        from_entity_id: UUID,
        to_entity_id: UUID,
        relationship_type: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> Relationship:
        """
        Create a relationship between entities
        
        Args:
            from_entity_id: Source entity UUID
            to_entity_id: Target entity UUID
            relationship_type: Type of relationship
            properties: Additional properties
            
        Returns:
            Relationship: Created relationship
        """
        # Parse relationship type
        try:
            parsed_rel_type = RelationshipType(relationship_type)
        except ValueError:
            parsed_rel_type = RelationshipType.CUSTOM
        
        relationship = Relationship(
            from_entity_id=from_entity_id,
            to_entity_id=to_entity_id,
            relationship_type=parsed_rel_type,
            properties=properties or {}
        )
        
        await self.graph_store.create_relationship(relationship)
        self.logger.info(
            f"Relationship created: {relationship_type}",
            from_id=str(from_entity_id),
            to_id=str(to_entity_id)
        )
        
        return relationship
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics from both databases
        
        Returns:
            Dict with stats from vector and graph stores
        """
        vector_stats = await self.vector_store.get_stats()
        graph_stats = await self.graph_store.get_stats()
        
        return {
            "vector_store": vector_stats,
            "graph_store": graph_stats,
            "orchestrator": {
                "status": "operational",
                "timestamp": datetime.utcnow().isoformat()
            }
        }
    
    async def close(self):
        """Close all database connections"""
        self.logger.info("Closing orchestrator connections")
        # Connections are managed by singleton instances
        # No explicit close needed for ChromaDB/Kuzu in current implementation


# Global singleton instance
_orchestrator: Optional[MemoryOrchestrator] = None


def get_orchestrator() -> MemoryOrchestrator:
    """
    Get or create global orchestrator instance
    
    Returns:
        MemoryOrchestrator: Singleton orchestrator instance
    """
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = MemoryOrchestrator()
    return _orchestrator


# Made with Bob