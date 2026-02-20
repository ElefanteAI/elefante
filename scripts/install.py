"""
Elefante Unified Installation Script
------------------------------------
Robust, one-click installation for Windows, macOS, and Linux.
Handles:
1. Virtual Environment creation
2. Dependency installation
3. Database initialization
4. MCP Server configuration (VSCode/Bob)
5. System verification
"""

import os
import sys
import subprocess
import platform
import json
import shutil
import argparse
import datetime
from pathlib import Path

# Ensure we can import from scripts directory
sys.path.append(str(Path(__file__).parent))

# Import existing configuration logic
try:
    from configure_vscode_bob import configure_mcp as configure_vscode
    from configure_antigravity import configure_mcp as configure_antigravity
except ImportError:
    # Fallback if running from root
    sys.path.append(str(Path(__file__).parent / "scripts"))
    from configure_vscode_bob import configure_mcp as configure_vscode
    from configure_antigravity import configure_mcp as configure_antigravity

class Logger:
    def __init__(self, log_file=None):
        self.log_file = log_file
        if log_file:
            # Ensure log file exists and is writable
            try:
                with open(log_file, 'a', encoding='utf-8') as f:
                    pass
            except Exception as e:
                print(f"WARN: Could not open log file {log_file}: {e}")
                self.log_file = None

    def log(self, msg, end="\n"):
        # Print to console
        print(msg, end=end)
        # Write to file if configured
        if self.log_file:
            try:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    # Strip ANSI color codes if we were using them (we aren't much, but good practice)
                    clean_msg = msg
                    f.write(clean_msg + end)
            except Exception:
                pass

logger = None

def print_header(msg):
    logger.log("\n" + "="*60)
    logger.log(msg)
    logger.log("="*60 + "\n")

def print_step(step, msg):
    logger.log(f"\n[Step {step}] {msg}...")

