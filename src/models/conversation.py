"""
Conversation context models for Elefante

Defines data structures for conversation messages and search candidates
that enable context-aware memory search across sessions.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class Message(BaseModel):
    """
    Represents a single conversation message
    
    Messages are the atomic units of conversation context, capturing
    user and assistant exchanges within a session.
    """
    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str = Field(..., min_length=1)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary"""
        return {
            "id": str(self.id),
            "session_id": str(self.session_id),
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Create message from dictionary"""
        if "id" in data and isinstance(data["id"], str):
            data["id"] = UUID(data["id"])
        if "session_id" in data and isinstance(data["session_id"], str):
            data["session_id"] = UUID(data["session_id"])
        if "timestamp" in data and isinstance(data["timestamp"], str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


class SearchCandidate(BaseModel):
    """
    Unified search candidate from any source
    
    Represents a potential search result before final ranking and deduplication.
    Can originate from conversation context, semantic search, graph traversal,
    or be a merged result from multiple sources (hybrid).
    """
    text: str = Field(..., min_length=1)
    score: float = Field(ge=0.0, le=1.0)
    source: str = Field(..., pattern="^(conversation|semantic|graph|hybrid)$")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Optional embedding for deduplication
    embedding: Optional[List[float]] = None
    
    # For linking back to stored memories
    memory_id: Optional[UUID] = None
    
    class Config:
        json_encoders = {
            UUID: lambda v: str(v) if v else None,
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert candidate to dictionary"""
        return {
            "text": self.text,
            "score": self.score,
            "source": self.source,
            "metadata": self.metadata,
            "memory_id": str(self.memory_id) if self.memory_id else None,
            "has_embedding": self.embedding is not None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SearchCandidate":
        """Create candidate from dictionary"""
        if "memory_id" in data and data["memory_id"] and isinstance(data["memory_id"], str):
            data["memory_id"] = UUID(data["memory_id"])
        # Remove has_embedding flag if present (not part of model)
        data.pop("has_embedding", None)
        return cls(**data)
    
    def __str__(self) -> str:
        return f"SearchCandidate(score={self.score:.3f}, source={self.source}, text='{self.text[:50]}...')"
    
    def __repr__(self) -> str:
        return self.__str__()


# Made with Bob