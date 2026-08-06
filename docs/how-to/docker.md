# Running Elefante in Docker (Beginner)

This guide shows how to run Elefante in a clean Docker environment.

If you are an autonomous agent operating inside an Agent Zero / A0 project
layout, read [`agent-handoff.md`](agent-handoff.md) first.

## What you will get

- A container running the Elefante dashboard server on port 8000, published to this machine's loopback interface only.
- A persistent data folder on your host machine at `./elefante_data/`.

## Prerequisites

- Docker Desktop installed and running.

## Use a released source tag

If your Docker environment can reach GitHub, clone and check out the released
v2.12.2 tag. `main` is a development branch and is not the customer release
contract.

If your destination folder already contains `.a0proj/`, do not use `git clone <url> .` (git refuses cloning into a non-empty directory).
Use one of the clone patterns in the "Agent Zero / A0 projects" section below.

## If you cannot clone: generate a copy/paste bundle

If your Docker environment cannot access GitHub, generate a tarball on your machine and upload/copy it into the Docker environment.

```bash
chmod +x scripts/ci/bundle_docker_package.sh
./scripts/ci/bundle_docker_package.sh
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

3. Open the dashboard in your browser:

- <http://localhost:8000>

The bundled Compose configuration intentionally publishes `127.0.0.1:8000:8000`: the dashboard can return private memory content and is not a public web service. Compose sets `ELEFANTE_DASHBOARD_HOST=0.0.0.0` only inside its isolated container network so the loopback-published port can reach the process. The standalone image remains loopback-only. Do not expose this service directly; a trusted reverse proxy must provide authentication, an explicit `ELEFANTE_DASHBOARD_CORS_ORIGINS` allowlist, and network controls before any external access is considered.

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
git fetch --depth 1 origin tag v2.12.2
git checkout --detach v2.12.2
docker compose up -d --build
```

### Pattern B (repo files at project root): git init + fetch + checkout

This keeps `.a0proj/` untouched and places Elefante code at `/a0/usr/projects/elefante/`.

```bash
cd /a0/usr/projects/elefante

# Initialize git in-place (safe when .a0proj exists)
git init
git remote add origin https://github.com/ElefanteAI/elefante || true
git fetch --depth 1 origin tag v2.12.2
git checkout --detach FETCH_HEAD

docker compose up -d --build
```

## Initialize databases and generate the dashboard snapshot

The dashboard reads a snapshot file located under the Elefante data directory.

Run these one-time setup commands:

```bash
# Create/update the dashboard snapshot JSON
docker compose run --rm elefante python scripts/pipeline/update_dashboard_data.py

# (Optional) verify the system
docker compose run --rm elefante python scripts/verify/verify_health.py
```

Then restart the dashboard server if needed:

```bash
docker compose up
```

## Important note about MCP

The released customer topology is one local daemon plus transport-only bridges
configured by the platform installer. This Docker Compose file runs the
snapshot dashboard only; it is not a substitute for the customer runtime.

If you are using **Agent Zero (A0)**, you can configure the MCP server by updating your `mcpServers` JSON object. See [agent-handoff.md](agent-handoff.md) for the exact JSON snippet to add to your `mcp_servers.json` or equivalent configuration file.

Running the daemon or MCP bridge across a container boundary is an advanced,
community-tier setup. For beginners, use Docker only for the snapshot dashboard
and install the released customer runtime for IDE memory.
