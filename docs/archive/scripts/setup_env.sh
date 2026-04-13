#!/bin/bash
# Elefante Environment Setup Script for Agent Zero / Non-Docker deployments

set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PATH="$REPO_DIR/.venv"

echo "=== Starting Elefante Environment Setup ==="

cd "$REPO_DIR" || { echo "ERROR: Could not cd to $REPO_DIR"; exit 1; }

echo "--- Creating virtual environment ---"
python3 -m venv .venv

echo "--- Installing dependencies ---"
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "--- Verifying installation ---"
if .venv/bin/python -c "import fastapi; import chromadb; import kuzu; print('All core dependencies OK')" ; then
    echo "=== Setup Successful! ==="
    echo "Use this python path for your MCP configuration:"
    echo "$VENV_PATH/bin/python"
else
    echo "ERROR: One or more dependencies failed to install correctly."
    exit 1
fi
