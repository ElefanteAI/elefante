# Elefante

Persistent memory system for AI coding agents. Runs locally via [MCP](https://modelcontextprotocol.io/) (Model Context Protocol), stores knowledge in a vector database (ChromaDB) and a graph database (Kuzu). Your agent remembers decisions, preferences, facts, and project context across sessions.

> **Current version:** v1.8.0

---

## Why

AI agents are stateless. Every new session starts from zero — no memory of your coding style, past decisions, project conventions, or what failed last time. Elefante gives agents persistent memory so they stop repeating mistakes and start building on prior work.

## What it does

- **Stores** facts, preferences, decisions, code patterns, and tasks with structured classification
- **Searches** memories using hybrid retrieval (semantic vectors + knowledge graph + session context)
- **Injects context** automatically — every tool call gets the top relevant memories appended to the response (v1.8.0)
- **Builds a knowledge graph** of entities and relationships (people, projects, concepts, dependencies)
- **Enforces quality** via a compliance gate: agents must search before writing, preventing duplicate or contradictory memories
- **Visualizes** the knowledge graph through a snapshot-driven dashboard

## How it works

```
IDE (VS Code, Cursor, etc.)
  └── MCP stdio connection
        └── Elefante Server (Python)
              ├── ChromaDB (semantic vector search)
              ├── Kuzu (knowledge graph, Cypher queries)
              ├── Context Injector (auto-surfaces relevant memories)
              └── Compliance Gate (search-before-write)
```

Everything runs locally. No cloud. No telemetry.

---

## Install

**Requirements:** Python 3.11, ~5 GB disk space.

macOS / Linux:

```bash
chmod +x install.sh
./install.sh
```

Windows:

```bash
install.bat
```

The installer creates a virtual environment, installs dependencies, and initializes the databases. See [`docs/technical/installation.md`](docs/technical/installation.md) for details.

---

## Connect to your IDE

Elefante is an MCP stdio server. Add it to your IDE's MCP configuration:

- **Command:** `<repo>/.venv/bin/python`
- **Args:** `-m src.mcp.server`
- **Env:**
  - `PYTHONPATH=/absolute/path/to/Elefante`
  - `ELEFANTE_CONFIG_PATH=/absolute/path/to/Elefante/config.yaml`

Setup guides for VS Code, Cursor, and other MCP-compatible IDEs: [`docs/technical/ide-mcp-configuration.md`](docs/technical/ide-mcp-configuration.md)

---

## MCP Tools

Elefante exposes **22 tools** and **2 prompts** via MCP.

### Memory

| Tool | Purpose |
|------|---------|
| `elefanteMemoryAdd` | Store a memory with layer/sublayer classification, importance, tags, and entity links |
| `elefanteMemorySearch` | Search memories — semantic, structured (graph), or hybrid mode |
| `elefanteMemoryListAll` | Retrieve all memories without filtering (for inspection or export) |
| `elefanteMemoryConsolidate` | Cleanup: deduplicate, canonicalize keys, quarantine test data |
| `elefanteMemoryMigrateToV3` | Admin: migrate memories to V3 schema |

### Knowledge Graph

| Tool | Purpose |
|------|---------|
| `elefanteGraphEntityCreate` | Create an entity node (person, project, concept, technology, etc.) |
| `elefanteGraphRelationshipCreate` | Create a directed edge between two entities |
| `elefanteGraphConnect` | Batch upsert: create multiple entities and relationships in one call |
| `elefanteGraphQuery` | Execute raw Cypher queries for advanced traversals |

### Context & Sessions

| Tool | Purpose |
|------|---------|
| `elefanteContextGet` | Get full context: related memories + graph connections for current work |
| `elefanteSessionsList` | List past sessions with summaries |

### Tasks

| Tool | Purpose |
|------|---------|
| `elefanteTaskCreate` | Create a task with priority, agent assignment, and dependencies |
| `elefanteTaskDecompose` | Break a task into subtasks |
| `elefanteTaskUpdate` | Update task status and attach output |
| `elefanteTaskGraph` | View task hierarchy |

### ETL (Batch Classification)

| Tool | Purpose |
|------|---------|
| `elefanteETLProcess` | Get unclassified memories for agent review |
| `elefanteETLClassify` | Submit classification for a memory |
| `elefanteETLStatus` | Get processing statistics |

### System

| Tool | Purpose |
|------|---------|
| `elefanteSystemEnable` | Activate Elefante and acquire database locks (required first step) |
| `elefanteSystemDisable` | Release locks for multi-IDE safety |
| `elefanteSystemStatusGet` | Check system health, lock state, and database stats |
| `elefanteDashboardOpen` | Open the knowledge graph dashboard |

### Prompts

| Prompt | Purpose |
|--------|---------|
| `elefante-grounding` | Injects memory-aware behavior into the agent's system prompt |
| `elefante-context` | Searches memories for a topic and returns results as context |

Full parameter schemas: [`docs/technical/usage.md`](docs/technical/usage.md)

---

## Memory Classification

Every memory is classified on two axes:

**Layer** (who / what / do):

| Layer | Sublayers | Use for |
|-------|-----------|---------|
| `self` | identity, preference, constraint | User info: who they are, what they like, their limits |
| `world` | fact, failure, method | Objective knowledge: truths, errors, how-tos |
| `intent` | rule, goal, anti-pattern | Directives: what to do, what to avoid |

**Importance** (1–10): Use 8+ for critical preferences, decisions, and architectural facts.

---

## Automatic Context Injection (v1.8.0)

Every tool call (except search/system tools) automatically gets the top 3 most relevant memories appended to its response. The agent doesn't need to manually search — context surfaces on its own.

Tools that skip injection (because they already return memory data or are system operations):

`elefanteMemorySearch`, `elefanteMemoryAdd`, `elefanteMemoryListAll`, `elefanteContextGet`, `elefanteMemoryConsolidate`, `elefanteMemoryMigrateToV3`, `elefanteSystemEnable`, `elefanteSystemDisable`, `elefanteSystemStatusGet`, `elefanteDashboardOpen`, `elefanteSessionsList`, `elefanteETLProcess`, `elefanteETLClassify`, `elefanteETLStatus`

---

## Compliance Gate

These tools are blocked until the agent has called `elefanteMemorySearch` at least once in the session:

- `elefanteMemoryAdd`
- `elefanteGraphEntityCreate`
- `elefanteGraphRelationshipCreate`
- `elefanteGraphConnect`

This prevents agents from writing memories without first checking what already exists.

---

## Dashboard

The dashboard is a read-only graph visualization. It reads from a snapshot file, not directly from the databases, to avoid lock conflicts with the MCP server.

```bash
# Via MCP tool (recommended)
elefanteDashboardOpen(refresh=true)

# Manual
python scripts/update_dashboard_data.py   # refresh snapshot
python -m src.dashboard.server            # start on port 8000
```

Guide: [`docs/technical/dashboard.md`](docs/technical/dashboard.md)

---

## Docker

Run the dashboard in Docker for a reproducible environment:

```bash
docker-compose up
```

The MCP server itself runs as a stdio process started by your IDE. Running MCP inside Docker requires additional configuration. See [`docs/technical/docker.md`](docs/technical/docker.md).

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Vector store | ChromaDB 1.3.5 | Semantic search via embeddings |
| Graph store | Kuzu 0.11.3 | Knowledge graph, Cypher queries |
| Embeddings | sentence-transformers (gte-base) | 768-dim vectors for similarity |
| Protocol | MCP 1.23.1 | IDE–server communication |
| Dashboard | React + TypeScript + Vite | Graph visualization (Canvas 2D) |
| API server | FastAPI + Uvicorn | Dashboard backend |
| Runtime | Python 3.11 | All server-side code |

---

## Project Structure

```
src/
  mcp/          Server, tool handlers, context injection, compliance gate
  core/         Orchestrator, ChromaDB store, Kuzu store, config
  models/       Data models (Memory, Entity, Relationship)
  dashboard/    FastAPI server + React UI
    ui/         TypeScript SPA (Vite + Tailwind)
  etl/          Batch memory classification pipeline
scripts/        Maintenance (snapshot refresh, migrations)
data/           Runtime data (databases, snapshots)
docs/           Documentation
tests/          Test suite
```

---

## Documentation

| Doc | Content |
|-----|---------|
| [`docs/technical/usage.md`](docs/technical/usage.md) | Complete tool reference with parameter schemas |
| [`docs/technical/installation.md`](docs/technical/installation.md) | Installation details |
| [`docs/technical/ide-mcp-configuration.md`](docs/technical/ide-mcp-configuration.md) | IDE setup (VS Code, Cursor, etc.) |
| [`docs/technical/mcp-server-startup.md`](docs/technical/mcp-server-startup.md) | Manual startup and handshake verification |
| [`docs/technical/dashboard.md`](docs/technical/dashboard.md) | Dashboard usage |
| [`docs/technical/docker.md`](docs/technical/docker.md) | Docker setup |
| [`docs/technical/second-brain-protocols.md`](docs/technical/second-brain-protocols.md) | Safety protocols |
| [`docs/technical/kuzu-lock-monitoring.md`](docs/technical/kuzu-lock-monitoring.md) | Lock behavior and troubleshooting |
| [`docs/technical/rollback.md`](docs/technical/rollback.md) | Backup and rollback |
| [`docs/debug/README.md`](docs/debug/README.md) | Debugging guide |

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

MIT. See [`LICENSE`](LICENSE).

---

[Changelog](CHANGELOG.md) · [GitHub](https://github.com/ElefanteAI/elefante)
