import sys
import subprocess
import os
from datetime import datetime

LOG_FILE = "docs/archive/historical/2025-12-06-implementation-log.md"

def log(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = f"\n- **{timestamp}**: {message}"
    print(message)
    with open(LOG_FILE, "a") as f:
        f.write(entry)

def check_install():
    log("Verifying Critical Dependencies...")
    
    python_exec = sys.executable
    log(f"Using Python: `{python_exec}`")
    
    required = ["mcp", "chromadb", "kuzu", "pydantic"]
    missing = []
    
    for pkg in required:
        try:
            __import__(pkg)
            log(f" Package `{pkg}` is importable.")
        except ImportError as e:
            log(f" Package `{pkg}` FAILED: {e}")
            missing.append(pkg)
            
    if missing:
        log(f" Missing packages: {', '.join(missing)}. Attempting FORCE install...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)
            log(" Force install completed.")
        except Exception as e:
            log(f" Force install failed: {e}")
    else:
        log(" All critical dependencies verified.")

if __name__ == "__main__":
    check_install()
