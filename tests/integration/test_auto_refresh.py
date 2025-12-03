"""
Test script to verify dashboard auto-refresh functionality.
Adds a test memory and checks if it appears without server restart.
"""
import asyncio
from src.core.orchestrator import MemoryOrchestrator

async def test_auto_refresh():
    """Add a test memory to verify dashboard auto-refresh."""
    orchestrator = MemoryOrchestrator()
    
    print("\n" + "="*70)
    print("TESTING DASHBOARD AUTO-REFRESH FEATURE")
    print("="*70)
    
    # Get current stats
    stats = await orchestrator.get_stats()
    current_count = stats['vector_store']['total_memories']
    print(f"\nCurrent memory count: {current_count}")
    
    # Add test memory
    print("\nAdding test memory...")
    result = await orchestrator.add_memory(
        content="TEST MEMORY: Dashboard auto-refresh verification at 2025-11-28 22:34 UTC. This memory should appear in the dashboard without server restart.",
        memory_type="note",
        importance=5,
        tags=["test", "auto-refresh", "verification"]
    )
    
    print(f"✓ Test memory added: {result.id}")
    
    # Verify new count
    stats = await orchestrator.get_stats()
    new_count = stats['vector_store']['total_memories']
    print(f"New memory count: {new_count}")
    
    if new_count == current_count + 1:
        print("\n✅ SUCCESS: Memory added to database")
        print("\n📋 NEXT STEP: Refresh the dashboard in your browser (F5)")
        print("   The new memory should appear WITHOUT restarting the server.")
        print("   Look for: 'TEST MEMORY: Dashboard auto-refresh...'")
    else:
        print("\n❌ FAILED: Memory count did not increase")
    
    print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(test_auto_refresh())

# Made with Bob
