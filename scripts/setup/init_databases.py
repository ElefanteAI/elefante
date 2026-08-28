#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────
# NAME    : init_databases.py
# PURPOSE : Initialize or re-verify the configured vector store and Kuzu schema without
#           running the full installer; safe bootstrap safety check.
# WHEN    : After a Kuzu reset or vector-store recovery, to re-initialize the
#           data stores without reinstalling everything. Also run if you see
#           'collection not found' or 'schema mismatch' errors on server start.
# USAGE   : python scripts/setup/init_databases.py
# NOTES   : Idempotent — safe to re-run on already-initialized databases (will
#           verify, not double-initialize). Called automatically by install.py;
#           use this standalone only when you need DB init without a full reinstall.
# ─────────────────────────────────────────────────────────────────────────────
"""
Database initialization script for Elefante

This script initializes the configured embedded vector store and Kuzu database,
creates necessary directories, and verifies the setup.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.vector_store import get_vector_store  # noqa: E402
from src.core.graph_store import get_graph_store  # noqa: E402
from src.core.embeddings import get_embedding_service  # noqa: E402
from src.utils.logger import get_logger  # noqa: E402
from src.utils.config import get_config  # noqa: E402

os.environ["ELEFANTE_LOGGING_FORMAT"] = "text"
logger = get_logger(__name__)


async def init_vector_store():
    """Initialize the configured embedded vector store."""
    store_type = get_config().elefante.vector_store.type
    logger.info("Initializing vector store...", backend=store_type)
    
    try:
        vector_store = get_vector_store()
        stats = await vector_store.get_stats()
        
        logger.info(
            "Vector store initialized",
            collection=stats.get("collection_name"),
            count=stats.get("count", 0)
        )
        
        return True
    except Exception as e:
        logger.error(f"Failed to initialize vector store: {e}", exc_info=True)
        return False


async def init_graph_store():
    """Initialize Kuzu graph database"""
    logger.info("Initializing Kuzu graph database...")
    
    try:
        graph_store = get_graph_store()
        stats = await graph_store.get_stats()
        
        logger.info(
            "Graph store initialized",
            num_nodes=stats.get("num_nodes", 0),
            num_relationships=stats.get("num_relationships", 0)
        )
        
        return True
    except Exception as e:
        logger.error(f"Failed to initialize graph store: {e}", exc_info=True)
        return False


async def init_embedding_service():
    """Initialize embedding service"""
    logger.info("Initializing embedding service...")
    
    try:
        embedding_service = get_embedding_service()
        
        # Test embedding generation
        test_text = "Hello, Elefante!"
        embedding = await embedding_service.generate_embedding(test_text)
        
        logger.info(
            "Embedding service initialized",
            model=embedding_service.model_name,
            dimension=len(embedding)
        )
        
        return True
    except Exception as e:
        logger.error(f"Failed to initialize embedding service: {e}", exc_info=True)
        return False


async def verify_setup():
    """Verify complete system setup"""
    logger.info("Verifying system setup...")
    
    config = get_config()
    
    # Check data directories
    data_dir = Path(config.elefante.data_dir)
    vector_dir = Path(config.elefante.vector_store.persist_directory)
    graph_dir = Path(config.elefante.graph_store.database_path)
    
    logger.info(
        "Data directories",
        data_dir=str(data_dir),
        vector_dir=str(vector_dir),
        graph_dir=str(graph_dir)
    )
    
    # The active vector directory is owned by the configured backend. Kuzu
    # materializes its database path lazily when the graph store opens.
    if not data_dir.exists():
        logger.warning(f"Data directory does not exist: {data_dir}")
        data_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created data directory: {data_dir}")
    
    return True


async def inject_seed_memory():
    """Inject the First Success 'Aha!' memory"""
    logger.info("Injecting test seed memory...")
    try:
        from src.core.orchestrator import get_orchestrator
        from src.models.memory import MemoryType, DomainType
        
        orc = get_orchestrator()
        
        # Check if already seeded to avoid duplicates on re-runs
        results = await orc.search_memories(query="Indigo-Echo")
        if results and any("Indigo-Echo" in getattr(m, 'content', '') for m in results):
            logger.info("Seed memory already exists, skipping.")
            return True
            
        memory = await orc.add_memory(
            content="The secret Elefante test passcode is 'Indigo-Echo'.",
            memory_type=MemoryType.FACT,
            tags=["seed", "passcode"],
            metadata={"domain": DomainType.SYSTEM, "category": "system-test"}
        )
        if memory is None:
            rejection_reason = getattr(orc, "_last_rejection_reason", "Unknown rejection reason")
            logger.error(
                "Seed memory injection was rejected",
                reason=rejection_reason,
            )
            return False

        logger.info("Successfully injected seed memory.", memory_id=memory.id)
        return True
    except Exception as e:
        logger.error(f"Failed to inject seed memory: {e}", exc_info=True)
        return False


async def cleanup_resources():
    """Clean up database connections to prevent async cleanup errors"""
    try:
        from src.core.graph_store import get_graph_store, reset_graph_store
        graph_store = get_graph_store()
        graph_store.close()
        reset_graph_store()
    except Exception:
        pass
    
    # Give background threads a moment to complete
    await asyncio.sleep(0.1)


async def main():
    """Main initialization routine"""
    logger.info("=" * 60)
    logger.info("Elefante Database Initialization")
    logger.info("=" * 60)
    
    results = {
        "embedding_service": False,
        "vector_store": False,
        "graph_store": False,
        "verification": False,
        "seed_memory": False
    }
    
    # Initialize components
    results["embedding_service"] = await init_embedding_service()
    results["vector_store"] = await init_vector_store()
    results["graph_store"] = await init_graph_store()
    results["verification"] = await verify_setup()
    
    if all([results["embedding_service"], results["vector_store"], results["graph_store"]]):
        results["seed_memory"] = await inject_seed_memory()
    else:
        logger.warning("Skipping seed memory injection due to component failure")
    
    # Summary
    logger.info("=" * 60)
    logger.info("Initialization Summary")
    logger.info("=" * 60)
    
    for component, success in results.items():
        status = "[OK] SUCCESS" if success else "[FAIL] FAILED"
        logger.info(f"{component:20s}: {status}")
    
    all_success = all(results.values())
    
    if all_success:
        logger.info("=" * 60)
        logger.info("[OK] All components initialized successfully!")
        logger.info("=" * 60)
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Start the MCP server: python -m src.mcp.server")
        logger.info("2. Configure your IDE to use the Elefante MCP server")
        logger.info("3. Start storing and retrieving memories!")
    else:
        logger.error("=" * 60)
        logger.error("[FAIL] Some components failed to initialize")
        logger.error("=" * 60)
        logger.error("Please check the logs above for details")
    
    # Clean up resources before event loop closes
    await cleanup_resources()
    
    return 0 if all_success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
