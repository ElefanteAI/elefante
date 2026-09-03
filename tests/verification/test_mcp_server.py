"""
MCP Server Verification Script
------------------------------
Launches the MCP server as a subprocess and verifies it responds to JSON-RPC.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest


SERVER_RESPONSE_TIMEOUT_SECONDS = 30
PROCESS_CLEANUP_TIMEOUT_SECONDS = 5


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")


def test_mcp_server(tmp_path: Path):
    log(" Starting MCP Server Test...")

    repo_root = Path(__file__).resolve().parents[2]
    data_dir = tmp_path / "elefante-data"
    vector_dir = data_dir / "vector"
    graph_path = data_dir / "kuzu_db"
    log_path = tmp_path / "elefante-logs" / "elefante.log"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "elefante:\n"
        f"  data_dir: {json.dumps(str(data_dir))}\n"
        "  vector_store:\n"
        "    type: sqlite\n"
        f"    persist_directory: {json.dumps(str(vector_dir))}\n"
        "  graph_store:\n"
        f"    database_path: {json.dumps(str(graph_path))}\n"
        "  logging:\n"
        f"    file: {json.dumps(str(log_path))}\n"
        "    console: false\n",
        encoding="utf-8",
    )

    server_cmd = [sys.executable, "-m", "src.mcp.server"]
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(repo_root),
            "ELEFANTE_CONFIG_PATH": str(config_path),
            "ELEFANTE_DATA_DIR": str(data_dir),
            "ELEFANTE_VECTOR_STORE_TYPE": "sqlite",
            "ELEFANTE_LOCK_DIR": str(tmp_path / "elefante-locks"),
            "ELEFANTE_PROCESS_IDENTITY_PATH": str(tmp_path / "process-identity.json"),
            "ELEFANTE_SESSION_INTELLIGENCE_DB": str(
                tmp_path / "session-intelligence.sqlite3"
            ),
            "ELEFANTE_SESSION_INTELLIGENCE_SNAPSHOT": str(
                tmp_path / "session-intelligence.json"
            ),
        }
    )

    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "ElefanteVerifier",
                "version": "1.0.0",
            },
        },
    }

    log(f"   Command: {' '.join(server_cmd)}")
    log(f"   CWD: {repo_root}")
    process = None
    stdout = ""
    stderr = ""
    try:
        process = subprocess.Popen(
            server_cmd,
            cwd=str(repo_root),
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0,
        )
        log("    Server process started.")

        log("    Sending 'initialize' request and waiting for response...")
        try:
            stdout, stderr = process.communicate(
                input=json.dumps(init_request) + "\n",
                timeout=SERVER_RESPONSE_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            pytest.fail(
                "Timed out waiting for MCP server response after "
                f"{SERVER_RESPONSE_TIMEOUT_SECONDS}s. Server stderr: {stderr[-2000:]}"
            )

        assert process.returncode == 0, (
            f"MCP server exited with code {process.returncode}. stderr: {stderr[-2000:]}"
        )

        response_line = next(
            (line for line in stdout.splitlines() if line.strip()),
            None,
        )
        assert response_line, (
            "MCP server returned no JSON-RPC response. "
            f"stderr: {stderr[-2000:]}"
        )
        log(f"    Received response: {response_line.strip()[:100]}...")

        try:
            response = json.loads(response_line)
        except json.JSONDecodeError as error:
            pytest.fail(f"Failed to decode JSON response: {error}")

        assert "result" in response, "MCP initialize response missing 'result'"
        assert "capabilities" in response["result"], (
            "MCP initialize response missing 'capabilities'"
        )
        assert "serverInfo" in response["result"], (
            "MCP initialize response missing 'serverInfo'"
        )
        assert "name" in response["result"]["serverInfo"], (
            "MCP initialize response missing server name"
        )
        assert data_dir.is_dir(), f"Isolated data directory was not created: {data_dir}"
        assert vector_dir.is_dir(), (
            f"Isolated vector directory was not created: {vector_dir}"
        )
        log("    Server returned capabilities.")
        log(f"   Server Name: {response['result']['serverInfo']['name']}")
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=PROCESS_CLEANUP_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=PROCESS_CLEANUP_TIMEOUT_SECONDS)
        if process is not None:
            assert process.poll() is not None, "MCP server process was not cleaned up"
            log("    Server process cleaned up.")


if __name__ == "__main__":
    try:
        with tempfile.TemporaryDirectory(prefix="elefante-mcp-server-") as temp_dir:
            test_mcp_server(Path(temp_dir))
    except AssertionError:
        print("\n MCP Server test failed.")
        sys.exit(1)
    else:
        print("\n MCP Server is functioning correctly.")
        sys.exit(0)
