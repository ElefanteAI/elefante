"""
Elefante - Local AI Memory System

A dual-database memory system combining embedded semantic search
with structured knowledge graphs (Kuzu) for comprehensive AI memory.
"""

__version__ = "2.15.2"
__author__ = "Elefante Contributors"

# Keep package import dependency-free. Installer preflight imports small,
# standard-library-only modules before the product environment exists.
# Public conveniences remain available through lazy attribute loading.


def __getattr__(name: str):
    if name in {"Memory", "MemoryType"}:
        from src.models.memory import Memory, MemoryType

        return {"Memory": Memory, "MemoryType": MemoryType}[name]
    if name in {"Entity", "Relationship"}:
        from src.models.entity import Entity, Relationship

        return {"Entity": Entity, "Relationship": Relationship}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def get_orchestrator():
    """Lazy import to prevent database lock on package load"""
    from src.core.orchestrator import get_orchestrator as _get

    return _get()


__all__ = [
    "get_orchestrator",  # Function instead of class
    "Memory",
    "MemoryType",
    "Entity",
    "Relationship",
]
