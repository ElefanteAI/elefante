#!/bin/bash
# Elefante One-Click Installer for Mac/Linux
# ==========================================

set -e

# Setup Logging
LOG_FILE="$(pwd)/.elefante-install.log"
STATUS_FILE="$(pwd)/.elefante-install-status.txt"
SUMMARY_FILE="$(pwd)/.elefante-install-summary.txt"
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
log "[INFO] Log file: $LOG_FILE"
log "[INFO] Status file: $STATUS_FILE"
log "[INFO] Summary file: $SUMMARY_FILE"
log "[INFO] Press Ctrl+C to request cancellation at the next safe checkpoint."
log ""

# 1. Check for Python 3.11 - 3.13
log "[INFO] Checking for compatible Python (3.11 - 3.13)..."

find_python() {
    for cmd in python3.13 python3.12 python3.11 python3 python; do
        if command -v "$cmd" &> /dev/null; then
            if "$cmd" -c 'import sys; sys.exit(0 if (3,11) <= sys.version_info < (3,14) else 1)' &> /dev/null; then
                echo "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

PYTHON_CMD=$(find_python)

if [ -z "$PYTHON_CMD" ]; then
    log "[ERROR] No compatible Python found. Requires 3.11, 3.12, or 3.13."
    log "[ERROR] Python 3.14+ is NOT supported due to Pydantic V1 limits."
    log "Please install Python 3.13 from python.org or Homebrew (brew install python@3.13)."
    exit 1
fi

log "[INFO] Using $($PYTHON_CMD --version)"
log "[INFO] Repository virtual environment strategy will be handled by install.py"

# 2. Run Python Installer
log "[INFO] Starting installation wizard..."
"$PYTHON_CMD" scripts/setup/install.py --log-file "$LOG_FILE" --status-file "$STATUS_FILE" --summary-file "$SUMMARY_FILE"
