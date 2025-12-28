import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from src.mcp.server import ElefanteMCPServer

async def list_recent_memories():
    print("📋 VERIFYING MEMORY ADDITION")
    print("----------------------------")
    
    server = ElefanteMCPServer()
    
    # We want to check if the memory we just added is there.
    # The simulated memory had content: "The user prefers to use 'safe_mode'..."
    
    # We can use the list_memories tool logic or search
    # Let's use search_memories tool logic for precision
    
    query = "safe_mode"
    print(f"Searching for '{query}'...")
    
    try:
        # Search using the server's method if possible, or orchestrator
        # The Orchestrator is what we really want to check.
        # But let's use the server handler to be consistent with the simulation
        
        # async def _handle_search_memories(self, arguments: dict)
        result = await server._handle_search_memories({"query": query, "limit": 1})
        
        print("\nSearch Result:")
        print(result)
        
        # Check if content matches
        if result and "safe_mode" in str(result):
            print("\n✅ VERIFICATION PASSED: Memory found.")
        else:
            print("\n❌ VERIFICATION FAILED: Memory not found.")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(list_recent_memories())
