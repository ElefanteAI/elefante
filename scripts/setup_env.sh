#!/bin/bash
# Elefante Environment Setup Script for Agent Zero / Non-Docker deployments

set -e

REPO_DIR="/a0/usr/projects/elefante/elefante-repo-files"
VENV_PATH="$REPO_DIR/.venv"

echo "=== Starting Elefante Environment Setup ==="

if [ ! -d "$REPO_DIR" ]; then
    echo "ERROR: $REPO_DIR not found. Extracted bundle first."
    exit 1
fi

cd "$REPO_DIR"

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
