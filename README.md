# Elefante

<p align="center">
  <img src="docs/assets/Elefante Logo 1024 black 2.png" alt="Elefante" width="256">
</p>

**Elefante never forgets.**

AI agents start every conversation from zero. Your preferences, decisions, and discovered patterns don't carry over. Elefante gives any MCP-compatible agent a persistent, local second brain — memories are stored, scored automatically, and surfaced at the right moment without being asked.

**v2.5.2** — Persistent Memory Engine

```
┌─────────────────────────────────────────────────────────────┐
│ YOUR IDE (VS Code · Cursor · Windsurf · any MCP client)     │
└────────────────────────┬────────────────────────────────────┘
                         │ MCP stdio
┌────────────────────────▼────────────────────────────────────┐
│ LAYER 1 · MCP PROTOCOL                                      │
│ 20 tools · 2 prompts · Context Injection                    │
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

The interface between your IDE and the memory engine. 20 tools and 2 prompts let agents store, search, connect, and manage knowledge. A **Compliance Gate** prevents duplicates before they exist. **Context Injection** attaches relevant memories to every tool response. **Directives** enforce persistent behavioral rules that survive across sessions. **Token Intelligence** measures every response and tells the agent what each tool call costs — output tokens, protocol overhead, and signal ratio — so memory never becomes invisible bloat.

Full tool reference → [docs/technical/spec-tools.md](docs/technical/spec-tools.md)
IDE configuration → [docs/technical/ops-ide-configuration.md](docs/technical/ops-ide-configuration.md)

### Layer 2 — Intelligence Engine

Two storage backends working together:

- **ChromaDB** — 768-dimensional semantic vectors for meaning-based retrieval across months of history.
- **Kuzu** — a knowledge graph that tracks entities, relationships, and structural context.
- **Behavioral Relevance** — a 6-signal scoring system that automatically surfaces the most useful memories. No manual importance ratings.

Scoring details → [docs/technical/spec-scoring.md](docs/technical/spec-scoring.md)
Architecture → [docs/technical/spec-architecture.md](docs/technical/spec-architecture.md)

### Layer 3 — Dashboard

A read-only view of your knowledge system, served from a lightweight snapshot so the agent stays fast:

- Health score with diagnostic panels
- Searchable, sortable memory table
- Topic distribution, memory insights, and a knowledge graph

Dashboard details → [docs/technical/ops-dashboard.md](docs/technical/ops-dashboard.md)
Docker deployment → [docs/technical/ops-docker.md](docs/technical/ops-docker.md)

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

*Looking for manual setup or deep technical details? See the [Full Installation Guide](docs/technical/ops-installation.md).*

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

Full reference with parameter schemas → [docs/technical/spec-tools.md](docs/technical/spec-tools.md)

## Specification And Directive Retrieval

Elefante keeps durable architecture rules out of the live prompt by separating lightweight agent instructions from retrieved knowledge:

1. **Keep the instruction file small.** Your `.cursorrules`, `copilot-instructions.md`, or equivalent should tell the agent to search Elefante before writing code or declaring work complete.
2. **Store durable rules in Elefante.** Architecture contracts, schemas, and team process belong in `specification` or `directive` memories rather than inside a giant prompt file.
3. **Retrieve only what is relevant.** When the agent searches, Elefante surfaces the specific rule needed for the current task instead of injecting an entire handbook into every prompt.

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
```

---

## Documentation

Full reference → [docs/technical/spec-tools.md](docs/technical/spec-tools.md)

- [Tool reference](docs/technical/spec-tools.md) — parameter schemas for all 20 tools and 2 prompts
- [Behavioral Relevance](docs/technical/spec-scoring.md) — how automatic scoring works
- [Installation](docs/technical/ops-installation.md) — step-by-step setup
- [Architecture](docs/technical/spec-architecture.md) — system design
- [Dashboard](docs/technical/ops-dashboard.md) — visualization and health monitoring
- [Docker](docs/technical/ops-docker.md) — containerized deployment
- [Debugging](docs/debug/README.md) — known issues tracker, compendium routing, and verification commands

---

## Contributing & License

See [CONTRIBUTING.md](CONTRIBUTING.md).

**License:** [Business Source License 1.1](LICENSE) — free for non-competitive use. Converts to Apache 2.0 on 2029-02-10.

[Changelog](CHANGELOG.md) · [Full Documentation](docs/README.md)
