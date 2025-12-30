#!/usr/bin/env python3
import os, sys, shutil, subprocess
from pathlib import Path

os.chdir("/Volumes/X10Pro/X10-2025/Documents2025/Elefante_early_dec2025")
venv = Path(".venv")

print(" STARTING AUTONOMOUS INSTALL")
print(f"Current dir: {os.getcwd()}")
print(f"Python: /opt/homebrew/bin/python3.11")

# Remove .venv
if venv.exists():
    print(f"Removing {venv}...")
    shutil.rmtree(venv, ignore_errors=True)
    subprocess.run(["rm", "-rf", str(venv)], timeout=30)

# Create venv
print("Creating venv...")
subprocess.run(["/opt/homebrew/bin/python3.11", "-m", "venv", str(venv)], check=True)

pip = venv / "bin" / "pip"
python = venv / "bin" / "python"

# Install
print("Installing requirements...")
subprocess.run([str(pip), "install", "-r", "requirements.txt"], check=False, timeout=600)

# Init DB
print("Initializing databases...")
subprocess.run([str(python), "scripts/init_databases.py"], check=False, timeout=120)

# Health check
print("Running health check...")
result = subprocess.run([str(python), "scripts/health_check.py"], capture_output=True, text=True, timeout=120)
print(result.stdout[-500:] if result.stdout else "No output")

print("\n COMPLETE")
print(f"Venv: {venv.absolute()}")
print(f"Python: {python.absolute()}")
