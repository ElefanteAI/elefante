# ─────────────────────────────────────────────────────────────────────────────
# NAME    : verify_mcp_handshake.py
# PURPOSE : Minimal JSON-RPC initialize probe that proves the customer stdio
#           bridge and local daemon can answer a real MCP handshake.
# WHEN    : After restart_elefante.py, to quickly confirm the server came back
#           and is accepting connections before running the full self-protocol.
#           Use this as the second check in the verification ladder:
#           verify_health → verify_mcp_handshake → verify_e2e_tests.
# USAGE   : python scripts/verify/verify_mcp_handshake.py
# NOTES   : Starts the server briefly, sends one JSON-RPC initialize request,
#           checks the response, then exits. Much faster than verify_e2e_tests.py
#           but proves only that the handshake succeeds, not tool correctness.
# ─────────────────────────────────────────────────────────────────────────────
import asyncio
import json
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.utils.logger import get_logger  # noqa: E402

logger = get_logger("verification")

MCP_MODULE = "src.mcp.stdio_bridge"
HANDSHAKE_TIMEOUT_SECONDS = 30.0


async def verify_handshake(timeout_seconds: float = HANDSHAKE_TIMEOUT_SECONDS):
    """
    Simulates a real MCP connection handshake.
    1. Starts the server process.
    2. Sends 'initialize' JSON-RPC request.
    3. Expects valid 'initialize' result with capabilities.
    4. Sends 'notifications/initialized'.
    5. Validates server is truly responsive (not just a running process).
    """
    logger.info("Testing MCP Server Handshake...")
    
    cmd = [sys.executable, "-m", MCP_MODULE]
    process = None
    
    try:
        # Start Server Process
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(project_root),
            env={**os.environ, "PYTHONPATH": str(project_root)}  # Preserve environment
        )
        
        # 1. Send Initialize Request
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "ElefanteVerifier", "version": "1.0"}
            }
        }
        
        logger.info("Sending 'initialize'...")
        process.stdin.write(json.dumps(init_request).encode() + b"\n")
        await process.stdin.drain()
        
        # 2. Read Response (with timeout)
        try:
            line = await asyncio.wait_for(process.stdout.readline(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            logger.error(
                f"Timeout waiting {timeout_seconds:g}s for 'initialize' response"
            )
            process.kill()
            await process.wait()
            stderr = await process.stderr.read()
            if stderr:
                logger.error(f"Bridge diagnostics: {stderr.decode(errors='replace')[-2000:]}")
            return False
            
        if not line:
            stderr = await process.stderr.read()
            logger.error(f"Server closed connection unexpectedly.\nStderr: {stderr.decode()}")
            return False
            
        response = json.loads(line.decode())
        
        # 3. Validate Response
        if response.get("id") != 1:
            logger.error(f"ID mismatch. Expected 1, got {response.get('id')}")
            return False
            
        if "result" not in response:
            logger.error(f"Invalid response format: {response}")
            return False
            
        capabilities = response["result"].get("capabilities", {})
        logger.info(f"Handshake OK. Server capabilities: {list(capabilities.keys())}")
        
        # 4. Send Initialized Notification
        logger.info("Sending 'notifications/initialized'...")
        notify_msg = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        }
        process.stdin.write(json.dumps(notify_msg).encode() + b"\n")
        await process.stdin.drain()
        
        logger.info("Verification complete: MCP Server is speaking protocol.")
        return True
        
    except Exception as e:
        logger.error(f"Verification failed: {e}")
        return False
    finally:
        if process is not None and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()

if __name__ == "__main__":
    success = asyncio.run(verify_handshake())
    if not success:
        sys.exit(1)
    sys.exit(0)
