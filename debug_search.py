#!/usr/bin/env python3
"""Debug script to investigate search issue"""

import asyncio
from src.core.orchestrator import get_orchestrator
from src.models.query import QueryMode

async def debug_search():
    """Debug why search returns 0 results"""
    
    orchestrator = get_orchestrator()
    
    print("=" * 70)
    print("DEBUGGING SEARCH ISSUE")
    print("=" * 70)
    
    # Get stats
    stats = await orchestrator.get_stats()
    print(f"\nVector Store: {stats['vector_store']['total_memories']} memories")
    print(f"Graph Store: {stats['graph_store']['total_entities']} entities")
    
    # Try different search queries
    queries = [
        "CRITICAL OPERATIONAL RULE",
        "user approval",
        "testing",
        "decision",
        "workflow"
    ]
    
    for query in queries:
        print(f"\n--- Query: '{query}' ---")
        results = await orchestrator.search_memories(
            query=query,
            mode=QueryMode.SEMANTIC,
            limit=5,
            include_conversation=False,
            include_stored=True
        )
        print(f"Results: {len(results)}")
        if results:
            for r in results[:2]:
                print(f"  - {r.memory.content[:80]}... (score: {r.score:.3f})")
    
    # Try direct vector store search
    print(f"\n--- Direct vector store search ---")
    try:
        direct_results = await orchestrator.vector_store.search(
            query="operational rule",
            limit=5
        )
        print(f"Retrieved {len(direct_results)} results")
        for r in direct_results:
            print(f"  - ID: {r.memory.id}")
            print(f"    Content: {r.memory.content[:80]}...")
            print(f"    Score: {r.score:.3f}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_search())

# Made with Bob
