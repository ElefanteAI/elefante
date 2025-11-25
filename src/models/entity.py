"""
Entity and Relationship models for the knowledge graph
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class EntityType(str, Enum):
    """Types of entities in the knowledge graph"""
    PERSON = "person"
    PROJECT = "project"
    FILE = "file"
    CONCEPT = "concept"
    TECHNOLOGY = "technology"
    TASK = "task"
    ORGANIZATION = "organization"
    LOCATION = "location"
    EVENT = "event"
    CUSTOM = "custom"


class Entity(BaseModel):
    """Entity in the knowledge graph"""
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., min_length=1)
    type: EntityType
    description: Optional[str] = None
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Properties (flexible key-value storage)
    properties: Dict[str, Any] = Field(default_factory=dict)
    
    # Tags for categorization
    tags: List[str] = Field(default_factory=list)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert entity to dictionary"""
        return {
            "id": str(self.id),
            "name": self.name,
            "type": self.type.value,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "properties": self.properties,
            "tags": self.tags,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Entity":
        """Create entity from dictionary"""
        if "id" in data and isinstance(data["id"], str):
            data["id"] = UUID(data["id"])
        if "type" in data and isinstance(data["type"], str):
            data["type"] = EntityType(data["type"])
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data and isinstance(data["updated_at"], str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**data)
    
    def __str__(self) -> str:
        return f"Entity(id={self.id}, name='{self.name}', type={self.type})"
    
    def __repr__(self) -> str:
        return self.__str__()


class RelationshipType(str, Enum):
    """Types of relationships between entities"""
    RELATES_TO = "RELATES_TO"
    DEPENDS_ON = "DEPENDS_ON"
    PART_OF = "PART_OF"
    CREATED_BY = "CREATED_BY"
    CREATED_IN = "CREATED_IN"  # Entity created in a session
    USES = "USES"
    BLOCKS = "BLOCKS"
    REFERENCES = "REFERENCES"
    SIMILAR_TO = "SIMILAR_TO"
    PARENT_OF = "PARENT_OF"
    CHILD_OF = "CHILD_OF"
    WORKS_ON = "WORKS_ON"
    LOCATED_IN = "LOCATED_IN"
    CUSTOM = "CUSTOM"


class Relationship(BaseModel):
    """Relationship between entities in the knowledge graph"""
    id: UUID = Field(default_factory=uuid4)
    from_entity_id: UUID
    to_entity_id: UUID
    relationship_type: RelationshipType
    
    # Optional description
    description: Optional[str] = None
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    strength: float = Field(default=1.0, ge=0.0, le=1.0)  # Relationship strength
    
    # Properties (flexible key-value storage)
    properties: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert relationship to dictionary"""
        return {
            "id": str(self.id),
            "from_entity_id": str(self.from_entity_id),
            "to_entity_id": str(self.to_entity_id),
            "relationship_type": self.relationship_type.value,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "strength": self.strength,
            "properties": self.properties,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Relationship":
        """Create relationship from dictionary"""
        if "id" in data and isinstance(data["id"], str):
            data["id"] = UUID(data["id"])
        if "from_entity_id" in data and isinstance(data["from_entity_id"], str):
            data["from_entity_id"] = UUID(data["from_entity_id"])
        if "to_entity_id" in data and isinstance(data["to_entity_id"], str):
            data["to_entity_id"] = UUID(data["to_entity_id"])
        if "relationship_type" in data and isinstance(data["relationship_type"], str):
            data["relationship_type"] = RelationshipType(data["relationship_type"])
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**data)
    
    def __str__(self) -> str:
        return f"Relationship({self.from_entity_id} -{self.relationship_type}-> {self.to_entity_id})"
    
    def __repr__(self) -> str:
        return self.__str__()

# Made with Bob
