"""
Test script to verify memory persistence across sessions
"""
import asyncio
import sys
import io
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
    print("="*70)
    print("🐘 ELEFANTE MEMORY PERSISTENCE TEST")
    print("="*70)
    
    # Initialize orchestrator
    orch = get_orchestrator()
    
    # Get current stats
    print("\n📊 Current Database State:")
    stats = await orch.get_stats()
    print(f"  Vector Store Memories: {stats['vector_store']['total_memories']}")
    print(f"  Graph Entities: {stats['graph_store']['total_entities']}")
    print(f"  Graph Relationships: {stats['graph_store']['total_relationships']}")
    
    # Search for the dog memory
    print("\n🔍 Searching for 'Jaime dog preferences'...")
    results = await orch.search_memories(
        query="Jaime likes Chihuahuas dogs Marty Emmett",
        mode=QueryMode.HYBRID,
        limit=5
    )
    
    if results:
        print(f"\n✅ Found {len(results)} matching memories:")
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
        print("\n❌ No memories found!")
        print("\nThis means the memory was NOT persisted to the database.")
        print("Possible causes:")
        print("  1. The addMemory tool call failed silently")
        print("  2. The MCP server is using a different database location")
        print("  3. The memory was stored in a different session's temporary context")
    
    # Try to add a test memory
    print("\n\n📝 Adding test memory...")
    memory_id = await orch.add_memory(
        content="TEST: This is a persistence test memory added at session startup.",
        memory_type=MemoryType.NOTE,
        importance=5,
        tags=["test", "persistence_check"]
    )
    print(f"✅ Test memory added with ID: {memory_id}")
    
    # Verify it was stored
    print("\n🔍 Verifying test memory was stored...")
    test_results = await orch.search_memories(
        query="persistence test memory",
        mode=QueryMode.HYBRID,
        limit=1
    )
    
    if test_results:
        print("✅ Test memory successfully stored and retrieved!")
    else:
        print("❌ Test memory was NOT found after storage!")
    
    print("\n" + "="*70)
    print("Test complete. Check results above.")
    print("="*70)

if __name__ == "__main__":
    asyncio.run(main())

# Made with Bob
