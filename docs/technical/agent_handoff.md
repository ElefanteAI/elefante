# Agent Handoff: Elefante MCP + Docker (Agent Zero / A0)

This document is written for an autonomous agent that will receive this repository (or a bundle of it) and must get Elefante operational inside an Agent Zero container layout.

## Mission (what success looks like)

1. **Environment Ready**: A dedicated Python 3.11 virtual environment is created and all `requirements.txt` are installed.
2. **Dashboard Operates**: Elefante dashboard runs in Docker (or locally) and is reachable at `http://localhost:8000`.
3. **MCP Server Integration**: Agent Zero is configured to use the Elefante MCP server using the venv's python executable.

## Non-negotiable constraints

- **Python 3.11** is the supported baseline. (If the container only has 3.13, try to create a venv and install; if databases fail to compile, you may need a 3.11 image).
- **No emojis** in any output.
- **Compliance Gate (search-before-write)** is enforced:
  - You MUST call `elefanteMemorySearch` before any write tool.
- **STDOUT PURITY**: The MCP server MUST NOT print anything to `stdout` except JSON-RPC. All logs go to `stderr`. `ModuleNotFoundError` on startup will kill the connection.

## Environment Setup (Critical First Step)

Before running the MCP server, you MUST install the dependencies. Do not use the system python; use a virtual environment.

**Quick Setup:**
```bash
chmod +x scripts/setup_env.sh
./scripts/setup_env.sh
```

**Manual Setup (if script fails):**
```bash
cd /a0/usr/projects/elefante/elefante-repo-files
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Agent Zero MCP Configuration

If your A0 environment is already running, you can configure the MCP server in the settings. Use the full path to the `.venv` you just created.

**Configuration JSON:**
```json
{
  "mcpServers": {
    "elefante": {
      "command": "/a0/usr/projects/elefante/elefante-repo-files/.venv/bin/python",
      "args": ["-m", "src.mcp.server"],
      "env": {
        "ELEFANTE_DATA_DIR": "/data",
        "PYTHONPATH": "/a0/usr/projects/elefante/elefante-repo-files"
      },
      "cwd": "/a0/usr/projects/elefante/elefante-repo-files",
      "description": "Elefante Local AI Memory System (ChromaDB + Kuzu)"
    }
  }
}
```

## Where this project lives in Agent Zero

Recommended location:

- `/a0/usr/projects/elefante/` (Agent Zero project root)
- `/a0/usr/projects/elefante/.a0proj/` already exists and must remain untouched

Because `.a0proj/` makes the directory non-empty, `git clone <url> .` will fail.

## Getting the latest code (preferred)

### Pattern A (safe): clone into a subfolder

```bash
cd /a0/usr/projects/elefante
git clone --depth 1 https://github.com/ElefanteAI/elefante elefante-repo-files
cd elefante-repo-files
```

### Pattern B (repo files at project root): git init + fetch + checkout

```bash
cd /a0/usr/projects/elefante
git init
git remote add origin https://github.com/ElefanteAI/elefante || true
git fetch --depth 1 origin main
git checkout -B main FETCH_HEAD
```

## If GitHub is blocked: use the bundle tarball

If a bundle tarball was provided (example name: `elefante-docker-bundle.tar.gz`):

```bash
mkdir -p /a0/usr/projects/elefante/elefante-repo-files
tar -xzf elefante-docker-bundle.tar.gz -C /a0/usr/projects/elefante/elefante-repo-files
cd /a0/usr/projects/elefante/elefante-repo-files
```

## Run the dashboard in Docker

### Start container

```bash
docker compose up -d --build
```

### Generate the snapshot (required for meaningful dashboard data)

```bash
docker compose run --rm elefante python scripts/update_dashboard_data.py
```

### Verify health (optional)

```bash
docker compose run --rm elefante python scripts/health_check.py
```

### Open dashboard

- `http://localhost:8000`

## Run the MCP server (stdio)

The MCP server is designed to be started by an IDE/client and communicate over stdio.

Use the configuration JSON provided in the **Agent Zero MCP Configuration** section above. Ensure the path to the `python` executable correctly points to your `.venv`.

From the repo root (inside your venv):

```bash
python -m src.mcp.server
```

If you need to verify the MCP handshake (outside Docker, in this repo):

```bash
python scripts/verify_mcp_handshake.py
```

## What to read first (fast orientation)

- `docs/debug/mcp-code-neural-register.md`
- `docs/debug/database-neural-register.md`
- `docs/debug/dashboard-neural-register.md`
- `docs/technical/architecture.md`
- `docs/technical/docker.md`

## Common failure modes

- Dashboard shows empty/old data: rerun `python scripts/update_dashboard_data.py` (or Docker equivalent) to regenerate the snapshot.
- Writes blocked: you forgot to call `elefanteMemorySearch` first.
- Path problems in Docker: ensure `ELEFANTE_DATA_DIR=/data` is set and volume is mounted (see `docker-compose.yml`).

## The "Installation Challenge" (Verify your setup)

As an autonomous agent, you must prove you can use this system effectively. Complete these three tasks to confirm your installation is valid:

### Challenge 1: The Retrieval Test
**Command:** Search for the project's "Version Bump Protocol".
**Required result:** You must find a reference to "LAW 13" and list at least 3 files that MUST be updated during a version change.

### Challenge 2: The Compliance Gate Test
**Command:** Attempt to call `elefanteMemoryAdd` with a new "dummy" memory BEFORE you have performed a search in this session.
**Required result:** The server MUST return a `BLOCKED` status or a "Compliance Gate" error. Paste the error message as proof.

### Challenge 3: The Integrated Loop
**Command:** 
1. Call `elefanteMemorySearch` for "Jaime's output preferences".
2. Based on the result, perform a `health_check.py` and save a new memory using `elefanteMemoryAdd` that summarizes the health status while following the output preferences.
**Required result:** A successful memory addition following the "No Emojis" and "BLUF" rules.
