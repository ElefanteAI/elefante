"""
Elefante End-to-End Test Script
-------------------------------
Simulates a full MCP client session:
1. Starts the server
2. Initializes connection
3. Calls 'elefante-System' with action="enable" to enable Elefante Mode
4. Calls 'elefante-Memory' to store a test fact
5. Calls 'elefante-Memory' to retrieve it
5. Verifies the result
"""

import subprocess
import json
import sys
import time
import os
from uuid import uuid4
from pathlib import Path

# This is a manual integration script.
# Skip it when collected by pytest, but allow direct execution via:
#   python tests/verification/test_end_to_end.py
if "pytest" in sys.modules:
    import pytest

    pytest.skip(
        "manual end-to-end script (not part of automated pytest)",
        allow_module_level=True,
    )

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def read_json_rpc(process, timeout=10):
    start_time = time.time()
    while time.time() - start_time < timeout:
        line = process.stdout.readline()
        if line:
            try:
                msg = json.loads(line)
                # The server may emit structured logs to stdout that are valid JSON.
                # Only return actual JSON-RPC payloads.
                if isinstance(msg, dict) and msg.get("jsonrpc") == "2.0":
                    return msg
                log(f"   Ignored non-RPC JSON: {str(msg)[:120]}")
            except json.JSONDecodeError:
                log(f"   Ignored non-JSON output: {line.strip()}")
        time.sleep(0.01)
    return None

def send_request(process, method, params=None, req_id=1):
    req = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method
    }
    if params:
        req["params"] = params
    
    json_req = json.dumps(req) + "\n"
    process.stdin.write(json_req)
    process.stdin.flush()
    return req_id

def test_end_to_end():
    log("Starting End-to-End Test...")
    
    # Setup paths
    repo_root = Path(__file__).resolve().parents[2]
    cwd = str(repo_root)
    server_cmd = [sys.executable, "-m", "src.mcp.server"]
    env = os.environ.copy()
    env["PYTHONPATH"] = cwd + os.pathsep + env.get("PYTHONPATH", "")
    
    process = None
    try:
        # 1. Start Server
        log("   Starting server process...")
        process = subprocess.Popen(
            server_cmd,
            cwd=cwd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=sys.stderr, # Pass stderr through to console
            text=True,
            bufsize=0
        )
        
        # 2. Initialize
        log("   Sending 'initialize'...")
        send_request(process, "initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "E2ETester", "version": "1.0"}
        }, req_id=1)
        
        resp = read_json_rpc(process)
        if not resp or "result" not in resp:
            log("   Initialization failed.")
            return False
        log("   Initialized.")

        # 3. Enable Elefante Mode (required before memory operations)
        log("   Enabling Elefante Mode...")
        send_request(process, "tools/call", {
            "name": "elefante-System",
            "arguments": {"action": "enable"}
        }, req_id=2)

        resp = read_json_rpc(process, timeout=10)
        if not resp or "result" not in resp:
            log("   elefante-System enable failed or timed out.")
            return False
        
        # 4. Add Memory
        unique_id = uuid4().hex
        test_content = f"Elefante E2E Test Memory {int(time.time())} {unique_id}"
        log(f"   Adding memory: '{test_content}'...")
        
        send_request(process, "tools/call", {
            "name": "elefante-Memory",
            "arguments": {
                "action": "add",
                "content": test_content,
                "memory_type": "fact",
                "tags": ["test", "e2e"],
                "metadata": {
                    "title": f"E2E-Test-{unique_id}"
                }
            }
        }, req_id=3)
        
        resp = read_json_rpc(process, timeout=15) # Give it time to embed
        if not resp or "result" not in resp:
            log("   elefante-Memory failed or timed out.")
            return False
            
        # Parse inner tool result
        tool_result = resp["result"]
        # MCP tool results are wrapped in content list
        if "content" in tool_result:
            inner_json = tool_result["content"][0]["text"]
            inner_data = json.loads(inner_json)
            status = inner_data.get("status")
            success = bool(inner_data.get("success"))
            if status in {"stored", "reinforced"} or success or inner_data.get("memory_id"):
                log(f"   Memory stored successfully. status={status}")
            else:
                log(f"   elefante-Memory reported failure: {inner_data}")
                return False
        
        # 5. Search Memory
        log(f"   Searching for memory with query: '{test_content}'...")
        send_request(process, "tools/call", {
            "name": "elefante-Memory",
            "arguments": {
                "action": "search",
                "query": test_content, # Use exact content for better match
                "limit": 5
            }
        }, req_id=4)
        
        resp = read_json_rpc(process, timeout=10)
        if not resp or "result" not in resp:
            log("   elefante-Memory failed.")
            return False
            
        tool_result = resp["result"]
        if "content" in tool_result:
            inner_json = tool_result["content"][0]["text"]
            inner_data = json.loads(inner_json)
            results = inner_data.get("results", [])
            
            log(f"   Found {len(results)} results.")
            if len(results) > 0:
                log(f"   First result raw: {json.dumps(results[0], default=str)}")
            
            found = False
            for i, res in enumerate(results):
                content = res.get('content') or res.get('text') or str(res)
                log(f"      [{i}] {content[:50]}...")
                if test_content in content:
                    found = True
            
            if found:
                log(f"   Found memory: '{test_content}'")
                return True
            else:
                log(f"   Memory not found in top {len(results)} results.")
                return False
                
    except Exception as e:
        log(f"   Test exception: {e}")
        return False
    finally:
        if process:
            process.terminate()
            log("   Server terminated.")

if __name__ == "__main__":
    if test_end_to_end():
        print("\nEnd-to-End Test PASSED")
        sys.exit(0)
    else:
        print("\nEnd-to-End Test FAILED")
        sys.exit(1)