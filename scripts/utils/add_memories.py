"""
Script to add user preference memories to Elefante
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.core.orchestrator import get_orchestrator

async def add_user_preferences():
    """Add memories about user preferences from recent interactions"""
    
    orchestrator = get_orchestrator()
    
    memories = [
        {
            "content": "User strongly dislikes regression in results. When fixing issues, ensure that previously working functionality is not broken. Always verify the complete user experience before claiming something is fixed.",
            "memory_type": "insight",
            "importance": 9,
            "tags": ["user_preference", "quality_standards", "testing", "regression"]
        },
        {
            "content": "User expects proactive problem-solving. Do not wait for user to discover issues - test thoroughly and verify end-to-end functionality before declaring success.",
            "memory_type": "insight",
            "importance": 9,
            "tags": ["user_preference", "proactive", "testing", "quality"]
        },
        {
            "content": "User prefers complete solutions over incremental half-fixes. Avoid claiming 'it works' without actually testing the full user-facing experience.",
            "memory_type": "insight",
            "importance": 8,
            "tags": ["user_preference", "completeness", "quality_standards"]
        },
        {
            "content": "When debugging, user expects deep investigation and root cause analysis, not surface-level fixes that may break other things.",
            "memory_type": "insight",
            "importance": 8,
            "tags": ["user_preference", "debugging", "root_cause_analysis"]
        },
        {
            "content": "User name: Jaime. Working on Elefante memory system installation and dashboard debugging. Located in Toronto timezone (UTC-5).",
            "memory_type": "fact",
            "importance": 7,
            "tags": ["user_info", "context", "project"]
        }
    ]
    
    print("Adding user preference memories...")
    print("=" * 60)
    
    for i, mem in enumerate(memories, 1):
        try:
            result = await orchestrator.add_memory(
                content=mem["content"],
                memory_type=mem["memory_type"],
                importance=mem["importance"],
                tags=mem["tags"]
            )
            print(f"[OK] Memory {i}/{len(memories)} added: {result}")
        except Exception as e:
            print(f"[FAIL] Failed to add memory {i}: {e}")
    
    print("=" * 60)
    print("Memory addition complete!")
    
    # Verify memories were added
    print("\nVerifying memories...")
    stats = await orchestrator.get_stats()
    print(f"Total memories in system: {stats.get('vector_store', {}).get('total_memories', 0)}")
    print(f"Total entities in graph: {stats.get('graph_store', {}).get('total_entities', 0)}")

if __name__ == "__main__":
    asyncio.run(add_user_preferences())

# Made with Bob
