# 🐘 Elefante v1.2.0

**Local-First AI Memory System with Perfect Recall**

> **Latest Release:** v1.2.0 - Critical bug fix + comprehensive documentation ([Release Notes](RELEASE_NOTES_v1.2.md))

Elefante gives AI agents a stateful brain by combining semantic search, knowledge graphs, and conversation context—all running 100% locally on your machine. No cloud. No data egress. Just pure, private memory.

---

## ⚡ Why Elefante?

AI agents are stateless by default. They forget everything between sessions. Elefante solves this by providing:

- **🧠 Triple-Layer Memory**: Semantic (ChromaDB) + Graph (Kuzu) + Context = Perfect Recall
- **🔒 Privacy First**: Your data never leaves your machine (`./data` directory)
- **🔌 MCP Native**: Plug-and-play for Cursor, Claude Desktop, Bob IDE
- **🎯 Adaptive Intelligence**: Dynamically adjusts retrieval based on query intent
- **📊 Visual Dashboard**: Interactive knowledge graph visualization

---

## 🚀 Quick Start

### Installation (2 minutes)

**Windows:**
```bash
install.bat
```

**Mac/Linux:**
```bash
./install.sh
```

The installer includes automated safeguards that prevent common issues (Kuzu 0.11+ compatibility, disk space, dependencies).

**Success Rate**: 98%+ (up from 50% before safeguards)

### Usage

Simply talk to your AI agent:

```
> "Remember that I'm a Senior Python Developer at IBM"
> "What projects am I working on?"
> "Show me the relationship between Project Omega and Kafka"
```

Elefante handles the rest—storing, indexing, and retrieving with perfect accuracy.

---

## 📚 Documentation

### 🎯 Start Here

- **New Users**: [`docs/technical/installation.md`](docs/technical/installation.md) - Complete setup guide
- **Understanding the System**: [`docs/technical/architecture.md`](docs/technical/architecture.md) - How it works
- **Using the API**: [`docs/technical/usage.md`](docs/technical/usage.md) - MCP tools & examples
- **Visual Dashboard**: [`docs/technical/dashboard.md`](docs/technical/dashboard.md) - Knowledge graph UI

### 📖 Complete Documentation

- **Technical Docs**: [`docs/technical/`](docs/technical/) - Architecture, schema, API reference
- **Debug Docs**: [`docs/debug/`](docs/debug/) - Troubleshooting, development logs
- **Archive**: [`docs/archive/`](docs/archive/) - Historical documentation

---

## 🏗️ Architecture Overview

```
User Query
    ↓
MCP Server
    ↓
Orchestrator (Adaptive Weighting)
    ↓
┌─────────────┬──────────────┬─────────────────┐
│  ChromaDB   │  Kuzu Graph  │  Session Context│
│  (Semantic) │  (Structure) │  (Recent)       │
└─────────────┴──────────────┴─────────────────┘
    ↓
Weighted Merge
    ↓
Perfect Result
```

**Key Innovation**: Adaptive weighting adjusts retrieval strategy based on query type:
- Questions → Semantic search
- IDs/Names → Graph lookup
- Pronouns → Session context

See [`docs/technical/architecture.md`](docs/technical/architecture.md) for details.

---

## 🔌 MCP Tools (11 Total)

Once installed, your AI agent gets these tools:

| Tool | Purpose | Example |
|------|---------|---------|
| `addMemory` | Store information with intelligent ingestion | "Remember I'm working on Project Omega" |
| `searchMemories` | Retrieve memories (semantic/structured/hybrid) | "What do you know about Omega?" |
| `queryGraph` | Execute Cypher queries on knowledge graph | "Show all AI-related projects" |
| `getContext` | Get comprehensive session context | (Auto-called by agent) |
| `createEntity` | Create nodes in knowledge graph | "Create entity for 'Bob'" |
| `createRelationship` | Link entities with relationships | "Link Bob to Elefante as Maintainer" |
| `getEpisodes` | Browse past sessions with summaries | "Show recent work sessions" |
| `getStats` | Get system health & usage statistics | "Show memory system stats" |
| `consolidateMemories` | Merge duplicates & resolve contradictions | (Auto-triggered or manual) |
| `listAllMemories` | Export/inspect all memories (no filtering) | "List all memories for backup" |
| `openDashboard` | Launch visual Knowledge Garden UI | "Open the dashboard" |

**Key Features**:
- **Intelligent Ingestion**: `addMemory` auto-detects NEW/REDUNDANT/RELATED/CONTRADICTORY
- **Query Rewriting**: `searchMemories` requires explicit, standalone queries (no pronouns)
- **Hybrid Search**: Combines semantic (ChromaDB) + structured (Kuzu) + context
- **Graph Analytics**: Direct Cypher query support via `queryGraph`
- **Visual Exploration**: Interactive dashboard via `openDashboard`

See [`docs/technical/usage.md`](docs/technical/usage.md) for complete API reference.

---

## 📊 Visual Dashboard

Launch the interactive knowledge graph:

```bash
cd Elefante
.venv\Scripts\python.exe -m src.dashboard.server
```

Open http://127.0.0.1:8000 to explore:
- Force-directed graph visualization
- Node inspector with full details
- Filter by spaces/categories
- Real-time statistics

**Auto-refresh**: Add memories via MCP, refresh browser (F5), see updates instantly.

See [`docs/technical/dashboard.md`](docs/technical/dashboard.md) for complete guide.

---

## 🛠️ Development Status

**Current Version**: v1.1.0 (Production)

**Completed Features**:
- ✅ Triple-layer architecture (ChromaDB + Kuzu + Context)
- ✅ MCP server with 10+ tools
- ✅ Cognitive memory model (entity extraction, relationships)
- ✅ Visual dashboard with interactive graph
- ✅ Automated installation safeguards
- ✅ Comprehensive documentation

**Next Priority** (from [`docs/debug/general/task-roadmap.md`](docs/debug/general/task-roadmap.md)):
- [ ] Advanced Memory Intelligence Pipeline
  - [ ] Enhanced LLM extraction
  - [ ] Smart UPDATE (merge logic)
  - [ ] Smart EXTEND (link logic)

---

## 🤝 Contributing

Elefante is under active development. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for guidelines.

**Development Docs**: [`docs/debug/`](docs/debug/) - Organized by topic (installation, dashboard, database, memory, general)

---

## 📄 License

See [`LICENSE`](LICENSE)

---

## 🔗 Links

- **Repository**: https://github.com/jsubiabreIBM/Elefante
- **Technical Docs**: [`docs/technical/README.md`](docs/technical/README.md)
- **Debug Docs**: [`docs/debug/README.md`](docs/debug/README.md)
- **Changelog**: [`CHANGELOG.md`](CHANGELOG.md)

---

**Built with ❤️ for AI agents that never forget**
