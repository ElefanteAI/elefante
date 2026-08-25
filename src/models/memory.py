# ─────────────────────────────────────────────────────────────────────────────
# MODULE  : src/models/memory.py
# VERSION : 2.5.2
# CHANGED : 2026-04-15
# PURPOSE : Core Memory dataclass and MemoryMetadata; the canonical in-memory
#           representation passed through the entire pipeline.
# ROLE    : Models — imported everywhere. This is the data contract between
#           vector_store, graph_store, orchestrator, server, and serializers.
# TOUCHED : When adding new memory fields, changing the metadata schema, or
#           adding new memory_type values. Changes here ripple across the entire
#           system including ChromaDB schema and Kuzu schema.
# ─────────────────────────────────────────────────────────────────────────────
"""
Memory data models for Elefante.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, model_validator
from src.models.entity import RelationshipType  # noqa: F401 — re-exported for MemoryMetadata


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
    """Types of memories that can be stored.
    
    Simplified from 12 to 6 values based on actual usage data.
    Industry research (Mem0, Cognee, Generative Agents) confirms:
    static type enums add zero retrieval power. These exist for
    human browsing and decay-rate differentiation only.
    """
    FACT = "fact"
    DECISION = "decision"
    PREFERENCE = "preference"
    INSIGHT = "insight"
    NOTE = "note"
    CONVERSATION = "conversation"
    SPECIFICATION = "specification"
    DIRECTIVE = "directive"


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
# DECAY RATES BY MEMORY TYPE
# Controls how fast a memory loses relevance without access.
# Half-life = ln(2) / decay_rate  (in days)
# ============================================================================

TYPE_DECAY_RATES: Dict[str, float] = {
    "preference": 0.002,    # ~347 days  — preferences are stable
    "decision": 0.005,      # ~139 days  — decisions get revisited
    "fact": 0.005,          # ~139 days  — facts change
    "insight": 0.008,       # ~87 days   — insights are validated or forgotten
    "note": 0.015,          # ~46 days   — notes are transient
    "conversation": 0.025,  # ~28 days   — conversations are ephemeral
    "specification": 0.0,   # Immutable  — specifications do not decay
    "directive": 0.0,       # Immutable  — directives do not decay
}


# ============================================================================
# METADATA MODEL
# ============================================================================

class MemoryMetadata(BaseModel):
    """Memory metadata."""
    
    # Identity
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = "user"
    
    # Classification (agent provides these)
    domain: DomainType = DomainType.REFERENCE
    category: str = "general"
    memory_type: MemoryType = MemoryType.FACT

    # Relevance (system-computed — do NOT set manually)
    score: int = Field(default=100, ge=0, le=100, description="Behavioral vitality (0-100). Born at 100 — decays slowly with age, grows with retrieval. Unproven memories keep full vitality until the agent actually uses them.")
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    tags: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)
    
    # Cognitive Retrieval
    concepts: List[str] = Field(default_factory=list, description="3-5 key terms for graph edges")
    surfaces_when: List[str] = Field(default_factory=list, description="Stored trigger metadata for inspection and future proactive surfacing; not a current ranking signal")
    authority_score: float = Field(default=0.5, ge=0.0, le=1.0, description="score x access x freshness")
    
    # Relationship Tracking
    status: MemoryStatus = MemoryStatus.NEW
    relationship_type: Optional[RelationshipType] = None
    parent_id: Optional[UUID] = None
    related_memory_ids: List[UUID] = Field(default_factory=list)
    conflict_ids: List[UUID] = Field(default_factory=list)
    supersedes_id: Optional[UUID] = None
    superseded_by_id: Optional[UUID] = None
    
    # Source Attribution
    source: SourceType = SourceType.USER_INPUT
    source_detail: str = "direct_input"
    source_reliability: float = Field(default=0.9, ge=0.0, le=1.0)
    verified: bool = False
    session_id: Optional[UUID] = None
    author: str = "user"
    
    # Context Anchoring
    project: Optional[str] = None
    workspace: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    url: Optional[str] = None
    location: Optional[str] = None
    
    # Temporal Intelligence
    last_accessed: datetime = Field(default_factory=datetime.utcnow)
    last_modified: datetime = Field(default_factory=datetime.utcnow)
    access_count: int = 0
    decay_rate: float = 0.01  # Set from TYPE_DECAY_RATES at creation
    reinforcement_factor: float = 0.25
    
    # Quality & Lifecycle
    version: int = 1
    deprecated: bool = False
    archived: bool = False
    summary: Optional[str] = None

    # Extensibility
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
    """Core memory object."""
    
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
        Behavioral vitality.

        Nobody assigns importance. Vitality emerges from behavior:
        - Recency: core exponential decay based on memory type's half-life
        - Reinforcement: frequent retrieval SLOWS the decay rate (extends half-life)
          rather than multiplying the product — this keeps scores bounded 0–100
          and ensures high-use memories survive longer WITHOUT inflating to 100+
        - Freshness: gentle additional penalty for memories not accessed recently

        Formula:
          effective_decay_rate = decay_rate / (1 + reinforcement_factor * log(access_count + 1))
          vitality = exp(-effective_decay_rate * days_since_created) * freshness

        Properties:
          - New memory at birth (ac=0): effective_dr = decay_rate → score = 100
          - ac=10: effective_dr = decay_rate / 1.58  (half-life 58% longer)
          - ac=71: effective_dr = decay_rate / 2.07  (half-life doubled)
          - Product is ALWAYS in [0, 1] — score can never inflate beyond 100
          - A 72-day-old frequently-accessed preference still scores ~90 (meaningful signal)
          - A 72-day-old rarely-accessed preference scores ~85 (correct differentiation)

        Returns float 0.0–1.0 → multiply by 100 for stored score.
        """
        import math

        if current_time is None:
            current_time = datetime.utcnow()

        days_since_created = max(0, (current_time - self.metadata.created_at).total_seconds() / 86400)
        days_since_access = max(0, (current_time - self.metadata.last_accessed).total_seconds() / 86400)
        access_count = max(0, self.metadata.access_count)

        # Reinforcement slows decay — frequent retrieval extends the half-life.
        # This is bounded below by decay_rate (no access) and above by decay_rate/2+
        # The product exp(-eff_dr * age) is always in [0, 1].
        effective_decay_rate = self.metadata.decay_rate / (
            1.0 + self.metadata.reinforcement_factor * math.log(access_count + 1)
        )

        recency = math.exp(-effective_decay_rate * days_since_created)

        # Freshness: gentle uniform decay since last access (applied regardless
        # of access_count — a never-retrieved memory that is 1 day old is considered
        # as fresh as one accessed 1 day ago, since last_accessed defaults to created_at).
        freshness = math.exp(-0.005 * days_since_access)

        return min(1.0, max(0.0, recency * freshness))
    
    def record_access(self):
        """Record access and recompute stored score."""
        self.metadata.last_accessed = datetime.utcnow()
        self.metadata.access_count += 1
        # Recompute stored score from behavioral signals
        self.metadata.score = min(100, max(0, round(self.calculate_relevance_score() * 100)))
    
    def __str__(self) -> str:
        return f"Memory(id={self.id}, type={self.metadata.memory_type}, domain={self.metadata.domain}, content='{self.content[:50]}...')"
    
    def __repr__(self) -> str:
        return self.__str__()





from enum import Enum


class HealthStatus(Enum):
    """Memory health status based on behavioral signals."""
    HEALTHY = "healthy"
    AT_RISK = "at_risk"
    STALE = "stale"
    ORPHAN = "orphan"
