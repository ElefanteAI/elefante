# Elefante

<p align="center">
  <img src="docs/assets/Elefante Logo 1024 white.png" alt="Elefante" width="256">
</p>

**Elefante never forgets.**

AI agents start every conversation from zero. Your preferences, decisions, and discovered patterns don't carry over. Elefante gives any MCP-compatible agent a persistent, local second brain — memories are stored, scored automatically, and surfaced at the right moment without being asked.

**v2.2.2** — Persistent Memory Engine

```
┌─────────────────────────────────────────────────────────────┐
│ YOUR IDE (VS Code · Cursor · Windsurf · any MCP client)     │
└────────────────────────┬────────────────────────────────────┘
                         │ MCP stdio
┌────────────────────────▼────────────────────────────────────┐
│ LAYER 1 · MCP PROTOCOL                                      │
│ 20 tools · Compliance Gate · Context Injection              │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│ LAYER 2 · INTELLIGENCE ENGINE                               │
│ Orchestrator · 6-signal scoring · Hybrid Memory             │
│ (ChromaDB vectors + Kuzu graph)                             │
└────────────────────────┬────────────────────────────────────┘
                         │ snapshot.json
┌────────────────────────▼────────────────────────────────────┐
│ LAYER 3 · DASHBOARD                                         │
│ Read-only view of your second brain's health                │
│ http://127.0.0.1:8000                                       │
└─────────────────────────────────────────────────────────────┘
```

Every memory stored. Every context surfaced. Nothing forgotten.

---

## What It Does

