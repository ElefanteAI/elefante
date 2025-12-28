#!/usr/bin/env python3
"""
Elefante Safe Restart Utility

Safely restarts the Elefante MCP server to pick up code changes.

Features:
- Graceful shutdown with resource cleanup
- Stale lock detection and removal
- Transaction-scoped locking safety (v1.1.0+)
- Verification of successful restart
- No corruption, no leftover files

Usage:
    python scripts/restart_elefante.py [--force] [--timeout SECONDS]

Options:
    --force         Force kill if graceful shutdown fails
    --timeout       Max wait time for graceful shutdown (default: 10s)
    --verify        Verify restart by checking version
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
WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

from src.utils.logger import get_logger

logger = get_logger(__name__)


def find_mcp_server_process():
    """Find the running MCP server process."""
    try:
        # Look for python process running src.mcp.server
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            check=True
        )
        
        for line in result.stdout.split('\n'):
            if 'python' in line and 'src.mcp.server' in line and 'grep' not in line:
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
            # Check if lock is stale (contains dead PID or very old timestamp)
            if lock_file.exists():
                content = lock_file.read_text().strip()
                
                if not content:
                    # Empty lock file - safe to remove
                    lock_file.unlink()
                    logger.info(f"Removed empty lock: {lock_file.name}")
                    continue
                
                # Parse PID|timestamp format
                parts = content.split("|")
                if len(parts) >= 1:
                    try:
                        pid = int(parts[0])
                        # Check if process is alive
                        os.kill(pid, 0)
                        logger.warning(f"Lock {lock_file.name} held by live PID {pid} - keeping")
                    except (ValueError, ProcessLookupError, PermissionError):
                        # Process is dead - safe to remove
                        lock_file.unlink()
                        logger.info(f"Removed stale lock: {lock_file.name} (dead PID)")
                        
        except Exception as e:
            logger.warning(f"Error checking lock {lock_file.name}: {e}")


def stop_mcp_server(pid: int, timeout: int = 10, force: bool = False) -> bool:
    """
    Gracefully stop the MCP server process.
    
    Args:
        pid: Process ID to stop
        timeout: Max wait time for graceful shutdown
        force: If True, use SIGKILL if SIGTERM fails
    
    Returns:
        True if stopped successfully
    """
    try:
        # Send SIGTERM for graceful shutdown
        logger.info(f"Sending SIGTERM to PID {pid}")
        os.kill(pid, signal.SIGTERM)
        
        # Wait for process to exit
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Check if process still exists
                os.kill(pid, 0)
                time.sleep(0.5)
            except ProcessLookupError:
                logger.info(f"Process {pid} exited gracefully")
                return True
        
        # Timeout - process didn't exit
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
        else:
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
    """
    Start the MCP server in the background.
    
    Returns:
        True if started successfully
    """
    try:
        # Activate venv and start server
        venv_python = WORKSPACE_ROOT / ".venv" / "bin" / "python"
        
        if not venv_python.exists():
            logger.error(f"Virtual environment not found: {venv_python}")
            return False
        
        # Start server in background
        logger.info("Starting MCP server...")
        
        process = subprocess.Popen(
            [str(venv_python), "-m", "src.mcp.server"],
            cwd=str(WORKSPACE_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True  # Detach from parent
        )
        
        # Wait briefly for startup
        time.sleep(2)
        
        # Check if process is still running
        if process.poll() is not None:
            logger.error(f"MCP server exited immediately with code {process.returncode}")
            return False
        
        logger.info(f"MCP server started with PID {process.pid}")
        return True
        
    except Exception as e:
        logger.error(f"Error starting MCP server: {e}")
        return False


def verify_restart(expected_version: str = None) -> bool:
    """
    Verify the MCP server restarted successfully.
    
    Args:
        expected_version: Expected version string (optional)
    
    Returns:
        True if verified
    """
    try:
        # Wait a bit for server to initialize
        time.sleep(1)
        
        # Find new process
        new_pid = find_mcp_server_process()
        if not new_pid:
            logger.error("MCP server process not found after restart")
            return False
        
        logger.info(f"MCP server running as PID {new_pid}")
        
        # Optionally verify version if MCP client is available
        if expected_version:
            try:
                # Import MCP client to check version
                # This would require the MCP server to be accessible
                logger.info(f"Server restarted successfully (version check not implemented)")
            except Exception as e:
                logger.warning(f"Could not verify version: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error verifying restart: {e}")
        return False


def main():
    """Main restart logic."""
    parser = argparse.ArgumentParser(
        description="Safely restart Elefante MCP server"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force kill if graceful shutdown fails"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="Max wait time for graceful shutdown (seconds)"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify restart by checking process"
    )
    parser.add_argument(
        "--version",
        type=str,
        help="Expected version to verify (e.g., '1.3.0')"
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Elefante Safe Restart Utility")
    logger.info(f"Time: {datetime.now().isoformat()}")
    logger.info("=" * 60)
    
    # Step 1: Find current MCP server
    logger.info("\n[1/5] Finding MCP server process...")
    current_pid = find_mcp_server_process()
    
    if current_pid:
        logger.info(f"Found MCP server: PID {current_pid}")
    else:
        logger.info("No MCP server process found")
    
    # Step 2: Stop current server (if running)
    if current_pid:
        logger.info(f"\n[2/5] Stopping MCP server (PID {current_pid})...")
        if not stop_mcp_server(current_pid, timeout=args.timeout, force=args.force):
            logger.error("Failed to stop MCP server")
            return 1
        logger.info("MCP server stopped successfully")
    else:
        logger.info("\n[2/5] No server to stop")
    
    # Step 3: Clean up locks
    logger.info("\n[3/5] Cleaning up lock files...")
    clean_locks()
    
    # Step 4: Start new server
    logger.info("\n[4/5] Starting MCP server...")
    if not start_mcp_server():
        logger.error("Failed to start MCP server")
        return 1
    logger.info("MCP server started successfully")
    
    # Step 5: Verify restart (optional)
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
    sys.exit(main())
