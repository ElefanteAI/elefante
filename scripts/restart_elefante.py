#!/usr/bin/env python3
"""Elefante Safe Restart Utility.

Safely restarts the Elefante MCP server to pick up code changes.

Usage:
  python scripts/restart_elefante.py [--force] [--timeout SECONDS] [--verify] [--version X.Y.Z]

Notes:
- This is a promoted entrypoint (previously under scripts/archive/historical/).
- It is safe with v1.1.0+ transaction-scoped locking.
"""

import os
import sys
import time
import signal
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

# Add src to path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

from src.utils.logger import get_logger

logger = get_logger(__name__)


def find_mcp_server_process():
    """Find the running MCP server process."""
    try:
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True, check=True)
        for line in result.stdout.split("\n"):
            if "python" in line and "src.mcp.server" in line and "grep" not in line:
                parts = line.split()
                pid = int(parts[1])
                return pid
        return None
    except Exception as e:
        logger.error(f"Error finding MCP server process: {e}")
        return None


def clean_locks():
    """Clean up any stale lock files."""
    from src.utils.config import ELEFANTE_HOME

    lock_dir = ELEFANTE_HOME / "locks"
    if not lock_dir.exists():
        logger.info("No lock directory found")
        return

    lock_files = list(lock_dir.glob("*.lock"))

    if not lock_files:
        logger.info("No lock files to clean")
        return

    for lock_file in lock_files:
        try:
            if lock_file.exists():
                content = lock_file.read_text().strip()

                if not content:
                    lock_file.unlink()
                    logger.info(f"Removed empty lock: {lock_file.name}")
                    continue

                parts = content.split("|")
                if len(parts) >= 1:
                    try:
                        pid = int(parts[0])
                        os.kill(pid, 0)
                        logger.warning(f"Lock {lock_file.name} held by live PID {pid} - keeping")
                    except (ValueError, ProcessLookupError, PermissionError):
                        lock_file.unlink()
                        logger.info(f"Removed stale lock: {lock_file.name} (dead PID)")
        except Exception as e:
            logger.warning(f"Error checking lock {lock_file.name}: {e}")


def stop_mcp_server(pid: int, timeout: int = 10, force: bool = False) -> bool:
    """Gracefully stop the MCP server process."""
    try:
        logger.info(f"Sending SIGTERM to PID {pid}")
        os.kill(pid, signal.SIGTERM)

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                os.kill(pid, 0)
                time.sleep(0.5)
            except ProcessLookupError:
                logger.info(f"Process {pid} exited gracefully")
                return True

        logger.warning(f"Process {pid} did not exit after {timeout}s")

        if force:
            logger.warning(f"Force killing PID {pid} with SIGKILL")
            os.kill(pid, signal.SIGKILL)
            time.sleep(1)

            try:
                os.kill(pid, 0)
                logger.error(f"Failed to kill process {pid}")
                return False
            except ProcessLookupError:
                logger.info(f"Process {pid} force killed")
                return True

        logger.error(f"Process {pid} still running (use --force to kill)")
        return False

    except ProcessLookupError:
        logger.info(f"Process {pid} already stopped")
        return True
    except PermissionError:
        logger.error(f"Permission denied when stopping PID {pid}")
        return False
    except Exception as e:
        logger.error(f"Error stopping process {pid}: {e}")
        return False


def start_mcp_server() -> bool:
    """Start the MCP server in the background."""
    try:
        venv_python = WORKSPACE_ROOT / ".venv" / "bin" / "python"

        if not venv_python.exists():
            logger.error(f"Virtual environment not found: {venv_python}")
            return False

        logger.info("Starting MCP server...")

        process = subprocess.Popen(
            [str(venv_python), "-m", "src.mcp.server"],
            cwd=str(WORKSPACE_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        time.sleep(2)

        if process.poll() is not None:
            logger.error(f"MCP server exited immediately with code {process.returncode}")
            return False

        logger.info(f"MCP server started with PID {process.pid}")
        return True

    except Exception as e:
        logger.error(f"Error starting MCP server: {e}")
        return False


def verify_restart(expected_version: str = None) -> bool:
    """Verify the MCP server restarted successfully."""
    try:
        time.sleep(1)

        new_pid = find_mcp_server_process()
        if not new_pid:
            logger.error("MCP server process not found after restart")
            return False

        logger.info(f"MCP server running as PID {new_pid}")

        if expected_version:
            logger.info("Server restarted successfully (version check not implemented)")

        return True

    except Exception as e:
        logger.error(f"Error verifying restart: {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely restart Elefante MCP server")
    parser.add_argument("--force", action="store_true", help="Force kill if graceful shutdown fails")
    parser.add_argument(
        "--timeout", type=int, default=10, help="Max wait time for graceful shutdown (seconds)"
    )
    parser.add_argument("--verify", action="store_true", help="Verify restart by checking process")
    parser.add_argument("--version", type=str, help="Expected version to verify (e.g., '1.3.0')")

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Elefante Safe Restart Utility")
    logger.info(f"Time: {datetime.now().isoformat()}")
    logger.info("=" * 60)

    logger.info("\n[1/5] Finding MCP server process...")
    current_pid = find_mcp_server_process()

    if current_pid:
        logger.info(f"Found MCP server: PID {current_pid}")
    else:
        logger.info("No MCP server process found")

    if current_pid:
        logger.info(f"\n[2/5] Stopping MCP server (PID {current_pid})...")
        if not stop_mcp_server(current_pid, timeout=args.timeout, force=args.force):
            logger.error("Failed to stop MCP server")
            return 1
        logger.info("MCP server stopped successfully")
    else:
        logger.info("\n[2/5] No server to stop")

    logger.info("\n[3/5] Cleaning up lock files...")
    clean_locks()

    logger.info("\n[4/5] Starting MCP server...")
    if not start_mcp_server():
        logger.error("Failed to start MCP server")
        return 1
    logger.info("MCP server started successfully")

    if args.verify:
        logger.info("\n[5/5] Verifying restart...")
        if not verify_restart(expected_version=args.version):
            logger.error("Restart verification failed")
            return 1
        logger.info("Restart verified successfully")
    else:
        logger.info("\n[5/5] Skipping verification (use --verify to enable)")

    logger.info("\n" + "=" * 60)
    logger.info("✅ Elefante restart completed successfully")
    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
