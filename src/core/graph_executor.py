"""
Graph Executor
Executes dynamic graph updates based on Cognitive Analysis.
"""

import asyncio
from typing import Dict, Any, List, Optional
from uuid import UUID, uuid4
from datetime import datetime

from src.core.graph_store import GraphStore, get_graph_store
from src.models.entity import Entity, EntityType, Relationship, RelationshipType
from src.utils.logger import get_logger
from src.utils.config import get_config

logger = get_logger(__name__)

class GraphExecutor:
    """
    Executes graph operations derived from Cognitive Analysis.
    Handles entity merging, relationship creation, and user linking.
    """
    
    def __init__(self, graph_store: Optional[GraphStore] = None):
        self.graph_store = graph_store or get_graph_store()
        self.config = get_config()
        self.user_name = self.config.elefante.user_profile.user_name
        
    async def execute_analysis(self, analysis: Dict[str, Any], memory_id: UUID) -> None:
        """
        Execute the graph updates from a Cognitive Analysis.
        
        Args:
            analysis: Dictionary matching CognitiveAnalysis schema
            memory_id: ID of the source memory node
        """
        logger.info("Executing Cognitive Graph Update", memory_id=str(memory_id))
        
        entity_map: Dict[str, UUID] = {}
        
        # 1. Process Entities
        for entity_data in analysis.get("entities", []):
            name = entity_data.get("name")
            type_str = entity_data.get("type", "Concept")
            
            # Normalize User entity
            if name.lower() in ["user", "me", "i", "myself"]:
                name = self.user_name
                type_str = "Person"
                
            # Create or Merge Entity
            entity_id = await self._merge_entity(name, type_str, entity_data.get("description"))
            entity_map[name] = entity_id
            
            # Link Memory -> Entity (MENTIONS)
            # We use RELATES_TO as a generic "mentions" for now
            await self._create_relationship(
                memory_id, 
                entity_id, 
                RelationshipType.RELATES_TO, 
                {"source": "cognitive_analysis"}
            )
            
        # 2. Process Relationships
        for rel_data in analysis.get("relationships", []):
            source_name = rel_data.get("source")
            target_name = rel_data.get("target")
            rel_type_str = rel_data.get("type", "RELATES_TO")
            reason = rel_data.get("reason")
            
            # Normalize names
            if source_name.lower() in ["user", "me", "i"]: source_name = self.user_name
            if target_name.lower() in ["user", "me", "i"]: target_name = self.user_name
            
            # Get IDs (should exist from step 1, but handle missing safely)
            source_id = entity_map.get(source_name)
            target_id = entity_map.get(target_name)
            
            if not source_id:
                source_id = await self._merge_entity(source_name, "Concept")
                entity_map[source_name] = source_id
            
            if not target_id:
                target_id = await self._merge_entity(target_name, "Concept")
                entity_map[target_name] = target_id
                
            # Map string type to Enum or Custom
            try:
                rel_type = RelationshipType(rel_type_str.upper())
            except ValueError:
                # Fallback to CUSTOM or closest match
                # For now, we map everything to RELATES_TO or similar if not in Enum
                # Ideally we extend RelationshipType or use CUSTOM
                rel_type = RelationshipType.CUSTOM
                
            # Create Relationship
            props = {"type_label": rel_type_str.upper()} # Store original label
            if reason:
                props["reason"] = reason
                
            await self._create_relationship(source_id, target_id, rel_type, props)
            
    async def _merge_entity(self, name: str, type_str: str, description: str = None) -> UUID:
        """
        Find existing entity by name or create new one.
        Note: This is a poor man's MERGE until Kuzu supports it fully via Cypher in Python API.
        """
        # 1. Try to find existing entity by name using execute_query (MERGE not yet available via Python API)
        query = f"MATCH (e:Entity {{name: '{name}'}}) RETURN e"
        results = await self.graph_store.execute_query(query)
        
        if results:
            # Found existing
            entity = results[0].get("e")
            if entity:
                # Ideally we update description if new one is better, but skip for now
                return entity.id if hasattr(entity, 'id') else UUID(entity.get('id'))
        
        # 2. Create new
        try:
            entity_type = EntityType(type_str.lower())
        except ValueError:
            entity_type = EntityType.CONCEPT
            
        new_entity = Entity(
            name=name,
            type=entity_type,
            description=description,
            properties={"original_type": type_str}
        )
        
        await self.graph_store.create_entity(new_entity)
        return new_entity.id

    async def _create_relationship(
        self, 
        source_id: UUID, 
        target_id: UUID, 
        rel_type: RelationshipType,
        properties: Dict[str, Any]
    ) -> None:
        """Create a relationship between two entities."""
        
        rel = Relationship(
            from_entity_id=source_id,
            to_entity_id=target_id,
            relationship_type=rel_type,
            properties=properties
        )
        await self.graph_store.create_relationship(rel)