def run_command(cmd, cwd=None, shell=False):
    """Run a command and check for errors"""
    try:
        # We want to capture output to log it, but also show it in real-time.
        # For simplicity in this script, we let subprocess write to stdout/stderr,
        # which means it goes to console.
        # If we have a log file, we really should capture it.
        if logger.log_file:
            # Use Popen to capture and log line by line
            process = subprocess.Popen(
                cmd, 
                cwd=cwd, 
                shell=shell, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    logger.log(line.rstrip())
            
            return process.poll() == 0
        else:
            subprocess.check_call(cmd, cwd=cwd, shell=shell)
            return True
    except subprocess.CalledProcessError:
        return False
    except Exception as e:
        logger.log(f"ERROR: Execution error: {e}")
        return False

def check_kuzu_compatibility(root_dir):
    """
    Pre-flight check for Kuzu 0.11+ compatibility issues
    Prevents the "Database path cannot be a directory" error
    """
    logger.log("\nChecking Kuzu compatibility...")
    
    # Check if Kuzu database directory exists
    kuzu_db_path = Path.home() / ".elefante" / "data" / "kuzu_db"
    
    if kuzu_db_path.exists() and kuzu_db_path.is_dir():
        # Check if it's a valid Kuzu database or empty directory
        kuzu_files = list(kuzu_db_path.glob("*.kz")) + list(kuzu_db_path.glob(".lock"))
        
        if kuzu_files:
            logger.log(f"WARN: Found existing Kuzu database at: {kuzu_db_path}")
            logger.log("   Kuzu 0.11+ requires clean installation for path compatibility.")
            logger.log("")
            logger.log("   Options:")
            logger.log("   1. Backup and remove (recommended)")
            logger.log("   2. Skip and risk installation failure")
            logger.log("")
            
            response = input("   Backup and remove existing database? (Y/n): ").strip().lower()
            
            if response in ['', 'y', 'yes']:
                logger.log("\n   This will MOVE the existing DB directory to a timestamped backup.")
                logger.log("   No data is deleted, but Elefante will start with a fresh DB.")
                confirm = input("   Type DELETE to proceed (or anything else to abort): ").strip()
                if confirm != "DELETE":
                    logger.log("OK: Aborted database move.")
                    logger.log("WARN: Skipping database removal. Installation may fail.")
                    logger.log("   If installation fails, manually move/remove: " + str(kuzu_db_path))
                    logger.log("")
                    return False

                # Move original to backup (safer than copy+delete)
                stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_path = kuzu_db_path.parent / f"kuzu_db.backup.{stamp}"
                # Ensure unique backup path
                suffix = 1
                while backup_path.exists():
                    backup_path = kuzu_db_path.parent / f"kuzu_db.backup.{stamp}.{suffix}"
                    suffix += 1

                logger.log(f"Moving database to backup at: {backup_path}")
                try:
                    shutil.move(str(kuzu_db_path), str(backup_path))
                except Exception as e:
                    logger.log(f"ERROR: Could not move database to backup: {e}")
                    logger.log("WARN: Skipping database removal. Installation may fail.")
                    logger.log("")
                    return False

                logger.log("OK: Database moved to backup successfully")
                logger.log("")
                return True
            else:
                logger.log("WARN: Skipping database removal. Installation may fail.")
                logger.log("   If installation fails, manually remove: " + str(kuzu_db_path))
                logger.log("")
                return False
        else:
            # Empty directory - safe to remove
            logger.log(f"Removing empty Kuzu directory: {kuzu_db_path}")
            kuzu_db_path.rmdir()
            logger.log("OK: Empty directory removed")
            return True
    else:
        logger.log("OK: No Kuzu compatibility issues detected")
        return True

def check_dependency_versions(root_dir):
    """
    Check for known breaking changes in dependencies
    """
    logger.log("\nChecking dependency versions for breaking changes...")
    
    requirements_file = root_dir / "requirements.txt"
    if not requirements_file.exists():
        logger.log("WARN: requirements.txt not found")
        return True
    
    breaking_changes = {
        "kuzu": {
            "version": "0.11",
            "issue": "Database path handling changed - cannot pre-create directories",
            "fixed_by": "check_kuzu_compatibility()"
        }
    }
    
    with open(requirements_file, 'r') as f:
        requirements = f.read()
    
    issues_found = []
    for package, info in breaking_changes.items():
        if package in requirements and info["version"] in requirements:
            logger.log(f"WARN: {package} {info['version']}+ detected")
            logger.log(f"   Known issue: {info['issue']}")
            logger.log(f"   Mitigation: {info['fixed_by']}")
            issues_found.append(package)
    
    if not issues_found:
        logger.log("OK: No known breaking changes detected")
    
    logger.log("")
    return True

def check_disk_space(root_dir):
    """
    Verify sufficient disk space for installation
    """
    logger.log("\nChecking disk space...")
    
    required_space = 5_000_000_000  # 5 GB
    
    if platform.system() == 'Windows':
        import ctypes
        free_bytes = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(
            ctypes.c_wchar_p(str(root_dir)), 
            None, 
            None, 
            ctypes.pointer(free_bytes)
        )
        available = free_bytes.value
    else:
        stat = os.statvfs(root_dir)
        available = stat.f_bavail * stat.f_frsize
    
    available_gb = available / (1024**3)
    required_gb = required_space / (1024**3)
    
    if available < required_space:
        logger.log("ERROR: Insufficient disk space")
        logger.log(f"   Available: {available_gb:.2f} GB")
        logger.log(f"   Required: {required_gb:.2f} GB")
        return False
    else:
        logger.log(f"OK: Sufficient disk space: {available_gb:.2f} GB available")
        return True

def run_preflight_checks(root_dir):
    """
    Run all pre-flight checks before installation
    """
    print_header("PRE-FLIGHT CHECKS")
    logger.log("Running automated checks to prevent common installation issues...")
    
    checks = [
        ("Disk Space", lambda: check_disk_space(root_dir)),
        ("Dependency Versions", lambda: check_dependency_versions(root_dir)),
        ("Kuzu Compatibility", lambda: check_kuzu_compatibility(root_dir)),
    ]
    
    all_passed = True
    for check_name, check_func in checks:
        try:
            result = check_func()
            if not result:
                all_passed = False
                logger.log(f"ERROR: {check_name} check failed")
        except Exception as e:
            logger.log(f"WARN: {check_name} check error: {e}")
            all_passed = False
    
    if all_passed:
        logger.log("\nOK: All pre-flight checks passed")
        logger.log("="*60 + "\n")
        return True
    else:
        logger.log("\nERROR: Some pre-flight checks failed")
        logger.log("Please resolve the issues above before continuing.")
        logger.log("="*60 + "\n")
        return False

def purge_bytecode(root_dir):
    """Purge compiled bytecode to prevent stale execution"""
    logger.log("\nPurging bytecode...")
    count = 0
    try:
        # Walk and delete __pycache__ folders
        for path in root_dir.rglob("__pycache__"):
            if path.is_dir():
                shutil.rmtree(path)
                count += 1
        
        # Walk and delete .pyc files
        for path in root_dir.rglob("*.pyc"):
             if path.is_file():
                 path.unlink()
                 count += 1
                 
        logger.log(f"OK: Cleaned {count} stale bytecode artifacts")
        return True
    except Exception as e:
        logger.log(f"WARN: Bytecode purge failed: {e}")
        return False


def get_python_cmd():
    """Get the correct python command"""
    if sys.platform == 'win32':
        return sys.executable
    return sys.executable

def create_venv(root_dir):
    """Create virtual environment if it doesn't exist"""
    venv_dir = root_dir / ".venv"
    if venv_dir.exists():
        logger.log("OK: Virtual environment already exists")
        return True
    
    logger.log("Creating virtual environment...")
    if run_command([sys.executable, "-m", "venv", ".venv"], cwd=root_dir):
        logger.log("OK: Virtual environment created")
        return True
    else:
        logger.log("ERROR: Failed to create virtual environment")
        return False

def install_dependencies(root_dir, python_cmd):
    """Install requirements.txt"""
    logger.log("Installing dependencies...")
    
    # Upgrade pip
    run_command([python_cmd, "-m", "pip", "install", "--upgrade", "pip"], cwd=root_dir)
    
    # Install requirements
    if run_command([python_cmd, "-m", "pip", "install", "-r", "requirements.txt"], cwd=root_dir):
        logger.log("OK: Dependencies installed")
        return True
    else:
        logger.log("ERROR: Failed to install dependencies")
        return False

def init_databases(root_dir, python_cmd):
    """Initialize ChromaDB and Kuzu"""
    logger.log("Initializing databases...")
    script_path = root_dir / "scripts" / "init_databases.py"
    if run_command([python_cmd, str(script_path)], cwd=root_dir):
        logger.log("OK: Databases initialized")
        return True
    else:
        logger.log("ERROR: Database initialization failed")
        return False

def run_health_check(root_dir, python_cmd):
    """Run health check script"""
    logger.log("Running health check...")
    script_path = root_dir / "scripts" / "health_check.py"
    if run_command([python_cmd, str(script_path)], cwd=root_dir):
        logger.log("OK: Health check passed")
        return True
    else:
        logger.log("ERROR: Health check failed")
        return False

def verify_copilot_instructions(root_dir):
    """Verify .github/copilot-instructions.md exists — the bootstrap layer for agent behavior"""
    logger.log("Verifying agent behavior bootstrap...")
    instructions_path = root_dir / ".github" / "copilot-instructions.md"
    if instructions_path.exists():
        logger.log(f"OK: copilot-instructions.md found at {instructions_path}")
        return True
    else:
        logger.log("ERROR: .github/copilot-instructions.md is MISSING")
        logger.log("   This file is the bootstrap layer that tells AI agents how to use Elefante.")
        logger.log("   Without it, agents will NOT proactively search memory.")
        logger.log("   Expected at: " + str(instructions_path))
        return False


def generate_proof(root_dir, success):
    """Generate installation proof block"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = "SUCCESS" if success else "FAILED"
    
    proof = f"""
============================================================
INSTALLATION PROOF
============================================================
Date:   {timestamp}
Status: {status}
Path:   {root_dir}
System: {platform.system()} {platform.release()}
============================================================
"""
    logger.log(proof)
    return proof

def main():
    global logger
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-file", help="Path to log file")
    args = parser.parse_args()
    
    logger = Logger(args.log_file)
    
    root_dir = Path(__file__).parent.parent.absolute()
    os.chdir(root_dir)
    
    print_header("ELEFANTE INSTALLATION WIZARD")
    logger.log(f"Installation Directory: {root_dir}")
    logger.log(f"Python: {sys.version.split()[0]}")
    
    # 0a. Purge Bytecode (Prevent Stale Code)
    purge_bytecode(root_dir)
    
    # 0. Pre-Flight Checks (NEW - Prevents Kuzu and other issues)
    if not run_preflight_checks(root_dir):
        logger.log("\nERROR: Installation aborted due to pre-flight check failures")
        logger.log("Please resolve the issues above and try again.")
        sys.exit(1)
    
    success = True
    
    # 1. Virtual Environment
    print_step(1, "Environment Setup")
    in_venv = sys.prefix != sys.base_prefix
    if not in_venv:
        logger.log("WARN: Not running in a virtual environment")
        logger.log("   It is recommended to run this script via 'install.bat' (Windows) or 'install.sh' (Mac/Linux).")
    
    python_cmd = get_python_cmd()
    
    # 2. Dependencies
    print_step(2, "Dependencies")
    if not install_dependencies(root_dir, python_cmd):
        success = False
    
    if success:
        # 3. Databases
        print_step(3, "Database Initialization")
        if not init_databases(root_dir, python_cmd):
            success = False
            
    if success:
        # 4. MCP Configuration
        print_step(4, "IDE Configuration")
        try:
            vscode_success = configure_vscode()
            antigravity_success = configure_antigravity()
            
            if vscode_success:
                logger.log("OK: MCP Server configured for VSCode/Bob")
            
            if antigravity_success:
                logger.log("OK: MCP Server configured for Antigravity")
                
            if not vscode_success and not antigravity_success:
                logger.log("WARN: Automatic MCP configuration skipped")
                logger.log("   Please configure your IDE manually.")
                logger.log("   See docs/technical/installation.md and docs/technical/mcp-server-startup.md for instructions.")
        except Exception as e:
            logger.log(f"ERROR: Error configuring MCP: {e}")
            
    if success:
        # 4a. Agent Behavior Bootstrap
        logger.log("")
        logger.log("[Step 4a] Agent Behavior Bootstrap...")
        if not verify_copilot_instructions(root_dir):
            logger.log("WARN: Agent behavior bootstrap missing. Agents will not proactively use Elefante.")
            logger.log("   See docs/technical/installation.md Section 4a for details.")
    
    if success:
        # 5. Verification
        print_step(5, "System Verification")
        if not run_health_check(root_dir, python_cmd):
            logger.log("WARN: Health check failed. Please review the errors.")
            success = False

        if success:
             # 5a. MCP Handshake Verification (Real Liveness Check)
             logger.log("\nVerifying MCP handshake...")
             handshake_script = root_dir / "scripts" / "verify_mcp_handshake.py"
             if run_command([python_cmd, str(handshake_script)], cwd=root_dir):
                 logger.log("OK: MCP handshake verified")
             else:
                 logger.log("ERROR: MCP handshake failed. Server is not responding to protocol.")
                 success = False

    # Generate Proof
    generate_proof(root_dir, success)
    
    if success:
        print_header("INSTALLATION COMPLETE")
        logger.log("Next Steps:")
        logger.log("1. Restart your IDE to load the MCP server.")
        logger.log("2. Start using Elefante commands in your AI chat!")
        logger.log("   - 'Remember that...'\n   - 'What do you know about...'\n")
    else:
        print_header("INSTALLATION FAILED")
        logger.log("Please check the logs above for errors.")
        sys.exit(1)
    
    if os.name == 'nt':
        input("Press Enter to exit...")

if __name__ == "__main__":
    main()
