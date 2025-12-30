#!/bin/bash
# Elefante One-Click Installer for Mac/Linux
# ==========================================

set -e

# Setup Logging
LOG_FILE="$(pwd)/install.log"
touch "$LOG_FILE"

log() {
    echo "$1" | tee -a "$LOG_FILE"
}

echo "============================================================" > "$LOG_FILE"
echo " ELEFANTE INSTALLATION LOG" >> "$LOG_FILE"
echo "Started at: $(date)" >> "$LOG_FILE"
echo "============================================================" >> "$LOG_FILE"

log "============================================================"
log " ELEFANTE INSTALLER"
log "============================================================"
log ""

# 1. Check for Python 3.11 explicitly (mandatory)
log "[INFO] Checking for Python 3.11..."
if command -v python3.11 &> /dev/null; then
    PYTHON_CMD=python3.11
elif command -v python3 &> /dev/null; then
    PYTHON_CMD=python3
elif command -v python &> /dev/null; then
    PYTHON_CMD=python
else
    log "[ERROR] Python is not installed."
    log "Please install Python 3.11 from python.org or Homebrew (brew install python@3.11)."
    exit 1
fi

PY_VER="$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [ "$PY_VER" != "3.11" ]; then
    log "[ERROR] Python 3.11 is required (found $PY_VER)."
    log "Install Python 3.11 and re-run: python3.11 -m venv .venv"
    exit 1
fi

log "[INFO] Using $($PYTHON_CMD --version)"

# 2. Create Virtual Environment
if [ ! -d ".venv" ]; then
    log "[INFO] Creating virtual environment..."
    $PYTHON_CMD -m venv .venv
else
    log "[INFO] Virtual environment already exists."
fi

# 3. Activate Virtual Environment
log "[INFO] Activating virtual environment..."
source .venv/bin/activate

# 4. Run Python Installer
log "[INFO] Starting installation wizard..."
python scripts/install.py --log-file "$LOG_FILE"
