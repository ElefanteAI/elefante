"""Test script to verify MCP tool registration"""
import asyncio
import sys
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.mcp.server import ElefanteMCPServer

async def _run_tool_registration():
    print("=" * 60)
    print("ELEFANTE MCP SERVER - TOOL REGISTRATION TEST")
    print("=" * 60)
    
    print("\n[1/3] Initializing MCP server...")
    try:
        server = ElefanteMCPServer()
        print("[OK] Server initialized successfully")
    except Exception as e:
        print(f"[FAIL] Server initialization failed: {e}")
        return False
    
    print("\n[2/3] Extracting tool list from server code...")
    # The tools are registered in _register_handlers, we need to inspect the source
    import inspect
    source = inspect.getsource(server._register_handlers)
    
    # Count Tool( declarations
    tool_count = source.count('Tool(')
    print(f"Found {tool_count} Tool() declarations in source code")
    
    # Extract tool names from source
    import re
    tool_names = re.findall(r'name="(\w+)"', source)
    
    print(f"\n[3/3] Registered tools ({len(tool_names)} total):")
    for i, name in enumerate(tool_names, 1):
        print(f"  {i}. {name}")
    
    expected_tools = [
        'elefanteMemoryAdd',
        'elefanteMemorySearch',
        'elefanteGraphQuery',
        'elefanteContextGet',
        'elefanteGraphEntityCreate',
        'elefanteGraphRelationshipCreate',
        'elefanteSessionsList',
        'elefanteSystemStatusGet',
        'elefanteDashboardOpen',
        'elefanteGraphConnect',
        'elefanteMemoryConsolidate',
        'elefanteMemoryListAll',
        'elefanteMemoryMigrateToV3',
        'elefanteSystemEnable',
        'elefanteSystemDisable',
    ]
    
    missing = [t for t in expected_tools if t not in tool_names]
    extra = [t for t in tool_names if t not in expected_tools]
    
    print("\n" + "=" * 60)
    print("VERIFICATION RESULTS")
    print("=" * 60)
    print(f"Expected tools: {len(expected_tools)}")
    print(f"Found in code:  {len(tool_names)}")
    
    if missing:
        print(f"\n[FAIL] Missing tools: {missing}")
    if extra:
        print(f"\n[WARN] Extra tools: {extra}")
    
    if len(tool_names) == len(expected_tools) and not missing:
        print("\n[SUCCESS] All expected tools are defined in the code!")
        print("\nNext step: Restart Bob-IDE to load the updated server.")
        return True
    else:
        print("\n[FAIL] Tool registration incomplete in code")
        return False


def test_tool_registration():
    pytest.skip("Manual verification script; run this module directly to execute")

if __name__ == "__main__":
    success = asyncio.run(_run_tool_registration())
    exit(0 if success else 1)

