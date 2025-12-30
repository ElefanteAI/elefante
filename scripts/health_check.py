#!/usr/bin/env python3
"""
Health check script for Elefante Memory System

Verifies that all components are operational and reports system status.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.orchestrator import get_orchestrator
from src.utils.logger import get_logger
from src.utils.config import get_config

logger = get_logger(__name__)


async def check_orchestrator():
    """Check orchestrator health"""
    try:
        orchestrator = get_orchestrator()
        stats = await orchestrator.get_stats()
        
        return {
            "status": "healthy",
            "stats": stats
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


async def check_vector_store():
    """Check vector store health"""
    try:
        from src.core.vector_store import get_vector_store
        
        vector_store = get_vector_store()
        stats = await vector_store.get_stats()

        count = (
            stats.get("total_memories")
            if stats.get("total_memories") is not None
            else stats.get("count", 0)
        )
        
        return {
            "status": "healthy",
            "collection": stats.get("collection_name"),
            "count": count,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


async def check_graph_store():
    """Check graph store health"""
    try:
        from src.core.graph_store import get_graph_store
        
        graph_store = get_graph_store()
        stats = await graph_store.get_stats()

        nodes = (
            stats.get("total_entities")
            if stats.get("total_entities") is not None
            else stats.get("num_nodes", 0)
        )
        relationships = (
            stats.get("total_relationships")
            if stats.get("total_relationships") is not None
            else stats.get("num_relationships", 0)
        )
        
        return {
            "status": "healthy",
            "nodes": nodes,
            "relationships": relationships,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


async def check_embedding_service():
    """Check embedding service health"""
    try:
        from src.core.embeddings import get_embedding_service
        
        service = get_embedding_service()
        
        # Test embedding generation
        test_embedding = await service.generate_embedding("test")
        
        return {
            "status": "healthy",
            "model": service.model_name,
            "dimension": len(test_embedding)
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


async def check_configuration():
    """Check configuration"""
    try:
        config = get_config()
        
        return {
            "status": "healthy",
            "data_dir": config.elefante.data_dir
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


async def cleanup_resources():
    """Clean up database connections to prevent async cleanup errors"""
    try:
        # Close graph store connection
        from src.core.graph_store import get_graph_store, reset_graph_store
        graph_store = get_graph_store()
        graph_store.close()
        reset_graph_store()
    except Exception:
        pass
    
    # Give background threads a moment to complete
    await asyncio.sleep(0.1)


async def main():
    """Run health checks"""
    logger.info("=" * 60)
    logger.info("Elefante Health Check")
    logger.info(f"Timestamp: {datetime.utcnow().isoformat()}")
    logger.info("=" * 60)
    
    checks = {
        "Configuration": check_configuration(),
        "Embedding Service": check_embedding_service(),
        "Vector Store": check_vector_store(),
        "Graph Store": check_graph_store(),
        "Orchestrator": check_orchestrator()
    }
    
    results = {}
    for name, check_coro in checks.items():
        logger.info(f"\nChecking {name}...")
        results[name] = await check_coro
    
    # Print results
    logger.info("\n" + "=" * 60)
    logger.info("Health Check Results")
    logger.info("=" * 60)
    
    all_healthy = True
    for name, result in results.items():
        status = result["status"]
        symbol = "✓" if status == "healthy" else "✗"
        
        logger.info(f"\n{symbol} {name}: {status.upper()}")
        
        if status == "healthy":
            for key, value in result.items():
                if key != "status":
                    logger.info(f"  - {key}: {value}")
        else:
            logger.error(f"  Error: {result.get('error', 'Unknown error')}")
            all_healthy = False
    
    logger.info("\n" + "=" * 60)
    
    if all_healthy:
        logger.info("✓ All systems operational!")
        logger.info("=" * 60)
    else:
        logger.error("✗ Some systems are unhealthy")
        logger.error("=" * 60)
    
    # Clean up resources before event loop closes
    await cleanup_resources()
    
    return 0 if all_healthy else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)


