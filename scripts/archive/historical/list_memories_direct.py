import sys
import os
import asyncio
from typing import List

# Add root to path
sys.path.append(os.getcwd())

# Set environment to use local .env if needed
from dotenv import load_dotenv
load_dotenv()

from src.core.orchestrator import get_orchestrator
from src.models.query import SearchFilters

async def list_memories():
    try:
        print("Initializing Orchestrator...")
        orchestrator = get_orchestrator()
        
        print("Fetching memories...")
        memories = await orchestrator.list_all_memories(limit=20)
        
        print(f"\nFound {len(memories)} memories:")
        for mem in memories:
            print(f"- [{mem.metadata.layer}.{mem.metadata.sublayer}] {mem.content[:100]}...")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(list_memories())
