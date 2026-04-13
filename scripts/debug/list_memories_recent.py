import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.core.orchestrator import get_orchestrator  # noqa: E402

async def list_recent():
    orchestrator = get_orchestrator()
    # List all (limit 100) then take the last ones since we don't have sort-by-date param exposed easily in list_all
    memories = await orchestrator.list_all_memories(limit=100)
    
    print(f"\nTotal Memories: {len(memories)}")
    print("Most Recent Entries:")
    # Assuming list_all returns in some order, likely insertion or ID. 
    # But usually, Chroma returns in insertion order if not shuffling.
    # We'll print the last 10.
    recent = memories[-10:]
    for mem in recent:
        print(f"[{mem.metadata.memory_type}.{mem.metadata.domain}] ({mem.id})")
        print(f"   {mem.content[:150]}...")
        print("-" * 40)

if __name__ == "__main__":
    asyncio.run(list_recent())
