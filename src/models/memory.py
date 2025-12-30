"""
Memory data models for Elefante - V2.0 Schema
Enhanced with 3-level taxonomy, relationship tracking, and temporal intelligence
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any, Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, model_validator


# ============================================================================
# ENUMS - Classification & Taxonomy
# ============================================================================

class DomainType(str, Enum):
    """High-level context domains"""
    WORK = "work"
    PERSONAL = "personal"
    LEARNING = "learning"
    PROJECT = "project"
    REFERENCE = "reference"
    SYSTEM = "system"


class MemoryType(str, Enum):
    """Types of memories that can be stored"""
    CONVERSATION = "conversation"
    FACT = "fact"
    INSIGHT = "insight"
    CODE = "code"
    DECISION = "decision"
    TASK = "task"
    NOTE = "note"
    PREFERENCE = "preference"
    QUESTION = "question"
    ANSWER = "answer"
    HYPOTHESIS = "hypothesis"
    OBSERVATION = "observation"


class IntentType(str, Enum):
    """Why the memory was stored"""
    REFERENCE = "reference"
    REMINDER = "reminder"
    LEARNING = "learning"
    DECISION_LOG = "decision_log"
    CONTEXT = "context"
    ACTION = "action"
    ARCHIVE = "archive"
    TEMPLATE = "template"


class MemoryStatus(str, Enum):
    """Status of a memory relative to existing knowledge"""
    NEW = "new"
    REDUNDANT = "redundant"
    CONTRADICTORY = "contradictory"
    RELATED = "related"
    CONSOLIDATED = "consolidated"
    REFINED = "refined"
    VERIFIED = "verified"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class RelationshipType(str, Enum):
    """How memories relate to each other"""
    # Additive
    EXTENDS = "extends"
    SUPPORTS = "supports"
    IMPLEMENTS = "implements"
    EXEMPLIFIES = "exemplifies"
    
    # Transformative
    REFINES = "refines"
    SUPERSEDES = "supersedes"
    CONSOLIDATES = "consolidates"
    
    # Conflictual
    CONTRADICTS = "contradicts"
    CHALLENGES = "challenges"
    
    # Structural
    DEPENDS_ON = "depends_on"
    PART_OF = "part_of"
    REFERENCES = "references"
    RELATES_TO = "relates_to"
    
    # Temporal
    FOLLOWS = "follows"
    PRECEDES = "precedes"
    UPDATES = "updates"


class SourceType(str, Enum):
    """Origin of the memory"""
    USER_INPUT = "user_input"
    AGENT_GENERATED = "agent_generated"
    SYSTEM_INFERRED = "system_inferred"
    EXTERNAL_API = "external_api"
    DOCUMENT = "document"
    WEB_SCRAPE = "web_scrape"
    CODE_ANALYSIS = "code_analysis"
    CONVERSATION = "conversation"


# ============================================================================
# SOURCE RELIABILITY SCORING
# ============================================================================

SOURCE_RELIABILITY_SCORES = {
    SourceType.USER_INPUT: 0.9,
    SourceType.DOCUMENT: 0.8,
    SourceType.CODE_ANALYSIS: 0.8,
    SourceType.AGENT_GENERATED: 0.7,
    SourceType.CONVERSATION: 0.7,
    SourceType.EXTERNAL_API: 0.6,
    SourceType.WEB_SCRAPE: 0.5,
    SourceType.SYSTEM_INFERRED: 0.4,
}


# ============================================================================
# METADATA MODEL
# ============================================================================

class MemoryMetadata(BaseModel):
    """Enhanced metadata for V2.0 schema"""
    
    # Layer 1: Core Identity
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = "user"
    
    # Layer 2: Classification (3-level taxonomy)
    layer: Literal["self", "world", "intent"] = "world"
    sublayer: str = "fact"
    domain: DomainType = DomainType.REFERENCE
    category: str = "general"
    memory_type: MemoryType = MemoryType.CONVERSATION
    subcategory: Optional[str] = None
    
    # Layer 3: Semantic Metadata
    intent: IntentType = IntentType.REFERENCE
    importance: int = Field(default=5, ge=1, le=10)
    urgency: int = Field(default=5, ge=1, le=10)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    tags: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)
    
    # Layer 3b: Cognitive Retrieval (V4 Schema)
    concepts: List[str] = Field(default_factory=list, description="3-5 key terms for graph edges")
    surfaces_when: List[str] = Field(default_factory=list, description="Query patterns that trigger this memory")
    co_activated_with: List[UUID] = Field(default_factory=list, description="Memories often retrieved together")
    authority_score: float = Field(default=0.5, ge=0.0, le=1.0, description="importance × access × freshness")
    contradicts: List[UUID] = Field(default_factory=list, description="Memories with opposing info")
    supports: List[UUID] = Field(default_factory=list, description="Memories that reinforce this one")
    
    # Layer 4: Relationship Tracking
    status: MemoryStatus = MemoryStatus.NEW
    relationship_type: Optional[RelationshipType] = None
    parent_id: Optional[UUID] = None
    related_memory_ids: List[UUID] = Field(default_factory=list)
    conflict_ids: List[UUID] = Field(default_factory=list)
    supersedes_id: Optional[UUID] = None
    superseded_by_id: Optional[UUID] = None
    
    # Layer 5: Source Attribution
    source: SourceType = SourceType.USER_INPUT
    source_detail: str = "direct_input"
    source_reliability: float = Field(default=0.9, ge=0.0, le=1.0)
    verified: bool = False
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    session_id: Optional[UUID] = None
    author: str = "user"
    
    # Layer 6: Context Anchoring
    project: Optional[str] = None
    workspace: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    url: Optional[str] = None
    location: Optional[str] = None
    
    # Layer 7: Temporal Intelligence
    last_accessed: datetime = Field(default_factory=datetime.utcnow)
    last_modified: datetime = Field(default_factory=datetime.utcnow)
    access_count: int = 0
    decay_rate: float = 0.01  # Slow decay by default
    reinforcement_factor: float = 0.1
    
    # Layer 8: Quality & Lifecycle
    version: int = 1
    deprecated: bool = False
    archived: bool = False
    summary: Optional[str] = None
    sentiment: Optional[float] = Field(default=None, ge=-1.0, le=1.0)
    quality_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    
    # Layer 9: Extensibility
    custom_metadata: Dict[str, Any] = Field(default_factory=dict)
    system_metadata: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = ConfigDict(use_enum_values=True)

    @model_validator(mode="after")
    def set_source_reliability(self):
        """Auto-set source reliability based on source type when not explicitly provided."""
        if "source_reliability" not in self.model_fields_set:
            self.source_reliability = SOURCE_RELIABILITY_SCORES.get(self.source, 0.7)
        return self


# ============================================================================
# MEMORY MODEL
# ============================================================================

class Memory(BaseModel):
    """Core memory object with V2.0 schema"""
    
    # Core identity
    id: UUID = Field(default_factory=uuid4)
    content: str = Field(..., min_length=1, max_length=10000)
    metadata: MemoryMetadata = Field(default_factory=MemoryMetadata)
    
    # Vector representation (populated by embedding service)
    embedding: Optional[List[float]] = None
    
    # Graph relationships (entity IDs this memory relates to)
    related_entities: List[UUID] = Field(default_factory=list)
    
    # Retrieval metadata (populated during search)
    similarity_score: Optional[float] = None
    relevance_score: Optional[float] = None
    
    model_config = ConfigDict(use_enum_values=True)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert memory to dictionary"""
        return {
            "id": str(self.id),
            "content": self.content,
            "metadata": self.metadata.model_dump(mode="json"),
            "embedding": self.embedding,
            "related_entities": [str(e) for e in self.related_entities],
            "similarity_score": self.similarity_score,
            "relevance_score": self.relevance_score,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Memory":
        """Create memory from dictionary"""
        if "id" in data and isinstance(data["id"], str):
            data["id"] = UUID(data["id"])
        if "related_entities" in data:
            data["related_entities"] = [
                UUID(e) if isinstance(e, str) else e 
                for e in data["related_entities"]
            ]
        if "metadata" in data and isinstance(data["metadata"], dict):
            data["metadata"] = MemoryMetadata(**data["metadata"])
        return cls(**data)
    
    def calculate_relevance_score(self, current_time: Optional[datetime] = None) -> float:
        """
        Calculate temporal relevance score
        Combines base importance with temporal factors
        """
        import math
        
        if current_time is None:
            current_time = datetime.utcnow()
        
        # Base score from importance
        base = self.metadata.importance / 10.0
        
        # Recency factor (exponential decay)
        days_since_created = (current_time - self.metadata.created_at).days
        recency = math.exp(-self.metadata.decay_rate * days_since_created)
        
        # Access reinforcement (logarithmic growth)
        if self.metadata.access_count > 0:
            reinforcement = 1 + (self.metadata.reinforcement_factor * math.log(self.metadata.access_count + 1))
        else:
            reinforcement = 1.0
        
        # Last access boost
        days_since_access = (current_time - self.metadata.last_accessed).days
        access_boost = math.exp(-0.1 * days_since_access)
        
        # Combined score
        return base * recency * reinforcement * access_boost
    
    def record_access(self):
        """Record that this memory was accessed"""
        self.metadata.last_accessed = datetime.utcnow()
        self.metadata.access_count += 1
    
    def __str__(self) -> str:
        return f"Memory(id={self.id}, type={self.metadata.memory_type}, domain={self.metadata.domain}, content='{self.content[:50]}...')"
    
    def __repr__(self) -> str:
        return self.__str__()


# ============================================================================
# BACKWARD COMPATIBILITY HELPERS
# ============================================================================

def create_v1_compatible_memory(
    content: str,
    memory_type: str = "conversation",
    importance: int = 5,
    tags: Optional[List[str]] = None,
    source: str = "user",
    session_id: Optional[UUID] = None,
    project: Optional[str] = None,
    file_path: Optional[str] = None,
    **kwargs
) -> Memory:
    """
    Create a V2 memory from V1-style parameters
    Provides backward compatibility for existing code
    """
    # Map V1 source to V2 SourceType
    source_mapping = {
        "user": SourceType.USER_INPUT,
        "agent": SourceType.AGENT_GENERATED,
        "system": SourceType.SYSTEM_INFERRED,
    }
    
    source_type = source_mapping.get(source, SourceType.USER_INPUT)
    
    # Infer domain from project/tags
    domain = DomainType.REFERENCE
    if project:
        domain = DomainType.PROJECT
    elif tags and any(tag in ["work", "professional"] for tag in tags):
        domain = DomainType.WORK
    elif tags and any(tag in ["learning", "education"] for tag in tags):
        domain = DomainType.LEARNING
    
    # Infer category from tags
    category = "general"
    if tags and len(tags) > 0:
        category = tags[0]  # Use first tag as category
    
    metadata = MemoryMetadata(
        memory_type=MemoryType(memory_type) if isinstance(memory_type, str) else memory_type,
        importance=importance,
        tags=tags or [],
        source=source_type,
        session_id=session_id,
        project=project,
        file_path=file_path,
        domain=domain,
        category=category,
        **kwargs
    )
    
    return Memory(content=content, metadata=metadata)


