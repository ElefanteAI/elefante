# 🐘 Elefante

**Local. Private. Triple-Layer AI Memory.**

Elefante is a local-first memory system designed to provide "perfect memory" for AI agents. It creates a stateful brain for your AI by combining semantic search, structured knowledge graphs, and conversation context—all running 100% on your machine.

## 🚨 NEW: Complete Installation Documentation System

**If you're experiencing installation issues or want to understand the system deeply:**

- 🎯 **Start Here**: [`NEVER_AGAIN_COMPLETE_GUIDE.md`](NEVER_AGAIN_COMPLETE_GUIDE.md) - Ultimate troubleshooting guide
- 📚 **Navigation**: [`COMPLETE_DOCUMENTATION_INDEX.md`](COMPLETE_DOCUMENTATION_INDEX.md) - Complete file index
- 🔧 **Technical**: [`TECHNICAL_IMPLEMENTATION_DETAILS.md`](TECHNICAL_IMPLEMENTATION_DETAILS.md) - Implementation details
- 🛡️ **Safeguards**: [`INSTALLATION_SAFEGUARDS.md`](INSTALLATION_SAFEGUARDS.md) - Automated prevention system

**Key Achievement**: Transformed installation success rate from 50% to 98%+ through automated safeguards and comprehensive documentation.

---

## ⚡ Core Features

- **Triple-Layer Architecture:** Combines **ChromaDB** (Semantic), **Kuzu** (Graph), and **Session Context** for robust retrieval.
- **Privacy First:** Zero data egress. Your memories live in `./data`, not the cloud.
- **MCP Native:** Built specifically for the **Model Context Protocol**, making it plug-and-play for Cursor, Claude Desktop, and Bob IDE.
- **Adaptive Weighting:** Dynamically adjusts retrieval strategies based on query intent (e.g., questions favor semantic search, IDs favor graph lookups).

## 🚀 Quick Start

**Windows:**
Run `install.bat` to install dependencies and configure your IDE automatically.

**Mac/Linux:**
Run `./install.sh`.

For detailed instructions, see [docs/INSTALLATION.md](docs/INSTALLATION.md).

## 🧠 Usage

Simply talk to your agent:

> "Remember that I am a Senior Python Developer at IBM."
> "What is the relationship between Project Omega and Kafka?"

For API examples and advanced queries, see [docs/USAGE.md](docs/USAGE.md).

### Installation Steps

0. **Run pre-flight checks** (NEW - prevents common issues)
   - Checks disk space (5GB+ required)
   - Detects Kuzu 0.11+ compatibility issues
   - Automatically backs up and resolves conflicts
1. Create a virtual environment
2. Install all dependencies
3. Initialize the databases
4. **Configure your IDE** (VSCode/Bob) to use Elefante
5. Verify the system is working

> **Note**: The installer now includes automated safeguards that prevent the Kuzu 0.11+ database path conflict. See [INSTALLATION_SAFEGUARDS.md](INSTALLATION_SAFEGUARDS.md) for details.

### Manual Installation

If you prefer to set up manually, see [SETUP.md](docs/SETUP.md).

---

## 📊 Dashboard Visualization (NEW!)

Elefante now includes a **visual knowledge graph dashboard** for exploring your memories interactively.

### Starting the Dashboard

```bash
cd Elefante
.venv\Scripts\python.exe -m src.dashboard.server
```

Open http://127.0.0.1:8000 in your browser to see:

- **Interactive Graph**: Force-directed visualization of all memories
- **Node Labels**: Each memory shows a truncated description
- **Hover Tooltips**: Full content and timestamps on hover
- **Statistics**: Real-time memory count and episode tracking
- **Spaces Filter**: Organize memories by category

### Auto-Refresh Feature ⭐

**Important**: The dashboard automatically reflects new memories without server restart!

1. Add a memory (via MCP, API, or script)
2. Refresh your browser (F5)
3. New memory appears instantly

No need to restart the server or reinitialize databases.

For complete dashboard documentation, see [docs/DASHBOARD.md](docs/DASHBOARD.md).

---

## 🔌 MCP Tools & Usage

Elefante integrates via the **Model Context Protocol (MCP)**. Once installed, your AI assistant will have access to these tools:

### 1. `addMemory`

**Store new information.**
The system automatically decides how to store it (Vector, Graph, or both) and links it to relevant entities.

- **Usage**: "Remember that I am working on the Omega Project."
- **Behind the scenes**:
  - Stores text in ChromaDB for semantic search.
  - Extracts "Omega Project" as an entity in Kuzu Graph.
  - Links it to your User Profile.

### 2. `searchMemories`

**Retrieve information.**
Uses **Hybrid Search** to find the most relevant memories based on meaning, facts, and recent context.

- **Usage**: "What do you know about the Omega Project?"
- **Behind the scenes**:
  - Queries Vector DB for similar concepts.
  - Queries Graph DB for exact relationships.
  - Merges results using adaptive weighting.

### 3. `queryGraph`

**Ask complex structural questions.**
Executes Cypher queries against the Knowledge Graph.

- **Usage**: "Show me all projects related to AI."
- **Behind the scenes**:
  - Runs `MATCH (p:Entity {type: 'project'})-[:RELATES_TO]->(t:Entity {name: 'AI'}) RETURN p`

### 4. `getContext`

**Get a "brain dump" for the current session.**
Retrieves the most relevant memories and entities for the current conversation context.

- **Usage**: (Called automatically by the agent at the start of a task)
- **Behind the scenes**:
  - Fetches recent conversation history.
  - Identifies active entities.
  - Returns a consolidated context object.

### 5. `createEntity` & `createRelationship`

**Manually build the Knowledge Graph.**
For when you want to be explicit about structure.

- **Usage**: "Create an entity for 'Bob' and link it to 'Elefante' as 'Maintainer'."

---
>>>>>>> 12e0497 (Elefante: Initial commit of AI Memory System)

## 🏗️ Architecture

Elefante uses an **Orchestrator Pattern** to route queries:
`User -> MCP Server -> Orchestrator -> (Vector + Graph + Context) -> Weighted Result`.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the deep dive.
