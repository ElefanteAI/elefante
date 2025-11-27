# 🐘 Elefante - Local AI Memory System

> **"An elephant never forgets"** - Give your AI assistant perfect memory with local, private, and intelligent storage.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests: 73 Passing](https://img.shields.io/badge/tests-73%20passing-brightgreen.svg)]()
[![Status: Production Ready](https://img.shields.io/badge/status-production%20ready-success.svg)]()

---

## 🎯 What is Elefante?

Elefante is a **production-ready, local, and zero-cost** persistent memory system designed specifically for AI assistants like Bob. It solves the fundamental problem of stateless LLMs by providing:

- 🧠 **Semantic Memory** (ChromaDB) - Fuzzy, meaning-based recall
- 🕸️ **Structured Memory** (Kuzu Graph DB) - Deterministic fact retrieval
- 💬 **Conversation Context** - Session-aware hybrid search with adaptive weighting
-  **Hybrid Intelligence** - Best of both worlds, automatically
- 🔒 **100% Private** - All data stays on your machine
- 💰 **Zero Cost** - Free, open-source components only
- ⚡ **Fast** - Sub-second query responses
- ✅ **Production Ready** - 73 tests passing, zero regressions

---

## 🚀 Quick Start

### Prerequisites

- Python 3.9 or higher
- 2GB RAM minimum (4GB recommended)
- 1GB disk space for system + storage for your memories

### Installation

```bash
# 1. Clone the repository
git clone <repository-url> Elefante
cd Elefante

# 2. Create virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Initialize databases
python scripts/init_databases.py

# 5. Verify installation
python scripts/health_check.py
```

### First Memory

```python
from src.core.orchestrator import MemoryOrchestrator

# Initialize the system
memory = MemoryOrchestrator()

# Store your first memory
await memory.add_memory(
    content="Elefante is my new AI memory system",
    memory_type="fact",
    importance=8,
    tags=["project", "ai", "memory"]
)

# Search for it
results = await memory.search("What is Elefante?")
print(results[0].content)
# Output: "Elefante is my new AI memory system"
```

---

## 🏗️ Architecture

Elefante uses a **triple-layer architecture** for comprehensive memory:

```
┌─────────────────────────────────────────────────┐
│           AI Agent (Bob)                        │
└────────────────┬────────────────────────────────┘
                 │ MCP Protocol
┌────────────────▼────────────────────────────────┐
│         Elefante Memory System                  │
│  ┌──────────────────────────────────────────┐  │
│  │    Hybrid Query Orchestrator             │  │
│  │    • Adaptive Weighting                  │  │
│  │    • Deduplication                       │  │
│  │    • Score Normalization                 │  │
│  └──┬───────────┬───────────────┬───────────┘  │
│     │           │               │               │
│  ┌──▼─────┐ ┌──▼──────┐  ┌─────▼──────────┐   │
│  │Convers-│ │ChromaDB │  │  Kuzu Graph    │   │
│  │ation   │ │(Vector) │  │  (Knowledge    │   │
│  │Context │ │         │  │   Graph)       │   │
│  │        │ │• Semantic│  │  • Facts       │   │
│  │• Recent│ │• Embed-  │  │  • Relations   │   │
│  │• Session│ │  dings  │  │  • Entities    │   │
│  └────────┘ └─────────┘  └────────────────┘   │
└─────────────────────────────────────────────────┘
```

### Why Three Memory Layers?

| Use Case | Best Layer | Example |
|----------|------------|---------|
| "What did we just discuss?" | **Conversation** (Recent) | Session context, pronouns |
| "What did we discuss about Python?" | **Vector** (Semantic) | Fuzzy meaning-based search |
| "Who created the Elefante project?" | **Graph** (Structured) | Exact fact retrieval |
| "Everything about Elefante" | **Hybrid** (All Three) | Comprehensive context |

### 🆕 Enterprise Features (v2.0)

Elefante has been upgraded with **production-grade intelligence**:

1.  **🧠 Intelligent Ingestion**:
    *   Automatically detects if a memory is `NEW`, `REDUNDANT`, or `RELATED`.
    *   Creates `SIMILAR_TO` links in the graph automatically.
    *   **No deletion**: Keeps all history but organizes it intelligently.

2.  **👤 User Profile (Contextual Awareness)**:
    *   Detects "I" statements (e.g., "I live in Canada").
    *   Links them to a persistent **User** node.
    *   **Global Context**: Automatically fetches user facts before every search.

3.  **📅 Episodic Memory**:
    *   Links every memory to a **Session** entity.
    *   Enables temporal queries ("What did we do yesterday?").
    *   New tool: `getEpisodes` for timeline browsing.

4.  **🌍 Cross-Workspace Persistence**:
    *   Data stored in `~/.elefante/data` (User Home).
    *   Memories follow you across projects and IDEs (VS Code, Cursor, etc.).

5.  **🛡️ Agent-Proof Search**:
    *   Enhanced prompt engineering forces the agent to search before asking.
    *   Automatic query rewriting for better results.

---

### 🆕 Conversation Context (Legacy)
Elefante also includes session-aware conversation context that:
- Tracks recent messages within the current session
- Resolves pronouns and vague references automatically
- Uses adaptive weighting based on query characteristics
- Deduplicates results across all three layers
- Provides seamless SHORT-TERM (session) + LONG-TERM (persistent) memory

---

## 📚 Core Features

### 1. Semantic Memory (ChromaDB)

Store and retrieve memories based on **meaning**, not just keywords:

```python
# Store a memory
await memory.add_memory(
    content="Python is great for data science and machine learning",
    tags=["programming", "python"]
)

# Later, search with different words
results = await memory.search("What languages are good for AI?")
# Finds the Python memory because of semantic similarity!
```

### 2. Knowledge Graph (Kuzu)

Build a **web of knowledge** with entities and relationships:

```python
# Create entities
await memory.create_entity(name="Elefante", type="project")
await memory.create_entity(name="Bob", type="ai_agent")

# Create relationships
await memory.create_relationship(
    from_entity="Bob",
    to_entity="Elefante",
    relationship_type="USES"
)

# Query the graph
results = await memory.query_graph(
    "MATCH (a:ai_agent)-[:USES]->(p:project) RETURN a.name, p.name"
)
```

### 3. Hybrid Search

Automatically combines both databases for best results:

```python
# The orchestrator decides which database(s) to use
results = await memory.search(
    query="Tell me everything about the Elefante project",
    mode="hybrid"  # or "semantic", "structured"
)

# Returns merged results from both databases, ranked by relevance
```

### 4. MCP Integration

Seamlessly integrates with your IDE via Model Context Protocol:

```json
{
  "mcpServers": {
    "elefante": {
      "command": "python",
      "args": ["-m", "src.mcp.server"],
      "cwd": "path/to/Elefante"
    }
  }
}
```

Available MCP Tools:
- `addMemory` - Store new memories
- `searchMemories` - Search with filters
- `queryGraph` - Execute graph queries
- `getContext` - Retrieve session context
- `createEntity` - Add graph entities
- `createRelationship` - Link entities

---

## 🎨 Usage Examples

### Example 1: Project Context Tracking

```python
# Store project decisions
await memory.add_memory(
    content="Decided to use ChromaDB for vector storage because it's file-based and doesn't require a server",
    memory_type="decision",
    importance=9,
    tags=["elefante", "architecture", "database"],
    entities=[
        {"name": "ChromaDB", "type": "technology"},
        {"name": "Elefante", "type": "project"}
    ]
)

# Later, recall why you made that choice
results = await memory.search("Why did we choose ChromaDB?")
```

### Example 2: Code Context

```python
# Store code insights
await memory.add_memory(
    content="The orchestrator.py file contains the hybrid query logic that routes between vector and graph databases",
    memory_type="code",
    tags=["elefante", "orchestrator", "architecture"],
    entities=[
        {"name": "orchestrator.py", "type": "file"},
        {"name": "hybrid_query", "type": "function"}
    ]
)

# Find related code
results = await memory.search("Where is the query routing logic?")
```

### Example 3: Learning & Insights

```python
# Store lessons learned
await memory.add_memory(
    content="Learned that Kuzu is faster than Neo4j for embedded use cases because it runs in-process",
    memory_type="insight",
    importance=7,
    tags=["learning", "database", "performance"]
)

# Retrieve insights
results = await memory.search(
    query="performance insights",
    filters={"memory_type": "insight"}
)
```

---

## 🔧 Configuration

### Automatic Path Resolution

Elefante now uses **absolute paths** to prevent database "amnesia":

```python
# Paths are automatically resolved relative to project root
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
DATA_DIR = PROJECT_ROOT / "data"
CHROMA_DIR = DATA_DIR / "chroma"  # Absolute path
KUZU_DIR = DATA_DIR / "kuzu"      # Absolute path
```

**Benefits:**
- ✅ No more "empty database" issues when starting from different directories
- ✅ Databases persist regardless of working directory
- ✅ Directories auto-created on startup

### Configuration File

Edit `config.yaml` to customize Elefante:

```yaml
elefante:
  # Paths are auto-resolved to absolute paths by config.py
  
  vector_store:
    embedding_model: "all-MiniLM-L6-v2"  # Fast, local model
    
  graph_store:
    buffer_pool_size: "512MB"  # Adjust based on RAM
    
  orchestrator:
    default_mode: "hybrid"  # or "semantic", "structured"
    vector_weight: 0.5      # Balance between databases
    graph_weight: 0.5
```

---

## 📊 Performance

Tested on a standard laptop (Intel i5, 8GB RAM):

| Operation | Latency | Notes |
|-----------|---------|-------|
| Add Memory | ~80ms | Including embedding generation |
| Semantic Search | ~150ms | 10,000 memories |
| Graph Query | ~30ms | Simple traversal |
| Hybrid Search | ~250ms | Combined operation |

**Scalability**: Tested up to 100,000 memories with sub-second query times.

---

## 🛠️ Development

### Project Structure

```
Elefante/
├── src/
│   ├── core/           # Core memory system
│   │   ├── orchestrator.py      # Hybrid query orchestration
│   │   ├── vector_store.py      # ChromaDB integration
│   │   ├── graph_store.py       # Kuzu integration
│   │   ├── conversation_context.py  # Session context
│   │   ├── scoring.py           # Adaptive weighting
│   │   └── deduplication.py     # Result deduplication
│   ├── mcp/            # MCP server integration
│   ├── models/         # Data models
│   │   ├── conversation.py      # Message & SearchCandidate
│   │   └── query.py             # SearchResult & filters
│   └── utils/          # Utilities
│       └── config.py            # Absolute path resolution
├── tests/              # Test suite (73 tests)
│   ├── test_conversation_context.py  # 22 tests
│   ├── test_conversation_models.py   # 11 tests
│   ├── test_scoring.py               # 12 tests
│   ├── test_deduplication.py         # 18 tests
│   └── test_memory_persistence.py    # 10 tests
├── scripts/            # Setup & maintenance
├── data/               # Database storage (auto-created)
├── docs/               # Documentation
│   ├── HYBRID_SEARCH_ARCHITECTURE.md
│   ├── IMPLEMENTATION_PLAN.md
│   └── HYBRID_SEARCH_IMPLEMENTATION_SUMMARY.md
├── SETUP_GUIDE.md      # Fresh installation guide
└── TESTING_INSTRUCTIONS.md  # User testing guide
```

### Running Tests

```bash
# Run all tests (73 tests)
pytest tests/ -v

# Run specific test suite
pytest tests/test_memory_persistence.py -v

# Run with coverage
pytest --cov=src tests/

# Expected output: 73 passed, 0 failed
```

### Test Coverage

- **Conversation Context**: 22 tests (keyword extraction, scoring, filtering)
- **Models**: 11 tests (Message, SearchCandidate validation)
- **Scoring**: 12 tests (adaptive weights, normalization)
- **Deduplication**: 18 tests (cosine similarity, merging)
- **Persistence**: 10 tests (write-path, absolute paths, survival)

### Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## 🔒 Privacy & Security

- ✅ **100% Local** - All data stored on your machine
- ✅ **No Telemetry** - Zero external API calls (except optional OpenAI embeddings)
- ✅ **No Cloud** - No data transmission to servers
- ✅ **Open Source** - Fully auditable code
- ✅ **Encrypted** - Optional OS-level encryption support

---

## 🐛 Troubleshooting

### "ChromaDB not found"
```bash
pip install chromadb
```

### "Kuzu import error"
```bash
pip install kuzu
```

### "Embedding model download failed"
```bash
# Pre-download the model
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

### "Database initialization failed"
```bash
# Reset databases
rm -rf data/
python scripts/init_databases.py
```

For more issues, see [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

---

## 📖 Documentation

### Core Documentation
- [SETUP_GUIDE.md](SETUP_GUIDE.md) - Step-by-step installation for new environments
- [TESTING_INSTRUCTIONS.md](TESTING_INSTRUCTIONS.md) - User testing guide

### Architecture Documentation
- [HYBRID_SEARCH_ARCHITECTURE.md](docs/HYBRID_SEARCH_ARCHITECTURE.md) - System design
- [IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) - Development roadmap
- [HYBRID_SEARCH_IMPLEMENTATION_SUMMARY.md](docs/HYBRID_SEARCH_IMPLEMENTATION_SUMMARY.md) - Complete implementation details

### Additional Resources
- [API Reference](docs/API.md) - Complete API documentation
- [Examples](docs/EXAMPLES.md) - More usage examples
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Common issues

---

## 🗺️ Roadmap

### ✅ Phase 1 - Core System (COMPLETE)
- [x] Architecture design
- [x] Dual-database implementation (ChromaDB + Kuzu)
- [x] MCP integration
- [x] Comprehensive testing (73 tests)
- [x] Production-ready deployment

### ✅ Phase 2 - Hybrid Search (COMPLETE)
- [x] Conversation context integration
- [x] Adaptive weighting system
- [x] Result deduplication
- [x] Score normalization
- [x] Absolute path resolution
- [x] Persistence verification tests

### 🚧 Phase 3 - Advanced Features (NEXT)
- [ ] Memory consolidation algorithms
- [ ] Export/import functionality
- [ ] Advanced graph traversal
- [ ] Performance optimization
- [ ] Multi-session management

### 🔮 Phase 4 - Future Enhancements
- [ ] Web UI for visualization
- [ ] Multi-user support
- [ ] Plugin system
- [ ] Advanced analytics dashboard
- [ ] Cloud sync (optional)

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details

---

## 🙏 Acknowledgments

- **ChromaDB** - Excellent vector database
- **Kuzu** - Fast embedded graph database
- **Sentence Transformers** - High-quality embeddings
- **MCP Protocol** - Standardized AI tool interface

---

## 📞 Support

- 📧 Email: [your-email]
- 💬 Discord: [your-discord]
- 🐛 Issues: [GitHub Issues](issues-url)
- 📖 Docs: [Documentation](docs-url)

---

**Made with ❤️ for the AI community**

*"An elephant never forgets, and now, neither does your AI."*
