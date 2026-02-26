# Elefante

**The Second Brain for AI Agents.** Your agent stops forgetting. Every preference, every decision, every pattern — remembered, scored, and surfaced at the moment of need.

> **v2.1.3** — Persistent Memory for AI Agents

```
┌─────────────────────────────────────────────────────────────┐
│                        YOUR IDE                             │
│  (VS Code, Cursor, Windsurf — any MCP-compatible client)    │
└────────────────────────┬────────────────────────────────────┘
                         │ MCP stdio
┌────────────────────────▼────────────────────────────────────┐
│              LAYER 1: MCP PROTOCOL                          │
│  20 tools · Compliance Gate · Context Injection             │
│  ┌─────────┐ ┌─────────────┐ ┌───────────┐ ┌────────────┐ │
│  │ Memory  │ │   Graph     │ │   Tasks   │ │  System    │ │
│  │ CRUD    │ │ Connect/    │ │ Create/   │ │ Status/    │ │
│  │ Search  │ │ Query       │ │ Decompose │ │ Dashboard  │ │
│  └────┬────┘ └──────┬──────┘ └─────┬─────┘ └─────┬──────┘ │
└───────┼─────────────┼──────────────┼──────────────┼────────┘
        │             │              │              │
┌───────▼─────────────▼──────────────▼──────────────▼────────┐
│              LAYER 2: INTELLIGENCE ENGINE                   │
│  Orchestrator · Adaptive Weighting · Behavioral Relevance   │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────────┐  │
│  │  ChromaDB    │ │    Kuzu      │ │  Cognitive         │  │
│  │  Semantic    │ │  Knowledge   │ │  Retrieval         │  │
│  │  Vectors     │ │  Graph       │ │  (6-signal score)  │  │
│  │  (768-dim)   │ │  (entities)  │ │                    │  │
│  └──────────────┘ └──────────────┘ └────────────────────┘  │
└──────────────────────┬──────────────────────────────────────┘
                       │ snapshot.json
┌──────────────────────▼──────────────────────────────────────┐
│              LAYER 3: DASHBOARD                             │
│  Read-only window into your knowledge system                │
│  ┌──────────┐ ┌────────────┐ ┌───────────────────────────┐ │
│  │ Overview │ │  Memories  │ │  Explore                  │ │
│  │ Health   │ │  Search    │ │  Topics · Insights · Graph│ │
│  │ Score    │ │  Table     │ │                           │ │
│  └──────────┘ └────────────┘ └───────────────────────────┘ │
│                 http://127.0.0.1:8000                       │
└─────────────────────────────────────────────────────────────┘
```

**The product is the cohesion.** MCP tools capture knowledge. The Intelligence Engine scores and connects it. The Dashboard shows you the health of your second brain. All three layers serve one purpose: _your agent gives better answers because it remembers._

---

## Quick Start

**Requirements:** Python 3.11, ~5 GB disk space

```bash
# macOS / Linux
chmod +x install.sh && ./install.sh

# Windows
install.bat
```

Connect to your IDE (VS Code, Cursor, etc.) via MCP stdio:

- **Command:** `<repo>/.venv/bin/python`
- **Args:** `-m src.mcp.server`
- **Env:** `PYTHONPATH` and `ELEFANTE_CONFIG_PATH` pointing to this repo

Full setup: [docs/technical/installation.md](docs/technical/installation.md) · [IDE configuration](docs/technical/ide-mcp-configuration.md)

---

## How It Works

### Layer 1: MCP Protocol

The bridge between your IDE and the brain. 20 tools that let agents store, search, connect, and manage knowledge. A **Compliance Gate** forces search-before-write — no duplicates, no noise. **Context Injection** silently attaches relevant memories to every tool call so the agent gets history without asking. **Directives** keep unconditional behavioral rules always present in every tool response — never dependent on search.

### Layer 2: Intelligence Engine

The brain. Two storage backends work together:

- **ChromaDB** (semantic vectors) finds memories by meaning — "how do we handle auth?" matches a decision about JWT tokens made three months ago.
- **Kuzu** (knowledge graph) tracks entities and relationships — who connects to what, which decisions depend on which facts.
- **Behavioral Relevance** scores every memory automatically. Recent, frequently-accessed, and type-appropriate memories surface first. No manual ratings.

### Layer 3: Dashboard

The window. A snapshot-driven read-only view of your knowledge system:

- **Overview**: Health score (freshness, coverage, connectivity) with diagnostic panels.
- **Memories**: Searchable, sortable table with semantic search integration.
- **Explore**: Topic distribution, memory insights, and a knowledge graph.

---

## What It Does

- **Stores** facts, preferences, decisions, code patterns, and tasks
- **Searches** using hybrid retrieval: semantic vectors + knowledge graph + session context
- **Scores** every memory automatically — recency, freshness, and reinforcement replace manual importance ratings
- **Injects context** into every tool call — the agent gets relevant memories without asking
- **Builds a knowledge graph** of entities and relationships
- **Enforces quality** via a compliance gate: search before write, no duplicates
- **Visualizes** knowledge through a snapshot-driven dashboard

Everything runs locally. No cloud. No telemetry. Your data stays on your machine.

---

## MCP Tools

20 tools + 2 prompts. All names follow `elefante-PascalCase` convention.

| Category   | Key Tools                                                                                                                     |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------- |
| Memory     | `elefante-MemoryAdd`, `elefante-MemorySearch`, `elefante-MemoryUpdate`, `elefante-MemoryDelete`, `elefante-MemoryConsolidate` |
| Graph      | `elefante-GraphConnect`, `elefante-GraphQuery`                                                                                |
| Context    | `elefante-ContextGet`, `elefante-SessionsList`                                                                                |
| Tasks      | `elefante-TaskCreate`, `elefante-TaskUpdate`, `elefante-TaskGraph`                                                            |
| ETL        | `elefante-ETLProcess`, `elefante-ETLClassify`                                                                                 |
| Directives | `elefante-DirectiveAdd`, `elefante-DirectiveList`, `elefante-DirectiveRemove`                                                 |
| System     | `elefante-System`, `elefante-SystemStatusGet`, `elefante-DashboardOpen`                                                       |

Full reference with parameter schemas: [docs/technical/usage.md](docs/technical/usage.md)

---

## Tech Stack

| Component    | Technology                       |
| ------------ | -------------------------------- |
| Vector store | ChromaDB 1.3.5                   |
| Graph store  | Kuzu 0.11.3                      |
| Embeddings   | sentence-transformers (gte-base) |
| Protocol     | MCP 1.23.1                       |
| Dashboard    | React + TypeScript + Vite        |
| Runtime      | Python 3.11                      |

---

## Documentation

The full reference lives in [docs/README.md](docs/README.md), covering:

- [Tool reference](docs/technical/usage.md) — complete parameter schemas
- [Behavioral Relevance](docs/README.md#behavioral-relevance-v1100) — how scoring works
- [Installation](docs/technical/installation.md) — detailed setup
- [Dashboard](docs/technical/dashboard.md) — graph visualization
- [Docker](docs/technical/docker.md) — containerized dashboard
- [Debugging](docs/debug/README.md) — troubleshooting guide
- [Architecture](docs/technical/architecture.md) — system design

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[Business Source License 1.1](LICENSE) — free for any non-competitive use. Converts to Apache 2.0 on 2029-02-10.

---

[Changelog](CHANGELOG.md) · [Full Documentation](docs/README.md)
