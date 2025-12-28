"""
Test script to verify memory persistence across sessions
"""
import asyncio
import sys
import io
import os
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.core.orchestrator import get_orchestrator
from src.models.memory import MemoryType
from src.models.query import QueryMode

async def main():
    write_test_memory = "--write-test-memory" in sys.argv

    print("="*70)
    print("ELEFANTE MEMORY PERSISTENCE TEST")
    print("="*70)
    
    # Initialize orchestrator
    orch = get_orchestrator()
    
    # Get current stats
    print("\nCurrent Database State:")
    stats = await orch.get_stats()
    print(f"  Vector Store Memories: {stats['vector_store']['total_memories']}")
    print(f"  Graph Entities: {stats['graph_store']['total_entities']}")
    print(f"  Graph Relationships: {stats['graph_store']['total_relationships']}")
    
    # Search for the dog memory
    print("\nSearching for 'Jaime dog preferences'...")
    results = await orch.search_memories(
        query="Jaime likes Chihuahuas dogs Marty Emmett",
        mode=QueryMode.HYBRID,
        limit=5
    )
    
    if results:
        print(f"\nFound {len(results)} matching memories:")
        for i, result in enumerate(results, 1):
            print(f"\n  Memory {i}:")
            print(f"    Content: {result.memory.content[:100]}...")
            print(f"    Type: {result.memory.metadata.memory_type}")
            print(f"    Importance: {result.memory.metadata.importance}")
            print(f"    Timestamp: {result.memory.metadata.timestamp}")
            print(f"    Score: {result.score}")
            if result.memory.metadata.tags:
                print(f"    Tags: {', '.join(result.memory.metadata.tags)}")
    else:
        print("\nNo memories found!")
        print("\nThis means the memory was NOT persisted to the database.")
        print("Possible causes:")
        print("  1. The elefanteMemoryAdd tool call failed silently")
        print("  2. The MCP server is using a different database location")
        print("  3. The memory was stored in a different session's temporary context")
    
    if write_test_memory:
        # This writes to the currently-configured DB. Keep it explicit.
        os.environ.setdefault("ELEFANTE_ALLOW_TEST_MEMORIES", "1")
        print("\n\nAdding test memory (explicit flag enabled)...")
        memory = await orch.add_memory(
            content="TEST: This is a persistence test memory added at session startup.",
            memory_type=MemoryType.NOTE,
            importance=5,
            tags=["test", "persistence_check"],
            metadata={"namespace": "test", "category": "test"},
        )
        print(f"Test memory add result: {getattr(memory, 'id', None)}")

        # Verify it was stored
        print("\nVerifying test memory was stored...")
        test_results = await orch.search_memories(
            query="persistence test memory",
            mode=QueryMode.HYBRID,
            limit=1
        )

        if test_results:
            print("Test memory was stored and retrieved.")
        else:
            print("Test memory was NOT found after storage.")
    else:
        print("\n\nSkipping test-memory write (read-only mode).")
        print("Run with: --write-test-memory (writes to current DB).")
    
    print("\n" + "="*70)
    print("Test complete. Check results above.")
    print("="*70)

if __name__ == "__main__":
    asyncio.run(main())

# Made with Bob
