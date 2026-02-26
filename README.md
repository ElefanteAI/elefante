# Elefante

**Elefante never forgets.**

Your agent forgets the moment the conversation ends.
Every preference you fought for. Every decision you refined. Every pattern you discovered. Gone.

**Elefante ends that forever.**

It gives any AI agent a living, local, automatically scored second brain that injects exactly the right context at the exact moment it is needed. No more hallucinations from missing history. Just answers that feel like they came from you — every single time.

**v2.1.4** — Persistent Memory Engine

```
┌─────────────────────────────────────────────────────────────┐
│ YOUR IDE (VS Code · Cursor · Windsurf · any MCP client)     │
└────────────────────────┬────────────────────────────────────┘
                         │ MCP stdio
┌────────────────────────▼────────────────────────────────────┐
│ LAYER 1 · MCP PROTOCOL                                      │
│ 20 precision tools · Compliance Gate · Silent Context       │
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
│ Live window into the health of your second brain            │
│ http://127.0.0.1:8000                                       │
└─────────────────────────────────────────────────────────────┘
```

**Cohesion is the product.**
MCP captures. The Engine scores and connects. The Dashboard shows health. One unbreakable system.

---

## Why This Changes Everything

Most agents are brilliant for one chat and useless the next.
Elefante is the persistent memory layer they were missing — 100% local-first, zero telemetry, designed to travel cleanly from today's VS Code to tomorrow's fully autonomous environments like **Agent Zero**.

Agent Zero is a Docker-sandboxed autonomous powerhouse that executes real actions (terminal, apps, multi-agent orchestration, 24/7 operation — the kind of "crazy things" OpenClaw popularized but Agent Zero does more reliably). Elefante ensures it never forgets context across wild sessions, making true long-term autonomy possible.

---

## Deep Dive: What Elefante Actually Does

### Layer 1 — MCP Protocol (the bridge)

20 battle-tested tools that let agents store, search, connect and manage knowledge.
**Compliance Gate** blocks duplicates before they exist.
**Context Injection** silently attaches relevant memories to every call.
**Directives** enforce your unbreakable rules unconditionally.

Full tool reference + parameter schemas → [docs/technical/usage.md](docs/technical/usage.md)
IDE/MCP setup → [docs/technical/ide-mcp-configuration.md](docs/technical/ide-mcp-configuration.md)

### Layer 2 — Intelligence Engine (the brain)

- **ChromaDB** (768-dim semantic vectors) finds meaning across months.
- **Kuzu** (knowledge graph) tracks entities and relationships.
- **6-signal Behavioral Relevance** automatic scoring (recency + reinforcement + type + frequency + freshness + context fit) — no manual ratings ever.

How scoring works + examples → [docs/README.md#behavioral-relevance](docs/README.md#behavioral-relevance-v1100)
Full architecture → [docs/technical/architecture.md](docs/technical/architecture.md)

### Layer 3 — Dashboard (your cockpit)

Live read-only view: health score, searchable memories, topic map, live graph — all from a lightweight snapshot so the agent stays fast.

Dashboard deep dive → [docs/technical/dashboard.md](docs/technical/dashboard.md)
Docker version → [docs/technical/docker.md](docs/technical/docker.md)

---

## What Elefante Delivers Every Day

- Stores facts, preferences, decisions, code patterns, tasks
- Hybrid search (semantic + graph + session)
- Automatic 6-signal scoring
- Zero-friction context injection
- Enforced quality (search-before-write)
- Instant visual brain health

Full "What It Does" with examples → [docs/README.md](docs/README.md)

---

## Quick Start

**Requirements:** Python 3.11+, ~5 GB disk

```bash
# macOS / Linux
chmod +x install.sh && ./install.sh

# Windows
install.bat
```

Connect via MCP stdio:
- **Command:** `<repo>/.venv/bin/python`
- **Args:** `-m src.mcp.server`

Full installation → [docs/technical/installation.md](docs/technical/installation.md)

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

Full reference with parameter schemas → [docs/technical/usage.md](docs/technical/usage.md)

---

## Tech Stack

| Purpose       | Technology                      |
| ------------- | ------------------------------- |
| Vector store  | ChromaDB 1.3.5                  |
| Graph store   | Kuzu 0.11.3                     |
| Embeddings    | sentence-transformers (gte-base)|
| Protocol      | MCP 1.23.1                      |
| Dashboard     | React + TypeScript + Vite       |
| Runtime       | Python 3.11                     |

---

## Documentation

Everything lives in [docs/README.md](docs/README.md).

- [Tool reference](docs/technical/usage.md) — complete parameter schemas
- [Behavioral Relevance](docs/README.md#behavioral-relevance-v1100) — how scoring works
- [Installation](docs/technical/installation.md) — detailed setup
- [Dashboard](docs/technical/dashboard.md) — graph visualization
- [Docker](docs/technical/docker.md) — containerized dashboard
- [Debugging](docs/debug/README.md) — troubleshooting guide
- [Architecture](docs/technical/architecture.md) — system design

---

## Contributing & License

See [CONTRIBUTING.md](CONTRIBUTING.md).

**License:** Business Source License 1.1 — free for non-competitive use. Converts to Apache 2.0 on 2029-02-10.

[Changelog](CHANGELOG.md) · [Full Docs](docs/README.md)

---

This is Elefante.
**Elefante never forgets.**
**Elefante ends that forever.**
