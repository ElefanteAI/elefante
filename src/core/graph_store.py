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
from src.models.memory import Memory
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
    
    def __init__(self, database_path: Optional[str] = None):
        """
        Initialize graph store
        
        Args:
            database_path: Path to Kuzu database directory
        """
        self.config = get_config()
        self.database_path = database_path or self.config.elefante.graph_store.database_path
        self.buffer_pool_size = self.config.elefante.graph_store.buffer_pool_size
        
        self._conn = None
        self._schema_initialized = False
        
        logger.info(
            "initializing_graph_store",
            database_path=self.database_path
        )
    
    def _initialize_connection(self):
        """Initialize Kuzu connection (lazy loading)"""
        if self._conn is not None:
            return
        
        try:
            import kuzu
            
            # Create database directory if it doesn't exist
            Path(self.database_path).mkdir(parents=True, exist_ok=True)
            
            # Initialize database
            db = kuzu.Database(self.database_path)
            self._conn = kuzu.Connection(db)
            
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
        except Exception as e:
            logger.error("failed_to_initialize_kuzu", error=str(e))
            raise
    
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
                    FROM Memory TO Entity,
                    strength DOUBLE
                )
                """,
                """
                CREATE REL TABLE PART_OF(
                    FROM Memory TO Session
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
                    FROM Memory TO Memory,
                    reference_type STRING
                )
                """,
                """
                CREATE REL TABLE CREATED_IN(
                    FROM Entity TO Session
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
        Create an entity in the graph
        
        Args:
            entity: Entity object to create
            
        Returns:
            Entity ID
        """
        self._initialize_connection()
        
        # Validate entity name
        validate_entity_name(entity.name)
        
        query = """
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
            "created_at": entity.created_at  # Pass datetime object directly for Kuzu
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
    
    async def get_entity(self, entity_id: UUID) -> Optional[Entity]:
        """
        Get an entity by ID
        
        Args:
            entity_id: Entity UUID
            
        Returns:
            Entity object or None if not found
        """
        self._initialize_connection()
        
        query = """
            MATCH (e:Entity)
            WHERE e.id = $id
            RETURN e.id, e.name, e.type, e.description, e.created_at
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
            entity = Entity(
                id=UUID(row[0]),
                name=row[1],
                type=EntityType(row[2]),
                description=row[3] if row[3] else None,
                created_at=datetime.fromisoformat(row[4])
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
            
            # Convert results to list of dictionaries
            results = []
            for row in self._get_query_results(result):
                # Create dict from row (simplified - may need column names)
                result_dict = {"values": row}
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

# Made with Bob
