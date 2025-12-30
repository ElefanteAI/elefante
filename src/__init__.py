"""
Elefante - Local AI Memory System

A dual-database memory system combining semantic search (ChromaDB)
with structured knowledge graphs (Kuzu) for comprehensive AI memory.
"""

__version__ = "1.6.3"
__author__ = "Your Name"

# LAW #1 ENFORCEMENT: Do NOT import orchestrator at package level
# This causes Kuzu initialization and database locking
# Use lazy imports instead

# from src.core.orchestrator import MemoryOrchestrator  # DISABLED - causes lock
from src.models.memory import Memory, MemoryType
from src.models.entity import Entity, Relationship


def get_orchestrator():
    """Lazy import to prevent database lock on package load"""
    from src.core.orchestrator import MemoryOrchestrator, get_orchestrator as _get
    return _get()


__all__ = [
    "get_orchestrator",  # Function instead of class
    "Memory",
    "MemoryType",
    "Entity",
    "Relationship",
]

