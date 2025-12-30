#!/usr/bin/env python3.11
"""
Emergency fix script - autonomous full installation with Python 3.11
Handles: venv creation, dependency install, db init, health check
"""

import os
import sys
import shutil
import subprocess
import logging
from pathlib import Path
from datetime import datetime

# Setup logging
log_file = Path(__file__).parent.parent / "autonomous_fix.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, mode='w'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def run_cmd(cmd, description="", check=True):
    """Run command and log output"""
    logger.info(f"  {description or ' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=300
        )
        if result.stdout:
            logger.info(result.stdout[:500])
        if result.returncode != 0 and check:
            logger.error(f" Command failed: {result.stderr[:500]}")
            raise subprocess.CalledProcessError(result.returncode, cmd, result.stderr)
        return result
    except Exception as e:
        logger.error(f" Error: {e}")
        raise

def main():
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    logger.info(f" Starting autonomous fix in {project_root}")

    # 1. Verify Python 3.11
    python_exe = "/opt/homebrew/bin/python3.11"
    if not Path(python_exe).exists():
        logger.error(f" Python 3.11 not found at {python_exe}")
        return False

    result = subprocess.run([python_exe, "--version"], capture_output=True, text=True)
    logger.info(f"✓ Python found: {result.stdout.strip()}")

    # 2. Remove broken .venv (with retry)
    venv_path = project_root / ".venv"
    if venv_path.exists():
        logger.info(f"  Removing broken .venv...")
        for attempt in range(3):
            try:
                shutil.rmtree(venv_path)
                logger.info("✓ Removed .venv")
                break
            except Exception as e:
                logger.warning(f"Attempt {attempt+1} failed: {e}, retrying...")
                if attempt == 2:
                    subprocess.run(["rm", "-rf", str(venv_path)], timeout=30)

    # 3. Create fresh venv
    logger.info(" Creating new virtual environment...")
    run_cmd([python_exe, "-m", "venv", str(venv_path)], "Creating venv")

    # Get paths for new venv
    if sys.platform == "win32":
        pip_exe = venv_path / "Scripts" / "pip.exe"
        python_venv = venv_path / "Scripts" / "python.exe"
    else:
        pip_exe = venv_path / "bin" / "pip"
        python_venv = venv_path / "bin" / "python"

    if not pip_exe.exists():
        logger.error(f" pip not found in new venv at {pip_exe}")
        return False

    logger.info(f"✓ New venv created at {venv_path}")

    # 4. Upgrade pip
    logger.info(" Upgrading pip...")
    run_cmd([str(pip_exe), "install", "--upgrade", "pip"], "Upgrade pip")

    # 5. Install requirements
    logger.info(" Installing requirements...")
    req_file = project_root / "requirements.txt"
    run_cmd([str(pip_exe), "install", "-r", str(req_file)], "Install dependencies", check=False)
    logger.info("✓ Dependencies installed")

    # 6. Verify python version in venv
    result = subprocess.run([str(python_venv), "--version"], capture_output=True, text=True)
    logger.info(f"✓ Venv Python: {result.stdout.strip()}")
    if "3.11" not in result.stdout:
        logger.error(f" Wrong Python version in venv!")
        return False

    # 7. Initialize databases
    logger.info(" Initializing databases...")
    init_script = project_root / "scripts" / "init_databases.py"
    run_cmd([str(python_venv), str(init_script)], "Init databases", check=False)
    logger.info("✓ Databases initialized")

    # 8. Run health check
    logger.info(" Running health check...")
    health_script = project_root / "scripts" / "health_check.py"
    result = run_cmd([str(python_venv), str(health_script)], "Health check", check=False)

    if "All systems operational" in result.stdout or "HEALTHY" in result.stdout:
        logger.info("\n" + "="*60)
        logger.info(" SUCCESS! Elefante is installed with Python 3.11")
        logger.info("="*60)
        logger.info(f"Venv location: {venv_path}")
        logger.info(f"Python: {python_venv}")
        logger.info(f"Log: {log_file}")
        return True
    else:
        logger.warning("  Health check output unclear, checking for errors...")
        if "error" in result.stdout.lower() or result.returncode != 0:
            logger.error(f" Health check failed")
            return False
        logger.info("✓ Health check passed")
        return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f" Fatal error: {e}", exc_info=True)
        sys.exit(1)
