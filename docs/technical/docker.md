# Running Elefante in Docker (Beginner)

This guide shows how to run Elefante in a clean Docker environment.

If you are an autonomous agent operating inside an Agent Zero / A0 project layout, read `docs/technical/agent_handoff.md` first.

## What you will get

- A container running the Elefante dashboard server on port 8000.
- A persistent data folder on your host machine at `./elefante_data/`.

## Prerequisites

- Docker Desktop installed and running.

## Best practice: clone from GitHub inside the Docker environment

If your Docker environment can reach GitHub, cloning is the cleanest way to ensure you have the latest Elefante `main`.

If your destination folder already contains `.a0proj/`, do not use `git clone <url> .` (git refuses cloning into a non-empty directory).
Use one of the clone patterns in the "Agent Zero / A0 projects" section below.

## If you cannot clone: generate a copy/paste bundle

If your Docker environment cannot access GitHub, generate a tarball on your machine and upload/copy it into the Docker environment.

```bash
chmod +x scripts/package_docker_bundle.sh
./scripts/package_docker_bundle.sh
```

This creates `dist/elefante-docker-bundle.tar.gz`.

In the Docker environment, extract it:

```bash
mkdir -p /a0/usr/projects/elefante/elefante-repo-files
tar -xzf elefante-docker-bundle.tar.gz -C /a0/usr/projects/elefante/elefante-repo-files
cd /a0/usr/projects/elefante/elefante-repo-files
docker compose up -d --build
```

## Step-by-step

1. Open a terminal in the project root.
2. Build and start the container:

```bash
docker compose up --build
```

1. Open the dashboard in your browser:

- <http://localhost:8000>

## Agent Zero / A0 projects (recommended clone layout)

If your Docker environment has an Agent Zero project folder like:

- `/a0/usr/projects/elefante/.a0proj/` (project metadata)
- `/a0/usr/projects/elefante/` (intended code root)

Do not use `git clone <url> .` if the directory is not empty (for example, because `.a0proj/` exists). Git will refuse to clone into a non-empty directory.

Use one of these two safe patterns instead.

### Pattern A (simple, safe): clone into a subfolder

```bash
cd /a0/usr/projects/elefante
git clone --depth 1 https://github.com/ElefanteAI/elefante elefante-repo-files
cd elefante-repo-files
docker compose up -d --build
```

### Pattern B (repo files at project root): git init + fetch + checkout

This keeps `.a0proj/` untouched and places Elefante code at `/a0/usr/projects/elefante/`.

```bash
cd /a0/usr/projects/elefante

# Initialize git in-place (safe when .a0proj exists)
git init
git remote add origin https://github.com/ElefanteAI/elefante || true
git fetch --depth 1 origin main
git checkout -B main FETCH_HEAD

docker compose up -d --build
```

## Initialize databases and generate the dashboard snapshot

The dashboard reads a snapshot file located under the Elefante data directory.

Run these one-time setup commands:

```bash
# Create/update the dashboard snapshot JSON
docker compose run --rm elefante python scripts/update_dashboard_data.py

# (Optional) verify the system
docker compose run --rm elefante python scripts/health_check.py
```

Then restart the dashboard server if needed:

```bash
docker compose up
```

## Important note about MCP

Elefante MCP is designed to be started by your IDE and communicate over stdio.

If you are using **Agent Zero (A0)**, you can configure the MCP server by updating your `mcpServers` JSON object. See [docs/technical/agent_handoff.md](docs/technical/agent_handoff.md) for the exact JSON snippet to add to your `mcp_servers.json` or equivalent configuration file.

Running MCP inside Docker is possible but is an advanced setup (you have to bridge stdio/tooling into your IDE).
For beginners, use Docker for the dashboard and scripts first.
