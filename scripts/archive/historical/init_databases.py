#!/usr/bin/env python3
"""
Database initialization script for Elefante

This script initializes both ChromaDB and Kuzu databases,
creates necessary directories, and verifies the setup.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.vector_store import get_vector_store
from src.core.graph_store import get_graph_store
from src.core.embeddings import get_embedding_service
from src.utils.logger import get_logger
from src.utils.config import get_config

logger = get_logger(__name__)


async def init_vector_store():
    """Initialize ChromaDB vector store"""
    logger.info("Initializing ChromaDB vector store...")
    
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
    vector_dir = data_dir / "chroma"
    graph_dir = data_dir / "kuzu"
    
    logger.info(
        "Data directories",
        data_dir=str(data_dir),
        vector_dir=str(vector_dir),
        graph_dir=str(graph_dir)
    )
    
    # Verify directories exist
    if not data_dir.exists():
        logger.warning(f"Data directory does not exist: {data_dir}")
        data_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created data directory: {data_dir}")
    
    return True


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
        "verification": False
    }
    
    # Initialize components
    results["embedding_service"] = await init_embedding_service()
    results["vector_store"] = await init_vector_store()
    results["graph_store"] = await init_graph_store()
    results["verification"] = await verify_setup()
    
    # Summary
    logger.info("=" * 60)
    logger.info("Initialization Summary")
    logger.info("=" * 60)
    
    for component, success in results.items():
        status = "✓ SUCCESS" if success else "✗ FAILED"
        logger.info(f"{component:20s}: {status}")
    
    all_success = all(results.values())
    
    if all_success:
        logger.info("=" * 60)
        logger.info("✓ All components initialized successfully!")
        logger.info("=" * 60)
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Start the MCP server: python -m src.mcp.server")
        logger.info("2. Configure your IDE to use the Elefante MCP server")
        logger.info("3. Start storing and retrieving memories!")
    else:
        logger.error("=" * 60)
        logger.error("✗ Some components failed to initialize")
        logger.error("=" * 60)
        logger.error("Please check the logs above for details")
    
    # Clean up resources before event loop closes
    await cleanup_resources()
    
    return 0 if all_success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)


# Made with Bob