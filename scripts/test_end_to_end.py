#!/usr/bin/env python3
"""
End-to-end validation test for Elefante Memory System

This script validates the complete system by:
1. Initializing databases
2. Storing memories
3. Performing searches
4. Verifying results
5. Testing all major features
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.orchestrator import get_orchestrator
from src.models.query import QueryMode
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_add_memory():
    """Test adding a memory"""
    logger.info("=" * 60)
    logger.info("TEST 1: Add Memory")
    logger.info("=" * 60)
    
    try:
        orchestrator = get_orchestrator()
        
        memory = await orchestrator.add_memory(
            content="Elefante is a dual-database AI memory system combining ChromaDB for semantic search and Kuzu for structured queries.",
            memory_type="fact",
            importance=10,
            tags=["elefante", "architecture", "database"],
            entities=[
                {"name": "Elefante", "type": "project"},
                {"name": "ChromaDB", "type": "technology"},
                {"name": "Kuzu", "type": "technology"}
            ],
            metadata={
                "author": "Jaime",
                "context": "system_test"
            }
        )
        
        logger.info(f"✓ Memory created: {memory.id}")
        logger.info(f"  Content: {memory.content[:80]}...")
        logger.info(f"  Type: {memory.metadata.memory_type}")
        logger.info(f"  Importance: {memory.metadata.importance}")
        logger.info(f"  Tags: {memory.metadata.tags}")
        
        return True, memory.id
        
    except Exception as e:
        logger.error(f"✗ Failed to add memory: {e}", exc_info=True)
        return False, None


async def test_semantic_search():
    """Test semantic search"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: Semantic Search")
    logger.info("=" * 60)
    
    try:
        orchestrator = get_orchestrator()
        
        results = await orchestrator.search_memories(
            query="What is Elefante?",
            mode=QueryMode.SEMANTIC,
            limit=5
        )
        
        logger.info(f"✓ Found {len(results)} results")
        
        for i, result in enumerate(results[:3], 1):
            logger.info(f"\n  Result {i}:")
            logger.info(f"    Score: {result.score:.3f}")
            logger.info(f"    Content: {result.memory.content[:80]}...")
            logger.info(f"    Source: {result.source}")
        
        return True, len(results)
        
    except Exception as e:
        logger.error(f"✗ Semantic search failed: {e}", exc_info=True)
        return False, 0


async def test_hybrid_search():
    """Test hybrid search"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Hybrid Search")
    logger.info("=" * 60)
    
    try:
        orchestrator = get_orchestrator()
        
        results = await orchestrator.search_memories(
            query="database architecture",
            mode=QueryMode.HYBRID,
            limit=5
        )
        
        logger.info(f"✓ Found {len(results)} results")
        
        for i, result in enumerate(results[:3], 1):
            logger.info(f"\n  Result {i}:")
            logger.info(f"    Score: {result.score:.3f}")
            logger.info(f"    Vector Score: {result.vector_score}")
            logger.info(f"    Graph Score: {result.graph_score}")
            logger.info(f"    Content: {result.memory.content[:80]}...")
        
        return True, len(results)
        
    except Exception as e:
        logger.error(f"✗ Hybrid search failed: {e}", exc_info=True)
        return False, 0


async def test_entity_creation():
    """Test entity and relationship creation"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 4: Entity & Relationship Creation")
    logger.info("=" * 60)
    
    try:
        orchestrator = get_orchestrator()
        
        # Create entities
        entity1 = await orchestrator.create_entity(
            name="Bob",
            entity_type="person",
            properties={"role": "AI Assistant"}
        )
        
        entity2 = await orchestrator.create_entity(
            name="Jaime",
            entity_type="person",
            properties={"role": "Developer"}
        )
        
        logger.info(f"✓ Created entity: {entity1.name} ({entity1.type})")
        logger.info(f"✓ Created entity: {entity2.name} ({entity2.type})")
        
        # Create relationship
        relationship = await orchestrator.create_relationship(
            from_entity_id=entity1.id,
            to_entity_id=entity2.id,
            relationship_type="relates_to",
            properties={"context": "collaboration"}
        )
        
        logger.info(f"✓ Created relationship: {entity1.name} -> {entity2.name}")
        
        return True, (entity1.id, entity2.id)
        
    except Exception as e:
        logger.error(f"✗ Entity creation failed: {e}", exc_info=True)
        return False, None


async def test_get_context():
    """Test context retrieval"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 5: Context Retrieval")
    logger.info("=" * 60)
    
    try:
        orchestrator = get_orchestrator()
        
        context = await orchestrator.get_context(
            depth=2,
            limit=10
        )
        
        logger.info(f"✓ Retrieved context:")
        logger.info(f"  Memories: {context['stats']['num_memories']}")
        logger.info(f"  Entities: {context['stats']['num_entities']}")
        logger.info(f"  Depth: {context['stats']['depth']}")
        
        return True, context
        
    except Exception as e:
        logger.error(f"✗ Context retrieval failed: {e}", exc_info=True)
        return False, None


async def test_system_stats():
    """Test system statistics"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 6: System Statistics")
    logger.info("=" * 60)
    
    try:
        orchestrator = get_orchestrator()
        
        stats = await orchestrator.get_stats()
        
        logger.info("✓ System Statistics:")
        logger.info(f"\n  Vector Store:")
        logger.info(f"    Collection: {stats['vector_store'].get('collection_name')}")
        logger.info(f"    Count: {stats['vector_store'].get('count', 0)}")
        
        logger.info(f"\n  Graph Store:")
        logger.info(f"    Nodes: {stats['graph_store'].get('num_nodes', 0)}")
        logger.info(f"    Relationships: {stats['graph_store'].get('num_relationships', 0)}")
        
        logger.info(f"\n  Orchestrator:")
        logger.info(f"    Status: {stats['orchestrator']['status']}")
        
        return True, stats
        
    except Exception as e:
        logger.error(f"✗ Stats retrieval failed: {e}", exc_info=True)
        return False, None


async def main():
    """Run all end-to-end tests"""
    logger.info("=" * 60)
    logger.info("ELEFANTE END-TO-END VALIDATION TEST")
    logger.info(f"Timestamp: {datetime.utcnow().isoformat()}")
    logger.info("=" * 60)
    
    results = {}
    
    # Run tests
    results["add_memory"] = await test_add_memory()
    results["semantic_search"] = await test_semantic_search()
    results["hybrid_search"] = await test_hybrid_search()
    results["entity_creation"] = await test_entity_creation()
    results["get_context"] = await test_get_context()
    results["system_stats"] = await test_system_stats()
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, (success, _) in results.items():
        status = "✓ PASS" if success else "✗ FAIL"
        logger.info(f"{test_name:20s}: {status}")
        if success:
            passed += 1
        else:
            failed += 1
    
    logger.info("\n" + "=" * 60)
    logger.info(f"Results: {passed} passed, {failed} failed")
    logger.info("=" * 60)
    
    if failed == 0:
        logger.info("\n🎉 ALL TESTS PASSED!")
        logger.info("Elefante is working end-to-end!")
        logger.info("\nNext steps:")
        logger.info("1. Start MCP server: python -m src.mcp.server")
        logger.info("2. Configure your IDE to use Elefante")
        logger.info("3. Start using persistent AI memory!")
        return 0
    else:
        logger.error(f"\n✗ {failed} test(s) failed")
        logger.error("Please check the logs above for details")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)


# Made with Bob