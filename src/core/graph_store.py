"""
Graph store implementation using Kuzu

Provides structured memory storage with entities and relationships.
Supports Cypher-like queries for deterministic fact retrieval.
"""

import asyncio
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime
from pathlib import Path

from src.models.entity import Entity, EntityType, Relationship, RelationshipType
from src.models.memory import Memory, MemoryMetadata, MemoryType
from src.utils.config import get_config
from src.utils.logger import get_logger
from src.utils.validators import validate_entity_name, validate_cypher_query

logger = get_logger(__name__)


class GraphStore:
    """
    Graph store for structured memory using Kuzu
    
    Stores entities and relationships in a knowledge graph.
    Supports Cypher-like queries for complex graph traversal.
    """
    
    def __init__(self, database_path: Optional[str] = None, read_only: bool = False):
        """
        Initialize graph store
        
        Args:
            database_path: Path to Kuzu database directory
            read_only: If True, open in read-only mode (NOT SUPPORTED BY KUZU - kept for future)
        """
        self.config = get_config()
        self.database_path = database_path or self.config.elefante.graph_store.database_path
        self.buffer_pool_size = self.config.elefante.graph_store.buffer_pool_size
        self.read_only = read_only
        
        self._conn = None
        self._db = None
        self._schema_initialized = False
        self._lock = None  # For thread safety
        
        logger.info(
            "initializing_graph_store",
            database_path=self.database_path,
            read_only=read_only
        )
    
    def _parse_buffer_size(self, size_str: str) -> int:
        """
        Parse buffer size string (e.g., '512MB') to bytes integer.
        
        Args:
            size_str: Size string like '512MB', '1GB', etc.
            
        Returns:
            Size in bytes as integer
        """
        if isinstance(size_str, int):
            return size_str
            
        size_str = size_str.upper().strip()
        
        # Extract number and unit
        import re
        match = re.match(r'(\d+)\s*(MB|GB|KB|B)?', size_str)
        if not match:
            logger.warning(f"Invalid buffer size format: {size_str}, using default 512MB")
            return 512 * 1024 * 1024
        
        number = int(match.group(1))
        unit = match.group(2) or 'B'
        
        # Convert to bytes
        multipliers = {
            'B': 1,
            'KB': 1024,
            'MB': 1024 * 1024,
            'GB': 1024 * 1024 * 1024
        }
        
        return number * multipliers.get(unit, 1)
    
    def _initialize_connection(self):
        """Initialize Kuzu connection (lazy loading) with thread safety"""
        if self._conn is not None:
            return
        
        # Initialize lock for thread-safe access
        if self._lock is None:
            import threading
            self._lock = threading.RLock()
        
        try:
            import kuzu
            
            # Create database parent directory if it doesn't exist
            db_path = Path(self.database_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)

            # --- ROBUST INIT START ---
            # Fix for Kuzu 0.11+ "clean install crash"
            # Issue: If kuzu_db exists as an empty directory (from manual mkdir) or file, Kuzu fails.
            if db_path.exists():
                if db_path.is_file():
                    if db_path.stat().st_size == 0:
                        logger.warning(f"kuzu_path_conflict: Removing empty file at {db_path}.")
                        db_path.unlink()
                    else:
                        logger.info(f"kuzu_path_check: Found existing file at {db_path}. Assuming valid DB.")
                elif db_path.is_dir() and not any(db_path.iterdir()):
                    logger.info(f"kuzu_clean_init: Removing empty pre-created directory at {db_path}.")
                    db_path.rmdir()
            # --- ROBUST INIT END ---


            
            # Kuzu expects the database path to be a directory that it manages
            # The directory should exist and contain Kuzu database files
            # Convert buffer_pool_size from string (e.g., "512MB") to bytes integer
            buffer_size_bytes = self._parse_buffer_size(self.buffer_pool_size)
            
            # Initialize database - Kuzu will use the directory as-is
            self._db = kuzu.Database(self.database_path, buffer_pool_size=buffer_size_bytes)
            self._conn = kuzu.Connection(self._db)
            
            # Initialize schema
            if not self._schema_initialized:
                self._initialize_schema()
            
            logger.info("kuzu_initialized", database_path=self.database_path)
            
        except ImportError:
            logger.error("kuzu_not_installed")
            raise ImportError(
                "kuzu not installed. "
                "Install with: pip install kuzu"
            )
        except RuntimeError as e:
            error_msg = str(e)
            if "Could not set lock on file" in error_msg or "IO exception" in error_msg:
                logger.error("kuzu_database_locked", error=error_msg)
                raise RuntimeError(
                    f"Kuzu database is locked by another process. "
                    f"This usually means the dashboard server or another MCP instance is running. "
                    f"Database path: {self.database_path}\n"
                    f"Solution: Stop the dashboard server or other processes accessing the database."
                ) from e
            logger.error("failed_to_initialize_kuzu", error=error_msg)
            raise
        except Exception as e:
            logger.error("failed_to_initialize_kuzu", error=str(e))
            raise

    def close(self):
        """Explicitly close connection and database to release locks."""
        if self._conn:
            # self._conn.close() # Kuzu Connection object doesn't have close(), it just goes out of scope? 
            # Double check docs, but assuming we drop ref.
            self._conn = None
            
        if self._db:
             # self._db.close() # Kuzu Database object might not have close either, but dropping refs is key.
             # According to docs/debug/database-neural-register.md, we should implement close.
             # If kuzu doesn't support specific close methods, assigning None allows GC to clean up.
             # However, it's safer to check if they have it.
             self._db = None
             
        logger.info("kuzu_connection_closed")

    def __enter__(self):
        """Context manager entry."""
        self._initialize_connection()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.close()

    def __del__(self):
        """Destructor cleanup."""
        try:
            self.close()
        except:
            pass
    
    def _get_query_results(self, result) -> list:
        """
        Helper to extract all rows from a Kuzu QueryResult.
        Kuzu 0.1.0 uses has_next() and get_next() instead of get_all()
        """
        rows = []
        while result.has_next():
            rows.append(result.get_next())
        return rows
    
    def _initialize_schema(self):
        """Initialize Kuzu schema (node and relationship tables)"""
        try:
            # Create node tables (Kuzu 0.1.0 doesn't support IF NOT EXISTS)
            # We'll catch exceptions for already-existing tables
            
            tables_to_create = [
                # Node tables
                """
                CREATE NODE TABLE Memory(
                    id STRING,
                    content STRING,
                    timestamp TIMESTAMP,
                    memory_type STRING,
                    importance INT64,
                    PRIMARY KEY(id)
                )
                """,
                """
                CREATE NODE TABLE Entity(
                    id STRING,
                    name STRING,
                    type STRING,
                    description STRING,
                    created_at TIMESTAMP,
                    props STRING,
                    PRIMARY KEY(id)
                )
                """,
                """
                CREATE NODE TABLE Session(
                    id STRING,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    PRIMARY KEY(id)
                )
                """,
                # Relationship tables
                """
                CREATE REL TABLE RELATES_TO(
                    FROM Entity TO Entity,
                    strength DOUBLE
                )
                """,
                """
                CREATE REL TABLE PART_OF(
                    FROM Entity TO Entity
                )
                """,
                """
                CREATE REL TABLE DEPENDS_ON(
                    FROM Entity TO Entity,
                    description STRING
                )
                """,
                """
                CREATE REL TABLE REFERENCES(
                    FROM Entity TO Entity,
                    reference_type STRING
                )
                """,
                """
                CREATE REL TABLE CREATED_IN(
                    FROM Entity TO Entity
                )
                """
            ]
            
            for table_sql in tables_to_create:
                try:
                    self._conn.execute(table_sql)
                except Exception as table_error:
                    # Ignore "already exists" errors
                    error_msg = str(table_error).lower()
                    if "already exists" not in error_msg and "duplicate" not in error_msg:
                        logger.warning("table_creation_warning", error=str(table_error))
            
            self._schema_initialized = True
            logger.info("kuzu_schema_initialized")
            
        except Exception as e:
            logger.error("failed_to_initialize_schema", error=str(e))
            raise
    
    async def create_entity(self, entity: Entity) -> UUID:
        """
        Create an entity in the graph (DEPRECATED - use create_or_get_entity for deduplication)
        
        Args:
            entity: Entity object to create
            
        Returns:
            Entity ID
        """
        self._initialize_connection()
        import json
        
        # Validate entity name
        validate_entity_name(entity.name)
        
        # Helper for JSON serialization
        def json_serializer(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            if hasattr(obj, 'value'): # Handle Enums
                return obj.value
            raise TypeError(f"Type {type(obj)} not serializable")
        
        props_json = json.dumps(entity.properties, default=json_serializer)
        created_at_iso = entity.created_at.isoformat() if entity.created_at else datetime.now().isoformat()
        
        query = """
            CREATE (e:Entity {
                id: $id,
                name: $name,
                type: $type,
                description: $description,
                created_at: timestamp($created_at),
                props: $props
            })
        """
        
        params = {
            "id": str(entity.id),
            "name": entity.name,
            "type": entity.type.value,
            "description": entity.description or "",
            "created_at": created_at_iso,
            "props": props_json
        }
        
        try:
            await asyncio.to_thread(
                self._conn.execute,
                query,
                params
            )
            
            logger.info(
                "entity_created",
                entity_id=str(entity.id),
                name=entity.name,
                type=entity.type.value
            )
            
            return entity.id
            
        except Exception as e:
            logger.error("failed_to_create_entity", entity_id=str(entity.id), error=str(e))
            raise
    
    async def create_or_get_entity(self, entity: Entity) -> UUID:
        """
        Create entity if not exists, or return existing entity ID (deduplication by name + type)
        
        This method prevents duplicate entities by checking if an entity with the same
        name and type already exists. If found, returns the existing entity's ID.
        If not found, creates a new entity.
        
        Args:
            entity: Entity object to create
            
        Returns:
            Entity ID (existing or newly created)
        """
        self._initialize_connection()
        
        # Validate entity name
        validate_entity_name(entity.name)
        
        # First, try to find existing entity by name + type
        query_find = """
            MATCH (e:Entity)
            WHERE e.name = $name AND e.type = $type
            RETURN e.id
        """
        
        try:
            result = await asyncio.to_thread(
                self._conn.execute,
                query_find,
                {"name": entity.name, "type": entity.type.value}
            )
            
            rows = self._get_query_results(result)
            if rows:
                # Entity exists, return its ID
                existing_id = UUID(rows[0][0])
                logger.debug(
                    "entity_already_exists",
                    entity_name=entity.name,
                    entity_type=entity.type.value,
                    entity_id=str(existing_id)
                )
                return existing_id
            
            # Entity doesn't exist, create it
            query_create = """
                CREATE (e:Entity {
                    id: $id,
                    name: $name,
                    type: $type,
                    description: $description,
                    created_at: $created_at
                })
            """
            
            params = {
                "id": str(entity.id),
                "name": entity.name,
                "type": entity.type.value,
                "description": entity.description or "",
                "created_at": entity.created_at
            }
            
            await asyncio.to_thread(
                self._conn.execute,
                query_create,
                params
            )
            
            logger.info(
                "entity_created",
                entity_id=str(entity.id),
                name=entity.name,
                type=entity.type.value
            )
            
            return entity.id
            
        except Exception as e:
            logger.error(
                "failed_to_create_or_get_entity",
                entity_name=entity.name,
                entity_type=entity.type.value,
                error=str(e)
            )
            raise
    
    async def get_entity(self, entity_id: UUID) -> Optional[Entity]:
        """
        Get an entity by ID
        
        Args:
            entity_id: Entity UUID
            
        Returns:
            Entity object or None if not found
        """
        self._initialize_connection()
        import json
        
        query = """
            MATCH (e:Entity)
            WHERE e.id = $id
            RETURN e.id, e.name, e.type, e.description, e.created_at, e.properties
        """
        
        try:
            result = await asyncio.to_thread(
                self._conn.execute,
                query,
                {"id": str(entity_id)}
            )
            
            rows = self._get_query_results(result)
            if not rows:
                return None
            
            row = rows[0]
            
            # Parse properties JSON if present
            props = {}
            if len(row) > 5 and row[5]:
                try:
                    props = json.loads(row[5])
                except:
                    props = {}

            entity = Entity(
                id=UUID(row[0]),
                name=row[1],
                type=EntityType(row[2]),
                description=row[3] if row[3] else None,
                created_at=datetime.fromisoformat(row[4]),
                properties=props
            )
            
            return entity
            
        except Exception as e:
            logger.error("failed_to_get_entity", entity_id=str(entity_id), error=str(e))
            return None
    
    async def create_relationship(self, relationship: Relationship) -> UUID:
        """
        Create a relationship between entities
        
        Args:
            relationship: Relationship object to create
            
        Returns:
            Relationship ID
        """
        self._initialize_connection()
        
        # Map relationship type to Kuzu relationship table
        rel_type_map = {
            RelationshipType.RELATES_TO: "RELATES_TO",
            RelationshipType.DEPENDS_ON: "DEPENDS_ON",
            RelationshipType.REFERENCES: "REFERENCES",
            RelationshipType.CREATED_IN: "CREATED_IN",
        }
        
        rel_table = rel_type_map.get(relationship.relationship_type, "RELATES_TO")
        
        # FIX: Kuzu 0.1.0 requires properties to be set during CREATE, not with SET afterward
        # Properties must be included in the CREATE clause: CREATE ()-[r:TYPE {prop: value}]->()
        query = f"""
            MATCH (fromNode:Entity), (toNode:Entity)
            WHERE fromNode.id = $from_id AND toNode.id = $to_id
            CREATE (fromNode)-[r:{rel_table} {{strength: $strength}}]->(toNode)
        """
        
        params = {
            "from_id": str(relationship.from_entity_id),
            "to_id": str(relationship.to_entity_id),
            "strength": relationship.strength
        }
        
        try:
            await asyncio.to_thread(
                self._conn.execute,
                query,
                params
            )
            
            logger.info(
                "relationship_created",
                relationship_id=str(relationship.id),
                type=relationship.relationship_type.value
            )
            
            return relationship.id
            
        except Exception as e:
            logger.error("failed_to_create_relationship", relationship_id=str(relationship.id), error=str(e))
            raise
    
    async def get_relationships(
        self,
        entity_id: UUID,
        direction: str = "both"
    ) -> List[Relationship]:
        """
        Get relationships for an entity
        
        Args:
            entity_id: Entity UUID
            direction: "outgoing", "incoming", or "both"
            
        Returns:
            List of relationships
        """
        self._initialize_connection()
        
        if direction == "outgoing":
            query = """
                MATCH (fromNode:Entity)-[r]->(toNode:Entity)
                WHERE fromNode.id = $id
                RETURN fromNode.id, toNode.id, type(r), r.strength
            """
        elif direction == "incoming":
            query = """
                MATCH (fromNode:Entity)-[r]->(toNode:Entity)
                WHERE toNode.id = $id
                RETURN fromNode.id, toNode.id, type(r), r.strength
            """
        else:  # both
            query = """
                MATCH (e1:Entity)-[r]-(e2:Entity)
                WHERE e1.id = $id OR e2.id = $id
                RETURN e1.id, e2.id, type(r), r.strength
            """
        
        try:
            result = await asyncio.to_thread(
                self._conn.execute,
                query,
                {"id": str(entity_id)}
            )
            
            relationships = []
            for row in self._get_query_results(result):
                rel = Relationship(
                    from_entity_id=UUID(row[0]),
                    to_entity_id=UUID(row[1]),
                    relationship_type=RelationshipType(row[2]),
                    strength=row[3] if len(row) > 3 else 1.0
                )
                relationships.append(rel)
            
            return relationships
            
        except Exception as e:
            logger.error("failed_to_get_relationships", entity_id=str(entity_id), error=str(e))
            return []
    
    async def execute_query(
        self,
        cypher_query: str,
        params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a Cypher query
        
        Args:
            cypher_query: Cypher query string
            params: Query parameters
            
        Returns:
            List of result dictionaries
        """
        self._initialize_connection()
        
        # Validate query (basic safety check)
        validate_cypher_query(cypher_query)
        
        try:
            result = await asyncio.to_thread(
                self._conn.execute,
                cypher_query,
                params or {}
            )
            
            # Get column names
            column_names = result.get_column_names()
            
            # Convert results to list of dictionaries
            results = []
            while result.has_next():
                row = result.get_next()
                # Map column names to values
                result_dict = {name: val for name, val in zip(column_names, row)}
                # Also keep "values" for backward compatibility if needed, but preferably not
                result_dict["values"] = row
                results.append(result_dict)
            
            logger.info("query_executed", query=cypher_query[:100])
            return results
            
        except Exception as e:
            logger.error("query_execution_failed", query=cypher_query[:100], error=str(e))
            raise
    
    async def find_path(
        self,
        from_entity_id: UUID,
        to_entity_id: UUID,
        max_depth: int = 3
    ) -> List[List[UUID]]:
        """
        Find paths between two entities
        
        Args:
            from_entity_id: Starting entity
            to_entity_id: Target entity
            max_depth: Maximum path length
            
        Returns:
            List of paths (each path is a list of entity IDs)
        """
        self._initialize_connection()
        
        query = f"""
            MATCH path = (from:Entity)-[*1..{max_depth}]-(to:Entity)
            WHERE from.id = $from_id AND to.id = $to_id
            RETURN path
            LIMIT 10
        """
        
        try:
            result = await asyncio.to_thread(
                self._conn.execute,
                query,
                {
                    "from_id": str(from_entity_id),
                    "to_id": str(to_entity_id)
                }
            )
            
            paths = []
            for row in self._get_query_results(result):
                # Extract entity IDs from path
                # This is simplified - actual implementation depends on Kuzu's path format
                path = [from_entity_id, to_entity_id]  # Placeholder
                paths.append(path)
            
            logger.info(
                "paths_found",
                from_id=str(from_entity_id),
                to_id=str(to_entity_id),
                count=len(paths)
            )
            
            return paths
            
        except Exception as e:
            logger.error("failed_to_find_path", error=str(e))
            return []
    
    async def get_neighbors(
        self,
        entity_id: UUID,
        depth: int = 1
    ) -> List[Entity]:
        """
        Get neighboring entities
        
        Args:
            entity_id: Entity UUID
            depth: Traversal depth
            
        Returns:
            List of neighboring entities
        """
        self._initialize_connection()
        
        query = f"""
            MATCH (start:Entity)-[*1..{depth}]-(neighbor:Entity)
            WHERE start.id = $id
            RETURN DISTINCT neighbor.id, neighbor.name, neighbor.type, neighbor.description, neighbor.created_at
        """
        
        try:
            result = await asyncio.to_thread(
                self._conn.execute,
                query,
                {"id": str(entity_id)}
            )
            
            neighbors = []
            for row in self._get_query_results(result):
                entity = Entity(
                    id=UUID(row[0]),
                    name=row[1],
                    type=EntityType(row[2]),
                    description=row[3] if row[3] else None,
                    created_at=datetime.fromisoformat(row[4])
                )
                neighbors.append(entity)
            
            return neighbors
            
        except Exception as e:
            logger.error("failed_to_get_neighbors", entity_id=str(entity_id), error=str(e))
            return []
    
    async def delete_entity(self, entity_id: UUID) -> bool:
        """
        Delete an entity and its relationships
        
        Args:
            entity_id: Entity UUID
            
        Returns:
            True if successful
        """
        self._initialize_connection()
        
        query = """
            MATCH (e:Entity)
            WHERE e.id = $id
            DETACH DELETE e
        """
        
        try:
            await asyncio.to_thread(
                self._conn.execute,
                query,
                {"id": str(entity_id)}
            )
            
            logger.info("entity_deleted", entity_id=str(entity_id))
            return True
            
        except Exception as e:
            logger.error("failed_to_delete_entity", entity_id=str(entity_id), error=str(e))
            return False
    async def search_memories(
        self,
        query: str,
        limit: int = 10,
        apply_temporal_decay: bool = True
    ) -> List[Memory]:
        """
        Search memories in graph store with optional temporal decay
        
        Args:
            query: Search query string
            limit: Maximum number of results
            apply_temporal_decay: Apply temporal strength scoring (default: True)
            
        Returns:
            List of Memory objects
        """
        self._initialize_connection()
        
        # Check if temporal decay is enabled in config
        config = get_config()
        temporal_enabled = (
            apply_temporal_decay and 
            hasattr(config.elefante, 'temporal_decay') and
            config.elefante.temporal_decay.enabled
        )
        
        # Get more results if temporal decay is enabled (for re-ranking)
        search_limit = limit * 2 if temporal_enabled else limit
        
        # Search for memories containing query text
        cypher = """
            MATCH (m:Memory)
            WHERE m.content CONTAINS $query
            RETURN m.id, m.content, m.timestamp, m.memory_type, m.importance
            ORDER BY m.importance DESC
            LIMIT $limit
        """
        
        try:
            result = await asyncio.to_thread(
                self._conn.execute,
                cypher,
                {"query": query, "limit": search_limit}
            )
            
            memories = []
            current_time = datetime.utcnow()
            
            for row in self._get_query_results(result):
                # Reconstruct memory from graph data
                memory_metadata = MemoryMetadata(
                    created_at=row[2] if isinstance(row[2], datetime) else datetime.fromisoformat(row[2]),
                    memory_type=MemoryType(row[3]) if row[3] else MemoryType.CONVERSATION,
                    importance=row[4] if row[4] else 5
                )
                
                memory = Memory(
                    id=UUID(row[0]),
                    content=row[1],
                    metadata=memory_metadata
                )
                
                # Apply temporal decay if enabled
                if temporal_enabled:
                    # Calculate temporal strength
                    temporal_score = memory.calculate_relevance_score(current_time)
                    memory.relevance_score = temporal_score
                    
                    # Update access tracking
                    memory.record_access()
                else:
                    # Use importance as relevance score
                    memory.relevance_score = memory.metadata.importance / 10.0
                
                memories.append(memory)
            
            # Re-sort by relevance score if temporal decay was applied
            if temporal_enabled:
                memories.sort(key=lambda m: m.relevance_score or 0, reverse=True)
                memories = memories[:limit]
            
            logger.info(
                "graph_search_completed",
                query=query[:50],
                results_count=len(memories),
                temporal_decay=temporal_enabled
            )
            
            return memories
            
        except Exception as e:
            logger.error("graph_search_failed", query=query[:50], error=str(e))
            return []
    
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get graph store statistics
        
        Returns:
            Dictionary with statistics
        """
        self._initialize_connection()
        
        try:
            # Count entities
            entity_result = await asyncio.to_thread(
                self._conn.execute,
                "MATCH (e:Entity) RETURN count(e)"
            )
            entity_rows = self._get_query_results(entity_result)
            entity_count = entity_rows[0][0] if entity_rows else 0
            
            # Count relationships
            rel_result = await asyncio.to_thread(
                self._conn.execute,
                "MATCH ()-[r]->() RETURN count(r)"
            )
            rel_rows = self._get_query_results(rel_result)
            rel_count = rel_rows[0][0] if rel_rows else 0
            
            return {
                "database_path": self.database_path,
                "total_entities": entity_count,
                "total_relationships": rel_count,
                "schema_initialized": self._schema_initialized
            }
            
        except Exception as e:
            logger.error("failed_to_get_stats", error=str(e))
            return {}
    
    def __repr__(self) -> str:
        return f"GraphStore(database_path={self.database_path})"


# Global graph store instance
_graph_store: Optional[GraphStore] = None


def get_graph_store() -> GraphStore:
    """
    Get global graph store instance
    
    Returns:
        GraphStore: Global graph store
    """
    global _graph_store
    if _graph_store is None:
        _graph_store = GraphStore()
    return _graph_store


def reset_graph_store():
    """Reset global graph store (useful for testing)"""
    global _graph_store
    _graph_store = None

