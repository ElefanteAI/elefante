# Elefante

Persistent memory for AI coding agents. Runs locally via [MCP](https://modelcontextprotocol.io/), storing knowledge in a vector database (ChromaDB) and a knowledge graph (Kuzu). Your agent remembers what matters — scored by behavior, not by labels.

> **v1.10.0** — Behavioral Relevance + tool renaming release

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

17 tools + 2 prompts. All names follow `elefante-PascalCase` convention.

| Category | Key Tools |
|----------|-----------|
| Memory | `elefante-MemoryAdd`, `elefante-MemorySearch`, `elefante-MemoryUpdate`, `elefante-MemoryDelete`, `elefante-MemoryConsolidate` |
| Graph | `elefante-GraphConnect`, `elefante-GraphQuery` |
| Context | `elefante-ContextGet`, `elefante-SessionsList` |
| Tasks | `elefante-TaskCreate`, `elefante-TaskUpdate`, `elefante-TaskGraph` |
| ETL | `elefante-ETLProcess`, `elefante-ETLClassify` |
| System | `elefante-System`, `elefante-SystemStatusGet`, `elefante-DashboardOpen` |

Full reference with parameter schemas: [docs/technical/usage.md](docs/technical/usage.md)

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Vector store | ChromaDB 1.3.5 |
| Graph store | Kuzu 0.11.3 |
| Embeddings | sentence-transformers (gte-base) |
| Protocol | MCP 1.23.1 |
| Dashboard | React + TypeScript + Vite |
| Runtime | Python 3.11 |

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
