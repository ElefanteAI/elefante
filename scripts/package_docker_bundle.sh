#!/usr/bin/env bash
set -euo pipefail

# Creates a small, copy-friendly tarball for running Elefante (dashboard + scripts) in Docker.
# This is intended for environments where you cannot `git clone` directly.
#
# Output:
#   dist/elefante-docker-bundle.tar.gz

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$ROOT_DIR/dist"
OUT_FILE="$OUT_DIR/elefante-docker-bundle.tar.gz"

mkdir -p "$OUT_DIR"

# Build an include list so we don't accidentally package local data.
INCLUDE_PATHS=(
  ".dockerignore"
  "Dockerfile"
  "docker-compose.yml"
  "README.md"
  "LICENSE"
  "requirements.txt"
  "config.yaml"
  "src"
  "scripts/health_check.py"
  "scripts/update_dashboard_data.py"
  "docs/technical/agent_handoff.md"
  "docs/technical/docker.md"
)

cd "$ROOT_DIR"

# Ensure included files exist (fail fast with a clear message)
for p in "${INCLUDE_PATHS[@]}"; do
  if [[ ! -e "$p" ]]; then
    echo "Missing required path for bundle: $p" >&2
    exit 1
  fi
done

# Create tarball
# - Exclude any VCS metadata and local environments
# - Exclude runtime data folders
# - Exclude caches

tar -czf "$OUT_FILE" \
  --exclude-vcs \
  --exclude=".venv" \
  --exclude="venv" \
  --exclude="env" \
  --exclude="__pycache__" \
  --exclude="*.pyc" \
  --exclude=".pytest_cache" \
  --exclude=".mypy_cache" \
  --exclude=".ruff_cache" \
  --exclude=".DS_Store" \
  --exclude="data" \
  --exclude="elefante_data" \
  --exclude="chroma_db" \
  --exclude="dist" \
  "${INCLUDE_PATHS[@]}"

echo "Wrote bundle: $OUT_FILE" >&2
