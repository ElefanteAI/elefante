import asyncio
import json
import sys
import os
import subprocess
from typing import Dict, Any

import pytest

pytest.skip("manual live MCP integration script (not part of automated pytest)", allow_module_level=True)

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def run_integration_test():
    print("Starting Live MCP Server Integration Test...")
    
    # Path to server script
    server_script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "mcp", "server.py")
    
    # Set PYTHONPATH to include project root
    env = os.environ.copy()
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env["PYTHONPATH"] = project_root + os.pathsep + env.get("PYTHONPATH", "")

    # Start the server process
    process = await asyncio.create_subprocess_exec(
        sys.executable, server_script,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env
    )
    
    print(f"Server process started (PID: {process.pid})")

    async def read_response():
        # Read line-by-line (JSON-RPC over stdio)
        while True:
            line = await process.stdout.readline()
            if not line:
                # Check if process exited
                if process.returncode is not None:
                    print(f"Process exited with code {process.returncode}")
                    stderr = await process.stderr.read()
                    print(f"[STDERR]:\n{stderr.decode()}")
                return None
            
            line = line.decode().strip()
            if not line:
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                print(f"  [Server STDOUT (Not JSON)]: {line}")

    async def send_request(method: str, params: Dict[str, Any] = None, req_id: int = 1):
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": req_id
        }
        msg = json.dumps(request) + "\n"
        process.stdin.write(msg.encode())
        await process.stdin.drain()
        return await read_response()

    try:
        # 1. Initialize
        print("\nSending 'initialize' request...")
        init_response = await send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"}
        }, req_id=1)
        
        if init_response and "result" in init_response:
            print("Initialization successful")
        else:
            print(f"Initialization failed: {init_response}")
            return

        # 2. Initialized notification
        msg = json.dumps({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        }) + "\n"
        process.stdin.write(msg.encode())
        await process.stdin.drain()

        # 3. Call Tool: elefante-MemorySearch (to trigger injection)
        print("\nCalling 'tools/call' (elefante-MemorySearch)...")
        # Note: MCP protocol for tool call
        tool_call_response = await send_request("tools/call", {
            "name": "elefante-MemorySearch",
            "arguments": {
                "query": "DEVELOPER ETIQUETTE",
                "mode": "semantic" # Force semantic to avoid graph errors if empty
            }
        }, req_id=2)

        # 4. Verify Injection
        print("\nVerifying Injection...")
        if tool_call_response and "result" in tool_call_response:
            content_list = tool_call_response["result"].get("content", [])
            if content_list:
                # The content is a list of TextContent objects, we need to parse the text inside
                text_content = content_list[0].get("text", "")
                try:
                    data = json.loads(text_content)
                    
                    # Print Result Summary
                    results = data.get("results", [])
                    print(f"\nFound {len(results)} memories:")
                    for res in results[:3]:
                        print(f"   - [{res.get('score', 0):.2f}] {res.get('content', '')[:60]}...")

                    # CHECK FOR INJECTION KEY
                    key = "MANDATORY_PROTOCOLS_READ_THIS_FIRST"
                    if key in data:
                        print(f"FOUND INJECTION KEY: {key}")
                        print("   Protocols found:")
                        for p in data[key]:
                            print(f"   - {p[:60]}...")
                    else:
                        print(f"INJECTION KEY NOT FOUND in: {data.keys()}")
                        
                except json.JSONDecodeError:
                    print(f"Failed to parse tool response text: {text_content[:100]}...")
            else:
                print("No content in tool response")
        else:
            print(f"Tool call failed: {tool_call_response}")

    except Exception as e:
        print(f"Test Exception: {e}")
    finally:
        print("\nTerminating server...")
        process.terminate()
        await process.wait()
        print("Server terminated")

if __name__ == "__main__":
    asyncio.run(run_integration_test())
