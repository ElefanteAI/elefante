"""
Hybrid Query Orchestrator - Routes queries between Vector and Graph stores

This is the central intelligence layer that:
1. Analyzes queries to determine optimal routing strategy
2. Executes searches across both databases
3. Merges and ranks results with weighted scoring
4. Provides unified API for memory operations
"""

import asyncio
import re
import json
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID, uuid4
from datetime import datetime

from src.models.memory import (
    Memory, MemoryType, MemoryMetadata, MemoryStatus,
    DomainType, IntentType, SourceType
)
from src.models.entity import Entity, EntityType, Relationship, RelationshipType
from src.models.query import QueryMode, QueryPlan, SearchResult, SearchFilters
from src.core.vector_store import VectorStore, get_vector_store
from src.core.graph_store import GraphStore, get_graph_store
from src.core.embeddings import EmbeddingService, get_embedding_service
from src.core.llm import get_llm_service
from src.utils.logger import get_logger
from src.utils.config import get_config
from src.utils.validators import validate_memory_content, validate_uuid
from src.models.metadata import StandardizedMetadata, CoreMetadata, ContextMetadata, SystemMetadata, MemoryType as StdMemoryType
from src.core.metadata_store import get_metadata_store

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
        self.llm_service = get_llm_service()
        self.config = get_config()
        self.logger = get_logger(self.__class__.__name__)
        self.metadata_store = get_metadata_store()
        
        # Initialize metadata store
        asyncio.create_task(self.metadata_store.initialize())
        
        self.logger.info("Memory orchestrator initialized")
    
    async def add_memory(
        self,
        content: str,
        memory_type: str = "conversation",
        tags: List[str] = None,
        entities: List[Dict[str, str]] = None,
        metadata: Dict[str, Any] = None,
        importance: int = 1
    ) -> Optional[Memory]:
        """
        Add a new memory via the Authoritative 5-Step Pipeline.
        
        Pipeline:
        1. PARSE & CLASSIFY: Validate input and extract Layer/Sublayer from metadata.
        2. INTEGRITY: Check for duplicates (REDUNDANT) and contradictions (CONTRADICTORY).
        3. WRITE: Construct Memory object with V2 metadata (Layers).
        4. REINFORCE: Initialize plasticity (access_count=1) and decay signals.
        5. GRAPH: Create Entity nodes and Relationships.
        """
        from src.core.graph_executor import GraphExecutor
        if not hasattr(self, 'graph_executor'):
            self.graph_executor = GraphExecutor(self.graph_store)

        # ==================================================================================
        # STEP 1: PARSE & CLASSIFY
        # ==================================================================================
        validate_memory_content(content)
        
        if metadata is None:
            metadata = {}
            
        # Extract Authoritative Classification (Layer/Sublayer)
        # We prefer the classification provided by the Agent (via metadata)
        layer = metadata.get("layer")
        sublayer = metadata.get("sublayer")
        
        # If Agent failed to classify, we mark it but don't block (system resilience)
        if not layer or not sublayer:
             self.logger.warning("Memory missing explicit Layer/Sublayer classification. Using defaults.")
             if not layer: layer = "world"
             if not sublayer: sublayer = "fact"

        # 1b. Cognitive Analysis (Optional Enrichment)
        # We still use the LLM to get a Title and deeper intent, but we don't let it override the Agent's layer
        try:
            analysis = await self.llm_service.analyze_memory(content)
            
            # Handle IGNORE action
            if analysis.get("action") == "IGNORE":
                self.logger.info(f"Memory ignored by Intelligence Pipeline: {content[:50]}...")
                return None
            
            title = analysis.get("title", f"Memory {datetime.utcnow().isoformat()}")
            
            # Update metadata with cognitive context
            metadata["title"] = title
            metadata["intent"] = analysis.get("intent")
            metadata["emotional_context"] = analysis.get("emotional_context")
            metadata["strategic_insight"] = analysis.get("strategic_insight")
            
        except Exception as e:
            self.logger.warning(f"Intelligence Pipeline enrichment failed: {e}. Proceeding with raw memory.")
            title = f"memory_{uuid4()}"
            analysis = {}

        # ==================================================================================
        # STEP 2: INTEGRITY (Duplicate & Contradiction Check)
        # ==================================================================================
        embedding = await self.embedding_service.generate_embedding(content)
        
        similar_memories = await self.vector_store.search(
            query=content,
            limit=3, 
            min_similarity=0.65  # Threshold
        )
        
        status = MemoryStatus.NEW
        related_id = None
        contradiction_details = None
        
        if similar_memories:
            best_match = similar_memories[0]
            
            # Check for redundancy
            if best_match.score >= 0.95:
                status = MemoryStatus.REDUNDANT
                related_id = best_match.memory.id
                self.logger.info(f"Found redundant memory: {best_match.memory.id} (Score: {best_match.score})")
            
            # Check for contradiction (High similarity but conflicting content)
            elif best_match.score >= 0.75:
                is_contradiction = self._detect_contradiction(content, best_match.memory.content)
                if is_contradiction:
                    status = MemoryStatus.CONTRADICTORY
                    related_id = best_match.memory.id
                    contradiction_details = {
                        "conflicting_memory_id": str(best_match.memory.id),
                        "conflicting_content": best_match.memory.content[:200],
                        "similarity": best_match.score
                    }
                    self.logger.warning(f"CONTRADICTORY memory detected vs {best_match.memory.id}")
                else:
                    status = MemoryStatus.RELATED
                    related_id = best_match.memory.id

        # ==================================================================================
        # STEP 3: WRITE (Construct Memory Object)
        # ==================================================================================
        try:
            # Map common V1 "custom" fields to V2 structured fields
            domain = metadata.get("domain", "reference")
            category = metadata.get("category", tags[0] if tags else "general")
            confidence = metadata.get("confidence", 0.7)
            source = metadata.get("source", "user_input")
            
            custom_metadata = {
                k: v for k, v in metadata.items()
                if k not in ["domain", "category", "intent", "confidence", "source", "layer", "sublayer"]
            }
            
            # Create V2 Metadata
            memory_metadata = MemoryMetadata(
                memory_type=MemoryType(memory_type),
                importance=importance,
                status=status,
                tags=tags or [],
                domain=DomainType(domain) if domain else DomainType.REFERENCE,
                category=category,
                # Enforce Layer/Sublayer
                layer=layer,
                sublayer=sublayer,
                intent=IntentType.REFERENCE, # Default, refined by analysis if avail
                confidence=confidence,
                source=SourceType(source),
                custom_metadata=custom_metadata,
                # ==================================================================================
                # STEP 4: REINFORCE (Plasticity & Decay)
                # ==================================================================================
                access_count=1,          # Initialize 'used once' (creation counts as use)
                last_accessed=datetime.utcnow(),
                decay_rate=0.01          # Standard Plasticity
            )
            
            memory = Memory(
                content=content,
                metadata=memory_metadata,
                embedding=embedding
            )
            
            # Persist to Vector DB
            await self.vector_store.add_memory(memory)
            
            # ==================================================================================
            # STEP 5: GRAPH LINKS (Entities & Relationships)
            # ==================================================================================
            
            # 5a. Create Memory Node
            entity_name = title if title and "Memory" not in title else f"memory_{memory.id}"
            
            memory_entity = Entity(
                id=memory.id,
                name=entity_name,
                type=EntityType.MEMORY,
                description=analysis.get("summary", content[:200]),
                properties={
                    "content": content[:200],
                    "layer": layer,
                    "sublayer": sublayer,
                    "importance": importance,
                    "status": status.value,
                    "timestamp": memory.metadata.created_at
                }
            )
            await self.graph_store.create_entity(memory_entity)
            
            # 5b. Link to Contradiction/Redundancy
            if related_id:
                rel_type = RelationshipType.RELATES_TO
                props = {"similarity": similar_memories[0].score}
                
                if status == MemoryStatus.REDUNDANT:
                    rel_type = RelationshipType.SIMILAR_TO
                elif status == MemoryStatus.CONTRADICTORY:
                    rel_type = RelationshipType.CONTRADICTS
                    props["resolved"] = False
                
                await self.graph_store.create_relationship(Relationship(
                    from_entity_id=memory.id,
                    to_entity_id=related_id,
                    relationship_type=rel_type,
                    properties=props
                ))
            
            # 5c. Link to Provided Entities
            if entities:
                for entity_data in entities:
                    ent_name = entity_data.get("name")
                    ent_type = entity_data.get("type", "concept")
                    
                    if ent_name:
                         # Create/Get Entity
                        linked_entity = Entity(
                            name=ent_name,
                            type=EntityType(ent_type) if ent_type in EntityType.__members__ else EntityType.CONCEPT,
                            properties={}
                        )
                        await self.graph_store.create_or_get_entity(linked_entity)
                        
                        # Link Memory -> Entity
                        await self.graph_store.create_relationship(Relationship(
                            from_entity_id=memory.id,
                            to_entity_id=linked_entity.id,
                            relationship_type=RelationshipType.RELATES_TO
                        ))
            
            if memory.metadata.session_id:
                session_id = str(memory.metadata.session_id)
                now_iso = datetime.utcnow().isoformat()
                
                # Use MERGE to create or update Session entity with stats
                session_cypher = f"""
                MERGE (s:Entity {{id: '{session_id}'}})
                ON CREATE SET 
                    s.name = 'Session {session_id[:8]}',
                    s.type = '{EntityType.SESSION.value}',
                    s.created_at = '{now_iso}',
                    s.last_active = '{now_iso}',
                    s.interaction_count = 1,
                    s.source = 'mcp'
                ON MATCH SET 
                    s.last_active = '{now_iso}',
                    s.interaction_count = s.interaction_count + 1
                RETURN s
                """
                try:
                    # We execute raw cypher here because create_entity doesn't support MERGE/ON MATCH yet
                    await self.graph_store.execute_query(session_cypher)
                    
                    # Link Memory -> Session (CREATED_IN)
                    session_rel = Relationship(
                        from_entity_id=memory_entity.id,
                        to_entity_id=UUID(session_id),
                        relationship_type=RelationshipType.CREATED_IN,
                        properties={"created_at": datetime.utcnow()}
                    )
                    await self.graph_store.create_relationship(session_rel)
                    self.logger.debug(f"Linked memory {memory.id} to Session {session_id}")
                except Exception as e:
                    self.logger.warning(f"Failed to update Session entity: {e}") 

            self.logger.info(f"Memory stored successfully: {memory.id} [{layer}/{sublayer}]")
            return memory
            
        except Exception as e:
            self.logger.error(f"Failed to store memory: {e}", exc_info=True)
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
        return_debug: bool = False,
        apply_temporal_decay: bool = True
    ) -> List[SearchResult]:
        """
        Search memories using semantic, structured, and/or conversation context with temporal decay
        
        This implements enhanced hybrid search with conversation awareness and adaptive memory strength:
        - SEMANTIC: Vector similarity search only
        - STRUCTURED: Graph traversal only
        - HYBRID: Combined search with weighted scoring
        - CONVERSATION: Recent session messages (when session_id provided)
        - TEMPORAL DECAY: Adaptive memory strength based on recency and access patterns
        
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
            apply_temporal_decay: Apply temporal strength scoring (default: True)
            
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
                # Execute traditional search (semantic/structured/hybrid) with temporal decay
                if mode == QueryMode.SEMANTIC:
                    stored_results = await self._search_semantic(query, plan, apply_temporal_decay)
                elif mode == QueryMode.STRUCTURED:
                    stored_results = await self._search_structured(query, plan, apply_temporal_decay)
                else:  # HYBRID
                    stored_results = await self._search_hybrid(query, plan, apply_temporal_decay)
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
        plan: QueryPlan,
        apply_temporal_decay: bool = True
    ) -> List[SearchResult]:
        """Execute semantic search via vector store with optional temporal decay"""
        # Build metadata filters
        metadata_filter = {}
        if plan.memory_types:
            metadata_filter["memory_type"] = plan.memory_types
        if plan.tags:
            metadata_filter["tags"] = {"$in": plan.tags}
        if plan.min_importance:
            metadata_filter["importance"] = {"$gte": plan.min_importance}
        
        # Search vector store with temporal decay - returns List[SearchResult]
        results = await self.vector_store.search(
            query=query,
            limit=plan.limit * 2,  # Get more for filtering
            apply_temporal_decay=apply_temporal_decay
        )
        
        # Filter by minimum similarity
        filtered_results = [
            result for result in results
            if result.score >= plan.min_similarity
        ]
        
        # Update access counts for retrieved memories
        if apply_temporal_decay:
            for result in filtered_results:
                await self.vector_store.update_memory_access(result.memory)
        
        return filtered_results
    
    async def _search_structured(
        self,
        query: str,
        plan: QueryPlan,
        apply_temporal_decay: bool = True
    ) -> List[SearchResult]:
        """Execute structured search via graph store with optional temporal decay"""
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
        
        # Apply Temporal Decay & Reinforcement (Read-Side Plasticity)
        if apply_temporal_decay:
            for result in results:
                # Calculate temporal score (even if just based on current time for graph results)
                current_time = datetime.utcnow()
                temporal_score = result.memory.calculate_relevance_score(current_time)
                
                # Blend with graph score (importance-based)
                # Config defaults: semantic=0.7, temporal=0.3
                # For graph, we treat importance as the "semantic" signal
                semantic_weight = 0.7 
                temporal_weight = 0.3
                
                # Re-calculate score
                result.score = (semantic_weight * result.score) + (temporal_weight * temporal_score)
                
                # REINFORCEMENT: Update access stats in Vector Store
                # This ensures graph-found memories also get "stronger"
                await self.vector_store.update_memory_access(result.memory)
                
            # Re-sort after decay application
            results.sort(key=lambda r: r.score, reverse=True)

        return results
    
    async def _search_hybrid(
        self,
        query: str,
        plan: QueryPlan,
        apply_temporal_decay: bool = True
    ) -> List[SearchResult]:
        """
        Execute hybrid search combining vector and graph results with temporal decay
        
        This is the most powerful search mode:
        1. Run semantic and structured searches in parallel
        2. Merge results by memory ID
        3. Calculate weighted scores (including temporal strength)
        4. Deduplicate and rank
        """
        # Execute both searches in parallel with temporal decay
        semantic_task = self._search_semantic(query, plan, apply_temporal_decay)
        structured_task = self._search_structured(query, plan, apply_temporal_decay)
        
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
                        "timestamp": result.memory.metadata.created_at.isoformat(),
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
            memory_ids = []
            if session_id:
                validate_uuid(str(session_id))
                # [FAST PATH] Get recent session memories from SQLite
                try:
                    fast_memories = await self.metadata_store.get_session_metadata(session_id, limit)
                    
                    for mem_id, std_meta, content in fast_memories:
                        # 1. Add to memories list
                        mem_dict = {
                            "id": mem_id,
                            "content": content,
                            "metadata": {
                                "memory_type": std_meta.core.memory_type.value,
                                "importance": std_meta.core.importance,
                                "timestamp": std_meta.system.created_at.isoformat(),
                                "tags": std_meta.core.tags,
                                **std_meta.custom
                            },
                            "embedding": None, 
                            "related_entities": [],
                            "similarity_score": None,
                            "relevance_score": None
                        }
                        context["memories"].append(mem_dict)
                        
                        # 2. Add to entities list (as memory nodes)
                        context["entities"].append({
                            "id": mem_id,
                            "name": f"memory_{mem_id}",
                            "type": "memory",
                            "properties": {
                                "content": content[:200],
                                "memory_type": std_meta.core.memory_type.value,
                                "importance": std_meta.core.importance,
                                "timestamp": std_meta.system.created_at.isoformat()
                            }
                        })
                        memory_ids.append(UUID(mem_id))
                        
                    self.logger.debug(f"Retrieved {len(fast_memories)} memories from Fast Store")
                    
                except Exception as e:
                    self.logger.warning(f"Fast memory retrieval failed: {e}")
                    # Fallback to graph query if needed, but for now we proceed
                    
            else:
                # AUTHORITATIVE: Use recursive traversal based on depth
                # Determine anchor points. If no session, rely on recency (flat) or relevant entities
                
                if session_id:
                     # Start from Session entity and traverse out
                     cypher = f"""
                     MATCH (s:Entity {{id: '{session_id}'}})-[r*1..{depth}]-(m:Entity)
                     WHERE m.type = 'memory' OR m.type = 'fact' OR m.type = 'person'
                     RETURN m, r
                     LIMIT {limit}
                     """
                else:
                    # Fallback to recent memories if no session anchor
                    # But we can still find their related entities up to depth
                    cypher = f"""
                    MATCH (m:Entity {{type: 'memory'}})
                    WITH m
                    ORDER BY m.created_at DESC
                    LIMIT 10
                    MATCH (m)-[r*1..{depth}]-(related:Entity)
                    RETURN m, related, r
                    LIMIT {limit}
                    """
            
                # Get memories/entities from graph
                try:
                    results = await self.graph_store.execute_query(cypher)
                    
                    for row in results:
                         # Handle Kuzu results which can be complex with var-length paths
                         # We'll flatten the results
                        
                        entities_to_process = []
                        if session_id:
                            # pattern: m, r (where r is list of rels, m is node)
                            # Actually Kuzu might return individual rows for paths
                            if "m" in row: entities_to_process.append(row["m"])
                        else:
                            if "m" in row: entities_to_process.append(row["m"])
                            if "related" in row: entities_to_process.append(row["related"])
                            
                        for entity in entities_to_process:
                            # Skip if already added
                            e_id = entity.get('id') if isinstance(entity, dict) else getattr(entity, 'id', None)
                            if not e_id or str(e_id) in [e["id"] for e in context["entities"]]:
                                continue
                                
                            # Safe property extraction
                            props = {}
                            if hasattr(entity, 'get') and entity.get('properties'):
                                try:
                                    props = json.loads(entity.get('properties'))
                                except:
                                    props = {}
                            elif isinstance(entity, dict) and 'properties' in entity and isinstance(entity['properties'], str):
                                try:
                                    props = json.loads(entity['properties'])
                                except:
                                    pass
                            
                            # Add to context
                            context["entities"].append({
                                "id": str(e_id),
                                "name": entity.get('name'),
                                "type": entity.get('type'),
                                "properties": props
                            })
                            
                            if entity.get('type') == 'memory':
                                memory_ids.append(e_id)
                                
                except Exception as e:
                     self.logger.warning(f"Recursive graph traversal failed: {e}. Falling back to flat search.")
                     # Fallback code
                     fallback_cypher = f"MATCH (m:Entity {{type: 'memory'}}) RETURN m ORDER BY m.created_at DESC LIMIT {limit}"
                     results = await self.graph_store.execute_query(fallback_cypher)
                     # (Simple processing for fallback - minimal implementation to prevent crash)
                     for row in results:
                         m = row.get("m")
                         if m:
                             memory_ids.append(m.get("id"))
                             context["entities"].append({"id": str(m.get("id")), "type": "memory", "name": m.get("name")})

            
            # [NEW] Fetch User Profile Context
            # Always try to find the "User" entity and its direct facts (location, role, preferences)
            try:
                user_name = self.config.elefante.user_profile.user_name
                user_cypher = f"""
                MATCH (u:Entity {{name: '{user_name}'}})-[r]-(fact:Entity)
                RETURN u, r, fact
                LIMIT 20
                """
                user_results = await self.graph_store.execute_query(user_cypher)
                for row in user_results:
                    # GraphStore returns {"values": [u, r, fact]}
                    u_entity = row["values"][0]
                    rel = row["values"][1]
                    fact = row["values"][2]
                    
                    # Handle Kuzu dictionary results
                    u_id = u_entity.get('id')
                    if u_id and u_id not in [e["id"] for e in context["entities"]]:
                        u_props = {k: v for k, v in u_entity.items() 
                                 if k not in ['id', 'name', 'type', '_id', '_label']}
                        context["entities"].append({
                            "id": str(u_id),
                            "name": u_entity.get('name'),
                            "type": u_entity.get('type'),
                            "properties": u_props,
                            "is_user_profile": True
                        })

                    fact_id = fact.get('id')
                    if fact_id and fact_id not in [e["id"] for e in context["entities"]]:
                        # Extract properties (exclude internal/standard fields)
                        fact_props = {k: v for k, v in fact.items() 
                                    if k not in ['id', 'name', 'type', '_id', '_label']}
                        
                        context["entities"].append({
                            "id": str(fact_id),
                            "name": fact.get('name'),
                            "type": fact.get('type'),
                            "properties": fact_props,
                            "is_user_fact": True  # Flag for client to prioritize
                        })
                        
                        rel_props = {k: v for k, v in rel.items() 
                                   if k not in ['_id', '_src', '_dst', '_label']}
                        
                        context["relationships"].append({
                            "from": str(u_entity.get('id')),
                            "to": str(fact_id),
                            "type": rel.get('_label'), # Kuzu uses _label for relationship type
                            "properties": rel_props
                        })
            except Exception as e:
                self.logger.warning(f"Failed to fetch User Profile context: {e}")

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
                            if entity:
                                # Handle dict vs object for ID
                                e_id = entity.get('id') if isinstance(entity, dict) else getattr(entity, 'id', None)
                                e_name = entity.get('name') if isinstance(entity, dict) else getattr(entity, 'name', None)
                                e_type = entity.get('type') if isinstance(entity, dict) else getattr(entity, 'type', None)
                                
                                # Handle properties
                                props = {}
                                if isinstance(entity, dict):
                                    p_str = entity.get('properties')
                                    if isinstance(p_str, str):
                                        try:
                                            props = json.loads(p_str)
                                        except:
                                            pass
                                else:
                                    p_str = getattr(entity, 'properties', None)
                                    if isinstance(p_str, str):
                                        try:
                                            props = json.loads(p_str)
                                        except:
                                            pass
                                            
                                if e_id and str(e_id) not in [e["id"] for e in context["entities"]]:
                                    context["entities"].append({
                                        "id": str(e_id),
                                        "name": e_name,
                                        "type": e_type,
                                        "properties": props
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

    def _detect_contradiction(self, new_content: str, existing_content: str) -> bool:
        """
        Detect if new_content semantically contradicts existing_content.
        Uses fast regex-based heuristics (no LLM call).
        
        Contradiction patterns:
        1. Negation: "X is not Y" vs "X is Y"
        2. Opposite sentiment: "I like X" vs "I don't like X"
        3. Factual conflict: "X lives in A" vs "X lives in B"
        """
        import re
        
        new_lower = new_content.lower()
        existing_lower = existing_content.lower()
        
        # Pattern 1: Direct negation markers
        negation_markers = [
            r"\bnot\b", r"\bno\b", r"\bnever\b", r"\bdon't\b", r"\bdoesn't\b",
            r"\bwon't\b", r"\bcan't\b", r"\bisn't\b", r"\baren't\b", r"\bwasn't\b",
            r"\bweren't\b", r"\bshouldn't\b", r"\bwouldn't\b", r"\bcouldn't\b",
            r"\bhate\b", r"\bdislike\b", r"\bavoid\b", r"\bstop\b", r"\bquit\b"
        ]
        
        new_has_negation = any(re.search(p, new_lower) for p in negation_markers)
        existing_has_negation = any(re.search(p, existing_lower) for p in negation_markers)
        
        # XOR: One has negation, other doesn't = potential contradiction
        if new_has_negation != existing_has_negation:
            # Extract subject to verify it's about the same thing
            # Simple heuristic: check if they share significant words
            new_words = set(re.findall(r'\b\w{4,}\b', new_lower))  # Words 4+ chars
            existing_words = set(re.findall(r'\b\w{4,}\b', existing_lower))
            
            # Remove common stopwords
            stopwords = {'that', 'this', 'with', 'from', 'have', 'been', 'were', 'will', 'would', 'could', 'should'}
            new_words -= stopwords
            existing_words -= stopwords
            
            overlap = new_words & existing_words
            
            # If significant overlap + negation difference = contradiction
            if len(overlap) >= 2:
                self.logger.debug(
                    f"Contradiction detected via negation",
                    overlap=list(overlap)[:5]
                )
                return True
        
        return False

    def _is_first_person_statement(self, content: str) -> bool:
        """
        Check if content contains first-person statements using robust regex.
        Avoids false positives from code (e.g., 'i = 0', 'my_var').
        """
        if not self.config.elefante.user_profile.auto_link_first_person:
            return False
            
        # 1. Check if it looks like code (simple heuristic)
        if self.config.elefante.user_profile.detect_code_blocks:
            # Strong heuristic: Starts with code keyword
            if any(content.strip().startswith(k) for k in ['return ', 'import ', 'def ', 'class ', 'for ', 'if ', 'async ', 'await ', 'try:', 'except', 'else', 'elif']):
                return False

            # If it has many code-like symbols, skip
            code_symbols = [
                '{', '}', 'def ', 'class ', 'return ', 'import ', ' = ', '(', ')', 
                'for ', 'if ', 'else', 'elif', 'try:', 'except', 'in ', 'range', 
                'print', '->', '[', ']', ':', 'await ', 'async '
            ]
            if sum(1 for s in code_symbols if s in content) >= 2:  # Lowered threshold to 2 for safety
                return False
        
        # 2. Regex for natural language first-person pronouns
        # \b ensures word boundaries
        # Case insensitive
        # Negative lookahead/behind to avoid variable names like my_var, i_index
        
        # Patterns:
        # "I " (but not "i =")
        # "my " (but not "my_")
        # "me", "we", "our", "mine"
        
        patterns = [
            r'\bI\b(?!\s*=)',  # "I" but not followed by "="
            r'\b(my|me|we|our|mine)\b(?!_)'  # pronouns not followed by underscore
        ]
        
        combined_pattern = '|'.join(patterns)
        return bool(re.search(combined_pattern, content, re.IGNORECASE))
    
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
        # Parse entity type (STRICT)
        parsed_type = EntityType(entity_type)
        
        entity = Entity(
            name=name,
            type=parsed_type,
            properties=properties or {}
        )
        
        # Use idempotent creation (MERGE behavior)
        await self.graph_store.create_or_get_entity(entity)
        self.logger.info(f"Entity created/retrieved: {name} ({entity_type})")
        
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
        # Parse relationship type (STRICT)
        parsed_rel_type = RelationshipType(relationship_type)
        
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
    
    async def consolidate_memories(self, force: bool = False) -> Dict[str, Any]:
        """
        Trigger memory consolidation process
        """
        from src.core.consolidation import MemoryConsolidator
        
        consolidator = MemoryConsolidator()
        new_memories = await consolidator.consolidate_recent(force=force)
        
        return {
            "success": True,
            "consolidated_count": len(new_memories),
            "new_memory_ids": [str(m.id) for m in new_memories]
        }
    
    async def list_all_memories(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: Optional[SearchFilters] = None
    ) -> List[Memory]:
        """
        List all memories without semantic search filtering
        
        This method retrieves memories directly from the vector store without
        applying semantic similarity filtering. Useful for:
        - Database inspection and debugging
        - Exporting all memories
        - Browsing complete memory collection
        - Administrative tasks
        
        Args:
            limit: Maximum number of memories to return (default: 100)
            offset: Number of memories to skip for pagination (default: 0)
            filters: Optional filters (memory_type, importance, etc.)
            
        Returns:
            List[Memory]: List of memory objects
            
        Example:
            # Get first 50 memories
            memories = await orchestrator.list_all_memories(limit=50)
            
            # Get next 50 memories (pagination)
            memories = await orchestrator.list_all_memories(limit=50, offset=50)
            
            # Filter by type
            filters = SearchFilters(memory_type="decision")
            memories = await orchestrator.list_all_memories(filters=filters)
        """
        self.logger.info(
            "Listing all memories",
            limit=limit,
            offset=offset,
            has_filters=filters is not None
        )
        
        try:
            memories = await self.vector_store.get_all(
                limit=limit,
                offset=offset,
                filters=filters
            )
            
            self.logger.info(
                "Listed all memories",
                count=len(memories),
                offset=offset
            )
            
            return memories
            
        except Exception as e:
            self.logger.error(f"Failed to list all memories: {e}", exc_info=True)
            raise
    
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