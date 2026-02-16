# Elefante

Persistent memory for AI coding agents. Elefante runs locally on your machine via [MCP](https://modelcontextprotocol.io/) (Model Context Protocol), storing knowledge in a vector database and a knowledge graph. Your agent remembers what you care about, forgets what you don't, and scores every memory based on how you actually use it — not how important you *said* it was.

> **Current version:** v1.10.0

---

## The Problem

AI agents are stateless. Every new session starts from zero. The agent doesn't remember your coding style, the architecture decision you made last week, what failed yesterday, or that you hate semicolons. You repeat yourself. The agent repeats its mistakes. Context is lost at the worst possible moment.

## What Elefante Does

Elefante gives your agent a second brain — one that learns what matters from your behavior, not from labels you assign.

- **Stores** facts, preferences, decisions, code patterns, and tasks
- **Searches** using hybrid retrieval: semantic similarity (vectors) + knowledge graph traversal + session context
- **Scores** every memory automatically based on recency, how often you access it, and when you last used it — no manual importance ratings
- **Injects context** on every tool call — the agent gets the most relevant memories without asking
- **Builds a knowledge graph** of entities and relationships (people, projects, technologies, dependencies)
- **Enforces quality** via a compliance gate: the agent must search before writing, preventing duplicates
- **Visualizes** knowledge through a snapshot-driven dashboard

## How It Works

```
IDE (VS Code, Cursor, etc.)
  └── MCP stdio connection
        └── Elefante Server (Python)
              ├── ChromaDB (semantic vector search)
              ├── Kuzu (knowledge graph, Cypher queries)
              ├── Context Injector (auto-surfaces relevant memories)
              └── Compliance Gate (search-before-write)
```

Everything runs locally. No cloud. No telemetry. Your data never leaves your machine.

---

## Behavioral Relevance (v1.10.0)

This is the core idea behind v1.10.0: **nobody assigns importance. Importance emerges from behavior.**

Traditional systems ask you to rate memories on a scale (1–10). That approach has two problems:

1. **Bias.** Users rate everything as "important" (8+).
2. **Rot.** An architecture decision from 6 months ago sits at importance=9 forever, even if the project moved on.

Elefante replaces human-assigned importance with a **system-computed score (0–100)** that changes over time based on three behavioral signals:

| Signal | What it measures | Effect |
|--------|-----------------|--------|
| **Recency** | Days since creation | Memories decay exponentially. Rate depends on type — a rule decays ~20x slower than a conversation. |
| **Freshness** | Days since last access | Recently retrieved memories get a boost. Stale ones fade. |
| **Reinforcement** | Number of times accessed | Frequently used memories grow stronger (logarithmic, so spamming won't game it). |

### The Formula

```
relevance = 0.5 * recency * freshness * reinforcement
```

Where:
- `recency = exp(-decay_rate * days_since_created)` — decay_rate varies by memory type
- `freshness = exp(-0.02 * days_since_accessed)`
- `reinforcement = 1 + 0.25 * ln(access_count + 1)`

Every memory starts at score **50**. It earns its way up through use, and loses ground through neglect. The raw formula produces 0.0–1.0, stored as an integer 0–100.

### Decay Rates by Memory Type

The decay rate (λ) controls how quickly a memory loses relevance if it's never accessed. Each type has a half-life — the number of days until a memory drops to half its initial score:

| Memory Type | Decay Rate (λ) | Half-Life | Why |
|-------------|----------------|-----------|-----|
| `rule` | 0.002 | ~347 days | Rules persist, but die if never enforced |
| `preference` | 0.002 | ~347 days | Preferences are stable but not eternal |
| `decision` | 0.005 | ~139 days | Decisions get revisited |
| `fact` | 0.005 | ~139 days | Facts change |
| `answer` | 0.005 | ~139 days | Answers may become outdated |
| `insight` | 0.008 | ~87 days | Insights are validated or forgotten |
| `code` | 0.008 | ~87 days | Code evolves constantly |
| `hypothesis` | 0.01 | ~69 days | Hypotheses get tested |
| `question` | 0.015 | ~46 days | Questions get answered |
| `note` | 0.015 | ~46 days | Notes are transient |
| `observation` | 0.015 | ~46 days | Observations are contextual |
| `task` | 0.02 | ~35 days | Tasks complete or go stale |
| `conversation` | 0.025 | ~28 days | Conversations are ephemeral |

A rule you set 6 months ago and still use? Score stays high. An architecture decision from a year ago that you never reference? It fades. Naturally.

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

## Connect to Your IDE

Elefante is an MCP stdio server. Add it to your IDE's MCP configuration:

- **Command:** `<repo>/.venv/bin/python`
- **Args:** `-m src.mcp.server`
- **Env:**
  - `PYTHONPATH=/absolute/path/to/Elefante`
  - `ELEFANTE_CONFIG_PATH=/absolute/path/to/Elefante/config.yaml`

Setup guides for VS Code, Cursor, and other MCP-compatible IDEs: [`docs/technical/ide-mcp-configuration.md`](docs/technical/ide-mcp-configuration.md)

---

## MCP Tools

Elefante exposes **17 tools** and **2 prompts** via MCP. All tool names follow the `elefante-PascalCase` convention.

### Memory

| Tool | Purpose |
|------|---------|
| `elefante-MemoryAdd` | Store a memory. Classify it by `memory_type` (fact, decision, preference, etc.) and let the system handle scoring. |
| `elefante-MemorySearch` | Search memories — semantic, structured (graph), or hybrid mode. Use `list_all=true` to dump everything. |
| `elefante-MemoryUpdate` | Amend a memory: correct content, deprecate, archive, or set supersession chains. |
| `elefante-MemoryDelete` | Permanently delete a memory with audit trail. Requires prior search. |
| `elefante-MemoryConsolidate` | Cleanup: deduplicate, canonicalize keys, quarantine test data. Dry-run by default. |

### Knowledge Graph

| Tool | Purpose |
|------|---------|
| `elefante-GraphConnect` | Batch upsert: create entities and relationships in one call. |
| `elefante-GraphQuery` | Execute raw Cypher queries for advanced traversals. |

### Context & Sessions

| Tool | Purpose |
|------|---------|
| `elefante-ContextGet` | Get full context: related memories + graph connections for current work. |
| `elefante-SessionsList` | List past sessions with summaries. |

### Tasks

| Tool | Purpose |
|------|---------|
| `elefante-TaskCreate` | Create a task with priority, agent assignment, dependencies, and optional inline subtasks. |
| `elefante-TaskUpdate` | Update task status and attach output. |
| `elefante-TaskGraph` | View task hierarchy. |

### ETL (Batch Processing)

| Tool | Purpose |
|------|---------|
| `elefante-ETLProcess` | Get unprocessed memories for agent review. Use `include_stats=true` for processing statistics. |
| `elefante-ETLClassify` | Submit classification for a memory. |

### System

| Tool | Purpose |
|------|---------|
| `elefante-System` | Enable or disable Elefante Mode (`action="enable"` / `action="disable"`). |
| `elefante-SystemStatusGet` | Check system health, lock state, and database stats. |
| `elefante-DashboardOpen` | Open the knowledge graph dashboard. |

### Prompts

| Prompt | Purpose |
|--------|---------|
| `elefante-grounding` | Injects memory-aware behavior into the agent's system prompt. |
| `elefante-context` | Searches memories for a topic and returns results as context. |

Full parameter schemas: [`docs/technical/usage.md`](docs/technical/usage.md)

---

## How Memories Are Classified

When you store a memory, the agent provides two things:

1. **`memory_type`** — What kind of knowledge this is. This determines the decay rate (see table above). Choose accurately: a `preference` will last ~347 days without use, while a `conversation` fragment fades in ~28 days.

2. **`domain`** — High-level context: `work`, `personal`, `learning`, `project`, `reference`, or `system`.

That's it. No importance scale. No layer/sublayer taxonomy. The score takes care of itself.

### What the Agent Does NOT Set

- **Score** — Starts at 50 for every memory. Changes only through behavior (access, time decay).
- **Decay rate** — Derived automatically from `memory_type`.
- **Authority score** — Computed from score, access count, and freshness during retrieval.

---

## Automatic Context Injection

Every tool call (except search and system tools) automatically gets the top 3 most relevant memories appended to its response. The agent doesn't need to manually search — context surfaces on its own.

Tools that skip injection (they already return memory data or are system operations):

`elefante-MemorySearch`, `elefante-MemoryAdd`, `elefante-MemoryUpdate`, `elefante-MemoryDelete`, `elefante-ContextGet`, `elefante-MemoryConsolidate`, `elefante-System`, `elefante-SystemStatusGet`, `elefante-DashboardOpen`, `elefante-SessionsList`, `elefante-ETLProcess`, `elefante-ETLClassify`

---

## Compliance Gate

These tools are blocked until the agent has called `elefante-MemorySearch` at least once in the session:

- `elefante-MemoryAdd`
- `elefante-MemoryUpdate`
- `elefante-MemoryDelete`
- `elefante-GraphConnect`

This prevents agents from writing memories without first checking what already exists. Search once, then write freely for the rest of the session.

---

## Dashboard

The dashboard is a read-only graph visualization. It reads from a snapshot file, not directly from the databases, to avoid lock conflicts with the MCP server.

```bash
# Via MCP tool (recommended)
elefante-DashboardOpen(refresh=true)

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
  core/         Orchestrator, ChromaDB store, Kuzu store, retrieval, config
  models/       Data models (Memory, Entity, Relationship, Query filters)
  dashboard/    FastAPI server + React UI
    ui/         TypeScript SPA (Vite + Tailwind)
  etl/          Batch memory processing pipeline
  distiller/    Memory ingestion and export
  utils/        Validators, curation, helpers
scripts/        Maintenance (snapshot refresh, migrations)
data/           Runtime data (databases, snapshots)
docs/           Documentation
tests/          Test suite
```

---

## Documentation

| Doc | Content |
|-----|---------|
| [`.github/copilot-instructions.md`](.github/copilot-instructions.md) | Agent behavior configuration (search-before-answer protocol) |
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

This project is licensed under the [Business Source License 1.1](LICENSE). You may use it freely for any non-competitive purpose. It converts to Apache 2.0 on 2029-02-10.

---

[Changelog](CHANGELOG.md) · [GitHub](https://github.com/ElefanteAI/elefante)