Elefante is a local-first persistent memory engine for AI agents, connected via the [Model Context Protocol](https://modelcontextprotocol.io/) (MCP).

- **Stores** facts, preferences, decisions, code patterns, and tasks
- **Searches** using hybrid retrieval — semantic vectors, knowledge graph, and session context
- **Scores** every memory automatically using 6 behavioral signals (recency, reinforcement, type, frequency, freshness, context fit) — no manual ratings
- **Injects context** silently into every tool call — the agent gets relevant history without asking
- **Connects knowledge** through an entity-relationship graph
- **Enforces quality** via a compliance gate: search before write, no duplicates
- **Visualizes** brain health through a snapshot-driven dashboard

Everything runs locally. No cloud. No telemetry. Your data stays on your machine.

---

## How It Works

### Layer 1 — MCP Protocol

The interface between your IDE and the memory engine. 20 tools that let agents store, search, connect, and manage knowledge. A **Compliance Gate** prevents duplicates before they exist. **Context Injection** attaches relevant memories to every tool response. **Directives** enforce persistent behavioral rules that survive across sessions.

Full tool reference → [docs/technical/usage.md](docs/technical/usage.md)
IDE configuration → [docs/technical/ide-mcp-configuration.md](docs/technical/ide-mcp-configuration.md)

### Layer 2 — Intelligence Engine

Two storage backends working together:

- **ChromaDB** — 768-dimensional semantic vectors for meaning-based retrieval across months of history.
- **Kuzu** — a knowledge graph that tracks entities, relationships, and structural context.
- **Behavioral Relevance** — a 6-signal scoring system that automatically surfaces the most useful memories. No manual importance ratings.

Scoring details → [docs/README.md](docs/README.md#behavioral-relevance-v1100)
Architecture → [docs/technical/architecture.md](docs/technical/architecture.md)

### Layer 3 — Dashboard

A read-only view of your knowledge system, served from a lightweight snapshot so the agent stays fast:

- Health score with diagnostic panels
- Searchable, sortable memory table
- Topic distribution, memory insights, and a knowledge graph

Dashboard details → [docs/technical/dashboard.md](docs/technical/dashboard.md)
Docker deployment → [docs/technical/docker.md](docs/technical/docker.md)

---

## Designed For

Elefante works with any MCP-compatible client today — VS Code, Cursor, Windsurf, and others. It is built to scale into fully autonomous agent frameworks (Docker-sandboxed, multi-agent, long-running) where persistent memory across sessions is not optional.

---

## One-Click Installation (Zero Config)

**Requirements:** Python 3.11+ (tested up to 3.13), Git

Our installer detects your OS, creates a segregated virtual environment, installs all deps, initializes local graph and vector databases, and **automatically configures VS Code, Cursor, and Bob-IDE** to connect to Elefante via MCP.

```bash
# macOS / Linux (Mac curl coming soon, git clone for now)
git clone https://github.com/elefante/elefante.git
cd elefante
chmod +x install.sh && ./install.sh

# Windows
git clone https://github.com/elefante/elefante.git
cd elefante
install.bat
```

You possess full local control. The installer automatically bridges into your IDE and injects a single "Seed Memory" to prove the connection.

**The 60-Second Proof of Work:**
1. Restart your IDE.
2. Open your AI Chat (Copilot, Cursor, etc).
3. Copy/paste exactly this question: 
   `What is my Elefante test passcode?`
4. Watch the AI hit your local memory, cure its amnesia, and return the secret code.

*Looking for manual setup or deep technical details? See the [Full Installation Guide](docs/technical/installation.md).*

---

## MCP Tools

20 tools + 2 prompts. All names follow `elefante-PascalCase` convention.

| Category   | Tools                                                                                                                                   |
| ---------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Memory     | `elefante-MemoryAdd`, `elefante-MemorySearch`, `elefante-MemoryUpdate`, `elefante-MemoryDelete`, `elefante-MemoryConsolidate` |
| Graph      | `elefante-GraphConnect`, `elefante-GraphQuery`                                                                                      |
| Context    | `elefante-ContextGet`, `elefante-SessionsList`                                                                                      |
| Tasks      | `elefante-TaskCreate`, `elefante-TaskUpdate`, `elefante-TaskGraph`                                                                |
| ETL        | `elefante-ETLProcess`, `elefante-ETLClassify`                                                                                       |
| Directives | `elefante-DirectiveAdd`, `elefante-DirectiveList`, `elefante-DirectiveRemove`                                                     |
| System     | `elefante-System`, `elefante-SystemStatusGet`, `elefante-DashboardOpen`                                                           |

Full reference with parameter schemas → [docs/technical/usage.md](docs/technical/usage.md)

## Native Spec-Driven Development (SDD)

Elefante is the foundation for context-safe Spec-Driven Development. To prevent your AI agent from hallucinating or overloading its token context with massive architectural specs, Elefante enforces the **Gatekeeper & Oracle** pattern:

1. **The Gatekeeper (System Prompt):** Your `.cursorrules` or `copilot-instructions.md` should only contain strict instructions mandating that the agent query Elefante before writing code.
2. **The Oracle (Elefante DB):** You store your massive architectural specs (like database schemas or API contracts) inside Elefante as `SPECIFICATION` memory types. 
3. **The Retrieval:** Specs are mathematically guaranteed an Authority Score of `1.0`. When the Gatekeeper forces the agent to search, the Oracle perfectly surfaces only the exact specification needed for the current task.

---

## Tech Stack

| Purpose      | Technology                       |
| ------------ | -------------------------------- |
| Vector store | ChromaDB 1.3.5                   |
| Graph store  | Kuzu 0.11.3                      |
| Embeddings   | sentence-transformers (gte-base) |
| Protocol     | MCP 1.23.1                       |
| Dashboard    | React + TypeScript + Vite        |
| Runtime      | Python 3.11                      |

---

## Repo Structure

```
src/              Core engine, MCP server, dashboard
docs/             Technical reference, guides, debug compendiums
examples/         Agent tutorial and integration patterns
tests/            Unit, integration, and verification tests
scripts/          Setup, deployment, and maintenance tools
vscode-extension/ VS Code extension source
```

---

## Documentation

Full reference → [docs/README.md](docs/README.md)

- [Tool reference](docs/technical/usage.md) — parameter schemas for all 20 tools
- [Behavioral Relevance](docs/README.md#behavioral-relevance-v1100) — how automatic scoring works
- [Installation](docs/technical/installation.md) — step-by-step setup
- [Architecture](docs/technical/architecture.md) — system design
- [Dashboard](docs/technical/dashboard.md) — visualization and health monitoring
- [Docker](docs/technical/docker.md) — containerized deployment
- [Debugging](docs/debug/README.md) — troubleshooting guide

---

## Contributing & License

See [CONTRIBUTING.md](CONTRIBUTING.md).

**License:** [Business Source License 1.1](LICENSE) — free for non-competitive use. Converts to Apache 2.0 on 2029-02-10.

[Changelog](CHANGELOG.md) · [Full Documentation](docs/README.md)
