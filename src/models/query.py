"""
Query models for search and retrieval operations
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.models.memory import Memory


class QueryMode(str, Enum):
    """Query execution modes"""
    SEMANTIC = "semantic"      # Vector search only
    STRUCTURED = "structured"  # Graph search only
    HYBRID = "hybrid"          # Combined search


class QueryPlan(BaseModel):
    """Plan for executing a query across databases"""
    mode: QueryMode
    vector_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    graph_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    
    # Query parameters
    limit: int = Field(default=10, ge=1, le=100)
    min_similarity: float = Field(default=0.3, ge=0.0, le=1.0)
    
    # Filters
    memory_types: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    min_importance: Optional[int] = None
    date_range: Optional[Dict[str, datetime]] = None
    
    # Graph-specific
    max_depth: int = Field(default=2, ge=1, le=5)

    @model_validator(mode="after")
    def normalize_weights(self):
        """Ensure vector_weight + graph_weight ~= 1.0 (normalize if needed)."""
        total = float(self.vector_weight) + float(self.graph_weight)
        if total <= 0.0:
            self.vector_weight = 0.5
            self.graph_weight = 0.5
            return self

        if abs(total - 1.0) > 0.01:
            self.vector_weight = float(self.vector_weight) / total
            self.graph_weight = float(self.graph_weight) / total
        return self
    
    model_config = ConfigDict()


class SearchResult(BaseModel):
    """Result from a search operation"""
    memory: Memory
    score: float = Field(ge=0.0, le=1.0)
    source: str  # "vector", "graph", or "hybrid"
    
    # Breakdown of scores
    vector_score: Optional[float] = None
    graph_score: Optional[float] = None
    
    # V5: Retrieval explanation (Req-1)
    explanation: Optional[Dict[str, Any]] = None
    
    # Context information
    matched_entities: List[UUID] = Field(default_factory=list)
    relationship_path: Optional[List[str]] = None
    
    model_config = ConfigDict()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = {
            "memory": self.memory.to_dict(),
            "score": self.score,
            "source": self.source,
            "vector_score": self.vector_score,
            "graph_score": self.graph_score,
            "matched_entities": [str(e) for e in self.matched_entities],
            "relationship_path": self.relationship_path,
        }
        # V5: Include explanation if present
        if self.explanation:
            result["explanation"] = self.explanation
        return result
    
    def __str__(self) -> str:
        return f"SearchResult(score={self.score:.3f}, source={self.source}, memory_id={self.memory.id})"
    
    def __repr__(self) -> str:
        return self.__str__()


class SearchFilters(BaseModel):
    """Filters for search operations"""
    memory_type: Optional[str] = None
    domain: Optional[str] = None
    category: Optional[str] = None
    min_importance: Optional[int] = Field(None, ge=1, le=10)
    max_importance: Optional[int] = Field(None, ge=1, le=10)
    tags: Optional[List[str]] = None
    source: Optional[str] = None
    
    # Date filters
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    
    # Entity filters
    related_entities: Optional[List[UUID]] = None
    
    # Project/file filters
    project: Optional[str] = None
    file_path: Optional[str] = None
    
    # NEW: Conversation context filters
    session_id: Optional[UUID] = None
    include_conversation: bool = True
    include_stored: bool = True
    conversation_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    
    model_config = ConfigDict()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database queries"""
        filters = {}
        
        if self.memory_type:
            filters["memory_type"] = self.memory_type
        if self.domain:
            filters["domain"] = self.domain
        if self.category:
            filters["category"] = self.category
        if self.min_importance is not None:
            filters["min_importance"] = self.min_importance
        if self.max_importance is not None:
            filters["max_importance"] = self.max_importance
        if self.tags:
            filters["tags"] = self.tags
        if self.source:
            filters["source"] = self.source
        if self.start_date:
            filters["start_date"] = self.start_date.isoformat()
        if self.end_date:
            filters["end_date"] = self.end_date.isoformat()
        if self.related_entities:
            filters["related_entities"] = [str(e) for e in self.related_entities]
        if self.project:
            filters["project"] = self.project
        if self.file_path:
            filters["file_path"] = self.file_path
            
        return filters

