"""
Task models for the Orchestration Engine
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"

class Task(BaseModel):
    id: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime
    updated_at: datetime
    assigned_agent: Optional[str] = None
    priority: int = 1
    
    # Relationships aren't stored in the node model directly but help with API
    subtasks: List[str] = [] # List of subtask IDs
    blocked_by: List[str] = [] # List of dependency IDs
