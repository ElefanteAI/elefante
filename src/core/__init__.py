"""Core services for Elefante memory system.

The package initializer stays dependency-free so installer preflight can import
small core modules before the product virtual environment is populated.
"""


def __getattr__(name: str):
    if name in {"EmbeddingService", "get_embedding_service"}:
        from src.core.embeddings import EmbeddingService, get_embedding_service

        return {
            "EmbeddingService": EmbeddingService,
            "get_embedding_service": get_embedding_service,
        }[name]
    if name in {"VectorStore", "get_vector_store"}:
        from src.core.vector_store import VectorStore, get_vector_store

        return {"VectorStore": VectorStore, "get_vector_store": get_vector_store}[name]
    if name in {"GraphStore", "get_graph_store"}:
        from src.core.graph_store import GraphStore, get_graph_store

        return {"GraphStore": GraphStore, "get_graph_store": get_graph_store}[name]
    if name in {"MemoryOrchestrator", "get_orchestrator"}:
        from src.core.orchestrator import MemoryOrchestrator, get_orchestrator

        return {
            "MemoryOrchestrator": MemoryOrchestrator,
            "get_orchestrator": get_orchestrator,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "EmbeddingService",
    "get_embedding_service",
    "VectorStore",
    "get_vector_store",
    "GraphStore",
    "get_graph_store",
    "MemoryOrchestrator",
    "get_orchestrator",
]
