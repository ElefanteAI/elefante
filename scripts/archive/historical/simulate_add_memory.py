import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from src.mcp.server import ElefanteMCPServer
from src.core.graph_store import GraphStore

async def simulate_add_memory():
    print("🤖 SIMULATING ADD MEMORY (Debugging Lock/Crash)")
    print("---------------------------------------------")
    
    # 1. Initialize Server (which initializes GraphStore)
    print("1. Initializing MCP Server...")
    try:
        server = ElefanteMCPServer()
        # Manually initialize graph store to check for locks/errors immediately
        print("   - accessible attributes:", dir(server))
        # Accessing private attr for debug, assuming it exists or is internal
        # Actually server initializes orchestrated which has graph_store.
        # But let's try to add memory via the tool handler directly.
        
    except Exception as e:
        print(f"❌ CRITICAL: Server initialization failed: {e}")
        return

    # 2. Prepare Payload
    print("\n2. Preparing Payload...")
    content = "The user prefers to use 'safe_mode' when deploying to production."
    args = {
        "content": content,
        "layer": "self",
        "sublayer": "preference",
        "importance": 9,
        "tags": ["deployment", "safety"]
    }
    print(f"   - Payload: {args}")

    # 3. Call internal handler directly
    print("\n3. Calling _handle_add_memory...")
    try:
        # We need to mock the call context or just call the method if possible.
        # Check server method signature.
        # async def _handle_add_memory(self, arguments: dict) -> list[types.TextContent]
        
        result = await server._handle_add_memory(args)
        print("   ✅ SUCCESS! Result:")
        print(result)
        
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    try:
        asyncio.run(simulate_add_memory())
    except KeyboardInterrupt:
        print("\n⚠ Interrupted")
    except Exception as e:
        print(f"\n❌ Script crash: {e}")
