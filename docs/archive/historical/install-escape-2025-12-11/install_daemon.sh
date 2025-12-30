#!/bin/bash
# Detached installation script - runs in background

PROJECT="/Volumes/X10Pro/X10-2025/Documents2025/Elefante_early_dec2025"
LOG="$PROJECT/install_daemon.log"

# Redirect all output
exec > "$LOG" 2>&1

echo " Starting daemon installation at $(date)"
cd "$PROJECT" || exit 1

# Kill any existing Python processes in this project
pkill -f "python.*$PROJECT" || true
sleep 2

# Remove broken venv
echo "Removing broken .venv..."
rm -rf .venv || true

# Create fresh venv with Python 3.11
echo "Creating venv with Python 3.11..."
/opt/homebrew/bin/python3.11 -m venv .venv || {
    echo "Failed to create venv"
    exit 1
}

# Install dependencies
echo "Installing dependencies..."
./.venv/bin/pip install --upgrade pip > /dev/null 2>&1
./.venv/bin/pip install -r requirements.txt > /dev/null 2>&1

# Initialize DB
echo "Initializing databases..."
./.venv/bin/python scripts/init_databases.py > /dev/null 2>&1

# Health check
echo "Running health check..."
./.venv/bin/python scripts/health_check.py

echo " Installation complete at $(date)"
echo "Log: $LOG"
echo "Venv: $PROJECT/.venv"
