#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────
# NAME    : verify_health.py
# PURPOSE : Structural health check for the core engine: paths, imports, config,
#           and baseline readiness without mutating any durable data.
# WHEN    : First check after any install or reinstall. After config.yaml changes.
#           When any core import fails or Elefante refuses to start — run this
#           before reaching for deeper diagnostics. Fastest non-destructive check.
# USAGE   : python scripts/verify/verify_health.py
# NOTES   : Does NOT start the MCP server or open databases. If this passes but
#           the server still fails, move to verify_mcp_handshake.py. If that fails
#           too, run verify_e2e_tests.py for the full surface diagnosis.
# ─────────────────────────────────────────────────────────────────────────────
"""
Health check script for Elefante Memory System

Verifies that all components are operational and reports system status.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.directive_store import (  # noqa: E402
    CLIENT_SYSTEM_DIRECTIVE_DEFINITIONS,
    SYSTEM_DIRECTIVE_DEFINITIONS,
    get_directive_store,
)
from src.core.orchestrator import SYSTEM_SPECIFICATIONS, get_orchestrator  # noqa: E402
from src.utils.logger import get_logger  # noqa: E402
from src.utils.config import get_config  # noqa: E402
from src.utils.runtime_profile import is_client_runtime  # noqa: E402

logger = get_logger(__name__)


async def check_orchestrator():
    """Check orchestrator health"""
    try:
        orchestrator = get_orchestrator()
        await orchestrator.ensure_system_baseline()
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


async def check_system_baseline():
    """Verify the customer or developer baseline selected by the runtime profile."""
    try:
        orchestrator = get_orchestrator()
        await orchestrator.ensure_system_baseline()

        directive_store = get_directive_store()
        directives = directive_store.list_all()
        client_runtime = is_client_runtime()
        expected_definitions = (
            CLIENT_SYSTEM_DIRECTIVE_DEFINITIONS
            if client_runtime
            else SYSTEM_DIRECTIVE_DEFINITIONS
        )
        expected_ids = {directive_id for directive_id, _ in expected_definitions}
        present_ids = {directive.get("id") for directive in directives}
        missing_directives = sorted(expected_ids.difference(present_ids))

        if client_runtime:
            leaked_developer_directives = sorted(
                directive_id
                for directive_id in present_ids
                if isinstance(directive_id, str) and directive_id.startswith("system-sdd-")
            )
            healthy = not missing_directives and not leaked_developer_directives
            result = {
                "status": "healthy" if healthy else "unhealthy",
                "profile": "client",
                "system_directives": len(expected_ids) - len(missing_directives),
                "missing_directives": missing_directives,
                "developer_directives": leaked_developer_directives,
                "specifications": "not-applicable",
            }
            if not healthy:
                result["error"] = "Customer runtime baseline is incomplete or contains developer directives"
            return result

        sdd_gate_count = sum(1 for directive in directives if directive.get("content", "").startswith("SDD "))
        stdout_purity_present = any("STDOUT" in directive.get("content", "") for directive in directives)

        missing_specifications = []
        for specification in SYSTEM_SPECIFICATIONS:
            memory = await orchestrator.vector_store.find_by_title(specification["title"])
            if memory is None:
                missing_specifications.append(specification["title"])
                continue

            memory_type = memory.metadata.memory_type
            if hasattr(memory_type, "value"):
                memory_type = memory_type.value
            if str(memory_type).lower() != "specification":
                missing_specifications.append(specification["title"])

        healthy = (
            not missing_directives
            and sdd_gate_count >= 5
            and stdout_purity_present
            and not missing_specifications
        )

        result = {
            "status": "healthy" if healthy else "unhealthy",
            "profile": "developer",
            "total_directives": directive_store.count(),
            "missing_directives": missing_directives,
            "sdd_directives": sdd_gate_count,
            "stdout_purity_present": stdout_purity_present,
            "specifications": len(SYSTEM_SPECIFICATIONS) - len(missing_specifications),
            "missing_specifications": missing_specifications,
        }
        if not healthy:
            result["error"] = "Developer runtime baseline is incomplete"
        return result
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
        "System Baseline": check_system_baseline(),
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
        symbol = "[OK]" if status == "healthy" else "[FAIL]"
        
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
        logger.info("[OK] All systems operational!")
        logger.info("=" * 60)
    else:
        logger.error("[FAIL] Some systems are unhealthy")
        logger.error("=" * 60)
    
    # Clean up resources before event loop closes
    await cleanup_resources()
    
    return 0 if all_healthy else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
