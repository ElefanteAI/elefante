"""
Standardized Metadata Schema
----------------------------
Defines the strict schema for memory metadata to ensure data quality and consistency.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field

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

class MemorySource(str, Enum):
    """Source of the memory"""
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"
    EXTERNAL = "external"

class CoreMetadata(BaseModel):
    """Core identity and classification metadata"""
    memory_type: MemoryType = Field(default=MemoryType.CONVERSATION, description="The fundamental type of the memory")
    source: MemorySource = Field(default=MemorySource.USER, description="Origin of the memory")
    importance: int = Field(default=50, ge=0, le=100, description="Behavioral relevance score (0-100)")
    tags: List[str] = Field(default_factory=list, description="Taxonomic tags")

class ContextMetadata(BaseModel):
    """Contextual grounding metadata"""
    session_id: Optional[UUID] = Field(default=None, description="Session where this occurred")
    project: Optional[str] = Field(default=None, description="Associated project name")
    file_path: Optional[str] = Field(default=None, description="Associated file path")
    line_number: Optional[int] = Field(default=None, description="Associated line number")
    parent_id: Optional[UUID] = Field(default=None, description="Parent memory ID for threading")

class SystemMetadata(BaseModel):
    """System-level tracking metadata"""
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    version: int = Field(default=1, description="Schema version")
    processing_time_ms: Optional[float] = Field(default=None, description="Processing latency")
    hash: Optional[str] = Field(default=None, description="Content hash for integrity")

class StandardizedMetadata(BaseModel):
    """
    The Master Metadata Schema
    Combines Core, Context, and System metadata into a single, validated structure.
    """
    core: CoreMetadata = Field(default_factory=CoreMetadata)
    context: ContextMetadata = Field(default_factory=ContextMetadata)
    system: SystemMetadata = Field(default_factory=SystemMetadata)
    custom: Dict[str, Any] = Field(default_factory=dict, description="Extensible custom fields")

    model_config = ConfigDict()
