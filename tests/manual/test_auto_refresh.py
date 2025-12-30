"""Manual script to verify dashboard auto-refresh functionality.

Read-only by default. Use --write-test-memory to actually write a test memory.
"""
import asyncio
import os
import sys
from src.core.orchestrator import MemoryOrchestrator

import pytest

async def _run_auto_refresh():
    """Add a test memory to verify dashboard auto-refresh."""
    write_test_memory = "--write-test-memory" in sys.argv
    orchestrator = MemoryOrchestrator()
    
    print("\n" + "=" * 70)
    print("TESTING DASHBOARD AUTO-REFRESH FEATURE")
    print("=" * 70)
    
    # Get current stats
    stats = await orchestrator.get_stats()
    current_count = stats['vector_store']['total_memories']
    print(f"\nCurrent memory count: {current_count}")
    
    if not write_test_memory:
        print("\nSkipping test-memory write (read-only mode).")
        print("Run with: --write-test-memory (writes to current DB).")
        print("=" * 70 + "\n")
        return

    os.environ.setdefault("ELEFANTE_ALLOW_TEST_MEMORIES", "1")
    print("\nAdding test memory (explicit flag enabled)...")
    result = await orchestrator.add_memory(
        content=(
            "TEST MEMORY: Dashboard auto-refresh verification at 2025-11-28 22:34 UTC. "
            "This memory should appear in the dashboard without server restart."
        ),
        memory_type="note",
        importance=5,
        tags=["test", "auto-refresh", "verification"],
        metadata={"namespace": "test", "category": "test"},
    )

    print(f"Test memory add result: {getattr(result, 'id', None)}")
    
    # Verify new count
    stats = await orchestrator.get_stats()
    new_count = stats['vector_store']['total_memories']
    print(f"New memory count: {new_count}")
    
    if new_count == current_count + 1:
        print("\nMemory added to database.")
        print("Next step: refresh the dashboard in your browser.")
        print("Look for: 'TEST MEMORY: Dashboard auto-refresh...'")
    else:
        print("\nMemory count did not increase.")
    
    print("=" * 70 + "\n")


def test_auto_refresh():
    pytest.skip("Manual verification script; run this module directly to execute")

if __name__ == "__main__":
    asyncio.run(_run_auto_refresh())

