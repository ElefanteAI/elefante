# Elefante v1.6.0

Local-first, privacy-first memory for AI agents.

Elefante runs on your machine and gives your agent durable memory across sessions using:

- Semantic search (ChromaDB)
- A knowledge graph (Kuzu)
- Conversation/session context

It is MCP-native: your IDE launches the server and the agent calls tools.

> **Current release:** v1.6.0 (Compliance Gate)

---

## What you get (in practice)

- Remember facts, preferences, decisions, and tasks (with structured classification)
- Search memories with hybrid retrieval (vector + graph + context)
- Build/query a knowledge graph (entities + relationships)
- ETL workflow for agent classification (process → classify → status)
- Snapshot-driven dashboard to visualize the graph safely

---

## Install

Prereqs:

- Python **3.11**
- ~5GB free disk recommended

Automated install (recommended):

Windows:

```bash
install.bat
```

macOS/Linux:

```bash
chmod +x install.sh
./install.sh
```

Installer details and safeguards: [`docs/technical/installation.md`](docs/technical/installation.md)

---

## Connect your IDE (MCP)

Elefante is an MCP stdio server.

- Command: `<repo>/.venv/bin/python`
- Args: `-m src.mcp.server`
- Env:
  - `PYTHONPATH=/absolute/path/to/Elefante`
  - `ELEFANTE_CONFIG_PATH=/absolute/path/to/Elefante/config.yaml`

Authoritative setup guide (VS Code / Cursor / Bob / Antigravity): [`docs/technical/ide-mcp-configuration.md`](docs/technical/ide-mcp-configuration.md)

Manual startup + handshake verification: [`docs/technical/mcp-server-startup.md`](docs/technical/mcp-server-startup.md)

---

## Usage

Elefante is driven by your AI agent via MCP tools. There are **four main capabilities**:

---

### 1. Memory (store, search, maintain)

**Store** → `elefanteMemoryAdd`  
Save a memory with full classification. The agent must always provide:

| Field | Purpose |
|-------|--------|
| `content` | The actual text to remember |
| `layer` | Who/what/do: `self`, `world`, or `intent` |
| `sublayer` | Fine classification (see table below) |
| `memory_type` | Kind of knowledge: `preference`, `fact`, `decision`, `task`, etc. |
| `domain` | Context: `work`, `personal`, `project`, `learning`, `reference`, `system` |
| `importance` | Priority 1–10 (use 8+ for critical items) |
| `category` | Topic grouping (e.g. `elefante`, `python`) |
| `tags` | Array of keywords for filtering |
| `entities` | Array of `{name, type}` to link in the graph |

**Layer/sublayer quick reference**:

| Layer | Sublayers | When to use |
|-------|-----------|-------------|
| `self` | identity, preference, constraint | About the user: who they are, what they like, limits |
| `world` | fact, failure, method | Objective knowledge: truths, errors encountered, how-tos |
| `intent` | rule, goal, anti-pattern | Directives: what to do, what to avoid |

**Search** → `elefanteMemorySearch`  
Find memories using semantic, structured, or hybrid mode.  
Critical: rewrite queries to be standalone (no pronouns like "it" or "that").

**Maintain** → `elefanteMemoryConsolidate` | `elefanteMemoryListAll`  
Cleanup duplicates or export/inspect all stored memories.

---

### 2. Knowledge Graph (entities + relationships)

**Create nodes** → `elefanteGraphEntityCreate`  
**Create edges** → `elefanteGraphRelationshipCreate`  
**Batch upsert** → `elefanteGraphConnect` (entities + edges in one call)  
**Query** → `elefanteGraphQuery` (Cypher)

Use the graph when you want explicit structure (who works on what, what depends on what).

---

### 3. Context & History

**Get context** → `elefanteContextGet`  
Retrieves session context + related memories + graph connections for the current task.

**Browse sessions** → `elefanteSessionsList`  
List past sessions ("episodes") with summaries.

---

### 4. ETL Classification (batch processing)

**Get items** → `elefanteETLProcess`  
**Classify** → `elefanteETLClassify`  
**Stats** → `elefanteETLStatus`

Use when you want a deliberate "classify these" workflow.

---

### Dashboard

`elefanteDashboardOpen` — Opens the visual knowledge graph. Use `refresh=true` to regenerate the snapshot first.

---

### System / Safety

`elefanteSystemStatusGet` — Status and lock info.  
`elefanteSystemEnable` / `elefanteSystemDisable` — Multi-IDE safety (usually automatic in v1.1.0+).

---

### STAC (Simple Terms And Concise)

When search returns results, the explanation shows **why** each result surfaced. STAC is the agent output style:

- **Why surfaced**: one line (key signals)
- **Relevance**: one line (tie to your request)
- **Next**: one line (do/ask one thing)

Example:

> "Why: vector 0.91, authority 0.88, temporal 0.96. Relevance: matches your installation question. Next: add keyword 'Python 3.11' or confirm OS."

---

Full parameter schemas and advanced tools: [`docs/technical/usage.md`](docs/technical/usage.md)

## MCP surface (code-truth)

Elefante exposes **18 tools + 2 prompts**. The root README focuses on “how to use” rather than listing every schema field.

Authoritative, complete list (including advanced/admin tools): [`docs/technical/usage.md`](docs/technical/usage.md)

---

## Dashboard (snapshot-driven)

The dashboard is intentionally read-only and snapshot-based to avoid Kuzu lock conflicts.

Recommended:

- Use `elefanteDashboardOpen` (optionally with refresh)

Manual start:

```bash
python -m src.dashboard.server
```

Snapshot refresh:

```bash
python scripts/update_dashboard_data.py
```

Then refresh the browser.

Guide: [`docs/technical/dashboard.md`](docs/technical/dashboard.md)

---

## Safety & troubleshooting

- Start with the canonical operating rules: [`docs/technical/developer-etiquette.md`](docs/technical/developer-etiquette.md)
- Lock behavior and troubleshooting: [`docs/technical/kuzu-lock-monitoring.md`](docs/technical/kuzu-lock-monitoring.md)
- Debug “laws” (read before debugging): [`docs/debug/README.md`](docs/debug/README.md)

Rollback/backup runbook (anchored to v1.5.0): [`docs/technical/rollback.md`](docs/technical/rollback.md)

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

---

## Links

- Repository: https://github.com/jsubiabreIBM/Elefante
- Changelog: [`CHANGELOG.md`](CHANGELOG.md)
- Docs index: [`docs/README.md`](docs/README.md)

Built for AI agents that never forget.
