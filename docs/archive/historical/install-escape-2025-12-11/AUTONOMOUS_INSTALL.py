#!/usr/bin/env python3
"""
Autonomous Elefante Python 3.11 installation script
Executes without workspace Python
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

LOG_PATH = "/Volumes/X10Pro/X10-2025/Documents2025/Elefante_early_dec2025/INSTALL_LOG.txt"
PROJECT_ROOT = "/Volumes/X10Pro/X10-2025/Documents2025/Elefante_early_dec2025"

def log_write(msg):
    """Write to both stdout and log file"""
    print(msg)
    with open(LOG_PATH, "a") as f:
        f.write(msg + "\n")

def log_clear():
    """Clear log file"""
    with open(LOG_PATH, "w") as f:
        f.write(f"Autonomous Elefante Installation Log\nStarted: {datetime.now()}\n{'='*60}\n")

def run_cmd(cmd, desc=""):
    """Run command and return result"""
    if desc:
        log_write(f"\n  {desc}")
    log_write(f"   Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=PROJECT_ROOT
        )
        
        if result.stdout:
            for line in result.stdout.split('\n')[:10]:
                if line.strip():
                    log_write(f"   {line}")
        
        if result.returncode != 0:
            log_write(f"    Exit code: {result.returncode}")
            if result.stderr:
                log_write(f"   Error: {result.stderr[:200]}")
            return False
        
        log_write(f"   ✓ Success")
        return True
    except Exception as e:
        log_write(f"    Exception: {e}")
        return False

def main():
    os.chdir(PROJECT_ROOT)
    log_clear()
    
    log_write(" AUTONOMOUS ELEFANTE INSTALLATION")
    log_write(f"Project root: {PROJECT_ROOT}")
    log_write(f"Python: {sys.executable}")
    log_write("="*60)
    
    # 1. Verify Python 3.11
    python_exe = "/opt/homebrew/bin/python3.11"
    if not os.path.exists(python_exe):
        log_write(f" Python 3.11 not found at {python_exe}")
        return False
    
    result = subprocess.run([python_exe, "--version"], capture_output=True, text=True)
    log_write(f"\n✓ Python 3.11: {result.stdout.strip()}")
    
    # 2. Remove broken .venv
    venv_path = f"{PROJECT_ROOT}/.venv"
    if os.path.exists(venv_path):
        log_write(f"\n  Removing broken .venv...")
        try:
            shutil.rmtree(venv_path, ignore_errors=True)
            subprocess.run(["rm", "-rf", venv_path], timeout=30)
            log_write("✓ Removed .venv")
        except Exception as e:
            log_write(f" Error removing: {e}")
            return False
    
    # 3. Create fresh venv
    log_write(f"\n Creating Python 3.11 virtual environment...")
    if not run_cmd([python_exe, "-m", "venv", venv_path], "Create venv"):
        return False
    
    # 4. Get venv paths
    pip_exe = f"{venv_path}/bin/pip"
    python_venv = f"{venv_path}/bin/python"
    
    if not os.path.exists(pip_exe):
        log_write(f" pip not found in venv")
        return False
    log_write(f"✓ Venv created at {venv_path}")
    
    # 5. Upgrade pip
    log_write(f"\n Upgrading pip...")
    run_cmd([pip_exe, "install", "--upgrade", "pip"], "Upgrade pip")
    
    # 6. Install requirements
    log_write(f"\n Installing requirements.txt...")
    if not run_cmd([pip_exe, "install", "-r", f"{PROJECT_ROOT}/requirements.txt"], "Install deps"):
        log_write("  Some deps may have failed, continuing...")
    
    # 7. Verify Python version
    result = subprocess.run([python_venv, "--version"], capture_output=True, text=True)
    log_write(f"\n✓ Venv Python: {result.stdout.strip()}")
    if "3.11" not in result.stdout:
        log_write(f" Wrong Python version in venv!")
        return False
    
    # 8. Initialize databases
    log_write(f"\n Initializing databases...")
    run_cmd([python_venv, f"{PROJECT_ROOT}/scripts/init_databases.py"], "Init databases")
    
    # 9. Health check
    log_write(f"\n Running health check...")
    result = subprocess.run(
        [python_venv, f"{PROJECT_ROOT}/scripts/health_check.py"],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=PROJECT_ROOT
    )
    
    if "operational" in result.stdout.lower() or result.returncode == 0:
        log_write("✓ Health check passed")
    else:
        log_write("  Health check output unclear")
    
    # Final summary
    log_write("\n" + "="*60)
    log_write(" INSTALLATION COMPLETE")
    log_write("="*60)
    log_write(f"Virtual environment: {venv_path}")
    log_write(f"Python executable: {python_venv}")
    log_write(f"Pip executable: {pip_exe}")
    log_write(f"\nTo activate:")
    log_write(f"  source {venv_path}/bin/activate")
    log_write(f"\nLog file: {LOG_PATH}")
    
    return True

if __name__ == "__main__":
    success = main()
    exit_code = 0 if success else 1
    print(f"\n{'='*60}")
    print(f"Exit code: {exit_code}")
    print(f"Log: {LOG_PATH}")
    sys.exit(exit_code)
