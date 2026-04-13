# Elefante Development Skills Guide

> **Purpose:** Essential knowledge for AI agents developing, debugging, and maintaining Elefante  
> **Audience:** AI Agents (Claude, GPT, Gemini) working on Elefante codebase  
> **Status:** Production Reference  
> **Last Updated:** 2026-03-24

---

## 🎯 Quick Start: The 3 Golden Rules

1. **SEARCH BEFORE CODE**: Always call `elefante-MemorySearch` before implementing anything
2. **VERIFY BEFORE CLAIM**: Never say "done" without testing and seeing actual output
3. **CHECK PITFALLS FIRST**: Read [`docs/pitfall-index.md`](docs/pitfall-index.md) before ANY task

---

## 📋 Table of Contents

- [Critical Laws (The Pain Index)](#critical-laws-the-pain-index)
- [Architecture Essentials](#architecture-essentials)
- [Development Workflow](#development-workflow)
- [Debugging Protocol](#debugging-protocol)
- [Common Pitfalls by Category](#common-pitfalls-by-category)
- [MCP Tool Usage Patterns](#mcp-tool-usage-patterns)
- [Testing & Verification](#testing--verification)
- [Quick Reference](#quick-reference)

---

## 🔥 Critical Laws (The Pain Index)

### AI Behavior Laws

| # | Law | Violation Cost | Source |
|---|-----|----------------|--------|
| 1 | VERIFY before claiming completion - never assume code works | Repeated iterations | ai-behavior-compendium.md |
| 2 | STATE → DO → VERIFY in same response - close the action gap | Analysis paralysis | ai-behavior-compendium.md |
| 3 | Search Elefante BEFORE implementing, not after | Repeated mistakes | ai-behavior-compendium.md |
| 4 | Code mode has NO MCP access - switch modes first | Failed operations | ai-behavior-compendium.md |
| 5 | "Should be done" ≠ "Is done" - only real tests matter | False confidence | ai-behavior-compendium.md |
| 6 | User environment ≠ Test environment - account for differences | "It works for me" | ai-behavior-compendium.md |
| 7 | **PASSIVE protocols CANNOT force agent compliance** | System prompt ignored | ai-behavior-compendium.md |

### Dashboard Laws

| # | Law | Violation Cost | Source |
|---|-----|----------------|--------|
| 1 | Dashboard reads from SNAPSHOT file, never query database directly | 3 hours | dashboard-compendium.md |
| 2 | ChromaDB = memories (70+), Kuzu = entities (17) - DIFFERENT DATA | 2 hours | dashboard-compendium.md |
| 3 | Always run `update_dashboard_data.py` after memory changes | Stale data | dashboard-compendium.md |
| 4 | Verify BOTH producer AND consumer when debugging data flow | Circular debugging | dashboard-compendium.md |
| 5 | Hard refresh browser after frontend changes (`Ctrl+Shift+R`) | "It's still broken!" | dashboard-compendium.md |
| 6 | Frontend reads `n.properties`, NOT `n.full_data.props` | 8 hours | dashboard-compendium.md |
| 7 | Long-running servers cache imports - restart after code changes | Silent failures | dashboard-compendium.md |

### Database Laws

| # | Law | Violation Cost | Source |
|---|-----|----------------|--------|
| 1 | NEVER use `properties` as column name - Cypher reserved word | Schema rewrite | database-compendium.md |
| 2 | Single-Writer Lock - only ONE process can access Kuzu at a time | Error 15105 | database-compendium.md |
| 3 | Kuzu 0.11+ creates its own directory - do NOT pre-create | Init failure | database-compendium.md |
| 4 | ChromaDB = memories, Kuzu = entities - DIFFERENT PURPOSES | Data confusion | database-compendium.md |
| 5 | Kill all Python processes before deleting `.lock` file | Stale locks | database-compendium.md |
| 6 | Use `read_only=True` for concurrent read access | Lock conflicts | database-compendium.md |

### Memory Laws

| # | Law | Violation Cost | Source |
|---|-----|----------------|--------|
| 1 | Use `min_similarity=0` to get ALL memories | Partial exports | memory-compendium.md |
| 2 | ChromaDB stores memories, Kuzu stores entities - DIFFERENT | Data confusion | memory-compendium.md |
| 3 | Use `collection.get()` for complete export, not `elefante-MemorySearch` | Missing data | memory-compendium.md |
| 4 | Search Elefante BEFORE implementing, not after | Repeated mistakes | memory-compendium.md |
| 5 | Verify code works BEFORE claiming completion | User frustration | memory-compendium.md |
| 6 | Memory metadata has 40+ fields - don't assume structure | Silent data loss | memory-compendium.md |
| 7 | V3 Schema: layer/sublayer must be saved in BOTH add_memory AND reconstruct | 8 hours | memory-compendium.md |
| 8 | **elefante-MemorySearch returns BLOATED JSON - 90% null fields waste tokens** | Context window | memory-compendium.md |
| 9 | **Similarity scores 0.3-0.4 for exact matches = embedding quality issue** | Poor retrieval | memory-compendium.md |

### Installation Laws

| # | Law | Violation Cost | Source |
|---|-----|----------------|--------|
| 1 | Do NOT pre-create Kuzu database directory | 12 minutes debugging | installation-compendium.md |
| 2 | Check library changelogs before upgrading | Breaking changes | installation-compendium.md |
| 3 | Test configuration files, not just code | Root cause missed | installation-compendium.md |
| 4 | Run `pip install -r requirements.txt` after git pull | Missing deps | installation-compendium.md |
| 5 | Verify Python version matches requirements | Cryptic errors | installation-compendium.md |

---

## 🏗️ Architecture Essentials

### The Triple-Layer Brain

```
┌─────────────────────────────────────────────────────────┐
│                    MCP Interface Layer                   │
│              (elefante-MemoryAdd, Search, etc.)         │
└────────────────────┬────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
    ┌────▼─────┐          ┌─────▼────┐
    │ ChromaDB │          │   Kuzu   │
    │ (Vector) │          │  (Graph) │
    └──────────┘          └──────────┘
    Semantic Memory       Structured Memory
    - Fuzzy queries       - Deterministic facts
    - 768-dim embeddings  - Relationships
    - thenlper/gte-base   - Cypher queries
```

### Key Components

1. **Memory Orchestrator** (`src/core/orchestrator.py`)
   - Central decision engine
   - Handles dual-write to ChromaDB + Kuzu
   - Manages transaction-scoped locking (v1.1.0+)

2. **Vector Store** (`src/core/vector_store.py`)
   - ChromaDB wrapper
   - Stores memory content + embeddings
   - Handles semantic search

3. **Graph Store** (`src/core/graph_store.py`)
   - Kuzu wrapper
   - Stores entities + relationships
   - Handles structured queries

4. **MCP Server** (`src/mcp/server.py`)
   - Exposes 20+ tools to AI agents
   - Handles JSON-RPC over stdio
   - **CRITICAL**: All logs must go to stderr, never stdout

### Data Flow: Adding a Memory

```
User/Agent
    │
    ├─> elefante-MemoryAdd (MCP Tool)
    │
    ├─> MemoryOrchestrator.add_memory()
    │
    ├──┬─> VectorStore.add() → ChromaDB
    │  │
    │  └─> GraphStore.create_memory_node() → Kuzu
    │
    └─> Return memory_id + confirmation
```

### Data Flow: Dashboard Display

```
MCP Server (Live Write)
    ↓
~/.elefante/data/kuzu_db/ (Kuzu Graph DB)
    ↓
scripts/update_dashboard_data.py (Export)
    ↓
data/dashboard_snapshot.json (Static File)
    ↓
Dashboard (Read Only)
```

**CRITICAL**: Dashboard NEVER queries databases directly. Always reads from snapshot.

---

## 🔄 Development Workflow

### Before Starting ANY Task

```bash
# 1. Check for relevant pitfalls
grep -i "pitfall: [your_task_category]" docs/pitfall-index.md

# 2. Search Elefante memory for related context
# Use elefante-MemorySearch MCP tool with your task keywords

# 3. Read relevant compendium
# docs/debug/[category]-compendium.md
```

### Standard Development Loop

```
1. SEARCH → Check Elefante memory + pitfall-index.md
2. PLAN → Identify files to modify, potential issues
3. READ → Use read_file with line ranges (efficient)
4. MODIFY → Use apply_diff for surgical edits
5. VERIFY → Run tests, check output
6. DOCUMENT → Update memory if new pattern discovered
```

### Mode Selection

- **Plan Mode**: Architecture, design, strategy
- **Code Mode**: Implementation (NO MCP access)
- **Advanced Mode**: Implementation WITH MCP + Browser tools
- **Ask Mode**: Questions, explanations, analysis

**CRITICAL**: If you need MCP tools, you MUST be in Advanced mode, not Code mode.

---

## 🐛 Debugging Protocol

### The 5-Layer Verification Protocol

When debugging, verify ALL layers:

```
Layer 1: SYNTAX
├─ Does the code compile/parse?
├─ Are imports correct?
└─ Are types valid?

Layer 2: LOGIC
├─ Does the function do what it claims?
├─ Are edge cases handled?
└─ Are return values correct?

Layer 3: INTEGRATION
├─ Do components communicate correctly?
├─ Are data formats compatible?
└─ Are dependencies available?

Layer 4: ENVIRONMENT
├─ Does it work in user's environment?
├─ Are paths correct (Windows vs Unix)?
└─ Are permissions set?

Layer 5: VERIFICATION
├─ Did you TEST it?
├─ Did you SEE the output?
└─ Did the USER confirm it works?
```

### Debugging Checklist

```markdown
- [ ] Read error message LITERALLY (don't assume)
- [ ] Check configuration BEFORE implementation
- [ ] Verify BOTH producer AND consumer
- [ ] Test in user's actual environment
- [ ] Check for stale locks/caches
- [ ] Restart servers after code changes
- [ ] Hard refresh browser after frontend changes
```

### Common Debug Commands

```bash
# Check Elefante system status
python scripts/verify_health.py

# Validate dashboard snapshot
python scripts/verify_dashboard_snapshot.py

# Check MCP server handshake
python scripts/verify_mcp_handshake.py

# Update dashboard data
python scripts/update_dashboard_data.py

# Check for stale locks
ls ~/.elefante/locks/

# Kill stale Python processes
# Windows: tasklist | findstr python
# Linux/Mac: ps aux | grep python
```

---

## 📚 Common Pitfalls by Category

### Dashboard Pitfalls

**Symptom**: Blank page or "No memories yet"
**Fix**:
1. Run `python scripts/update_dashboard_data.py`
2. Hard refresh browser (`Ctrl+Shift+R`)
3. Check snapshot exists: `~/.elefante/data/dashboard_snapshot.json`

**Symptom**: HTTP 500 error
**Fix**:
1. Check server logs for actual error
2. Verify snapshot file is valid JSON
3. Restart server after code changes

**Symptom**: Frontend not found
**Fix**:
```bash
cd src/dashboard/ui
npm install
npm run build
```

### Database Pitfalls

**Symptom**: "Cannot acquire lock"
**Fix**:
```bash
# Kill all Python processes
# Windows: taskkill /F /IM python.exe
# Linux/Mac: pkill python

# Remove stale lock
rm ~/.elefante/locks/write.lock
```

**Symptom**: "Database path cannot be a directory"
**Fix**:
- Do NOT pre-create `kuzu_db/` directory
- Let Kuzu 0.11+ create it automatically
- If exists, delete and reinitialize

**Symptom**: "Binder exception: Cannot find property properties"
**Fix**:
- NEVER use `properties` as column name (Cypher reserved word)
- Use `props` instead

### MCP Pitfalls

**Symptom**: Tools not showing in IDE
**Fix**:
- Return `list[types.Tool]` not `List[Tool]`
- Reload IDE window after config changes
- Check `mcp_settings.json` path is correct

**Symptom**: "Connection refused" or blank responses
**Fix**:
- All logs MUST go to stderr, never stdout
- Check uvicorn log_config routes to stderr
- Verify no print() statements in MCP server

**Symptom**: Write operations blocked
**Fix**:
- Call `elefante-MemorySearch` first (Compliance Gate)
- Then retry write operation

### Memory Pitfalls

**Symptom**: Export returns only 10 memories
**Fix**:
```python
# WRONG
collection.query(query_texts=[""], n_results=1000)

# RIGHT
collection._collection.get(
    include=["documents", "metadatas", "embeddings"],
    limit=1000
)
```

**Symptom**: Search returns no results
**Fix**:
- Use `min_similarity=0.0` to disable filtering
- Check if memories actually exist in ChromaDB
- Verify embedding model is loaded

---

## 🛠️ MCP Tool Usage Patterns

### Memory Operations

```python
# Add memory (with compliance gate bypass)
elefante-MemoryAdd {
  "content": "Your memory content",
  "memory_type": "fact",  # fact, decision, preference, insight, note
  "domain": "work",       # work, personal, learning, project
  "category": "elefante"
}

# Search memory (ALWAYS do this first)
elefante-MemorySearch {
  "query": "your search query",
  "mode": "hybrid",  # semantic, structured, hybrid
  "limit": 10
}

# List ALL memories (for export/inspection)
elefante-MemorySearch {
  "query": "",
  "list_all": true,
  "limit": 1000
}

# Update memory (requires prior search)
elefante-MemoryUpdate {
  "memory_id": "uuid-from-search",
  "content": "new content",
  "deprecated": false
}

# Delete memory (requires prior search + reason)
elefante-MemoryDelete {
  "memory_id": "uuid-from-search",
  "reason": "Why this memory is being deleted"
}
```

### Graph Operations

```python
# Connect entities (idempotent)
elefante-GraphConnect {
  "entities": [
    {"ref": "project", "name": "Elefante", "type": "Project"},
    {"ref": "person", "name": "Developer", "type": "Person"}
  ],
  "relationships": [
    {
      "from_ref": "person",
      "to_ref": "project",
      "relationship_type": "WORKS_ON"
    }
  ]
}

# Query graph (Cypher)
elefante-GraphQuery {
  "cypher_query": "MATCH (n:Entity) RETURN n LIMIT 10"
}
```

### System Operations

```python
# Get system status
elefante-SystemStatusGet {}

# Open dashboard
elefante-DashboardOpen {
  "refresh": false  # Set true to update snapshot first
}

# Process ETL (agent classification)
elefante-ETLProcess {
  "limit": 5
}

# Classify memory (after ETL)
elefante-ETLClassify {
  "memory_id": "uuid-from-etl",
  "summary": "One-line description",
  "concepts": ["key", "terms"],
  "surfaces_when": ["query patterns"]
}
```

### Directives (Behavioral Constraints)

```python
# Add directive (unconditional rule)
elefante-DirectiveAdd {
  "content": "Never claim success without user confirmation"
}

# List directives
elefante-DirectiveList {}

# Remove directive
elefante-DirectiveRemove {
  "directive_id": "uuid-from-list"
}
```

---

## ✅ Testing & Verification

### Pre-Commit Checklist

```markdown
- [ ] All tests pass: `pytest tests/`
- [ ] Health check passes: `python scripts/verify_health.py`
- [ ] Dashboard builds: `cd src/dashboard/ui && npm run build`
- [ ] MCP handshake works: `python scripts/verify_mcp_handshake.py`
- [ ] No stale locks: `ls ~/.elefante/locks/`
- [ ] Documentation updated if behavior changed
- [ ] Pitfall-index.md updated if new issue discovered
```

### Verification Commands

```bash
# Test MCP server
python -c "from src.mcp.server import app; print('✓ MCP server imports')"

# Test orchestrator
python -c "from src.core.orchestrator import MemoryOrchestrator; print('✓ Orchestrator imports')"

# Test databases
python scripts/verify_health.py

# Test dashboard snapshot
python scripts/verify_dashboard_snapshot.py

# Test MCP handshake
python scripts/verify_mcp_handshake.py
```

---

## 🚀 Quick Reference

### File Structure

```
elefante/
├── src/
│   ├── core/           # Orchestrator, vector store, graph store
│   ├── mcp/            # MCP server (20+ tools)
│   ├── dashboard/      # FastAPI backend + React frontend
│   ├── models/         # Data models (Memory, Entity, etc.)
│   └── utils/          # Config, logger, helpers
├── scripts/            # Maintenance scripts
├── docs/
│   ├── technical/      # Architecture, usage guides
│   ├── debug/          # *-compendium.md (post-mortems)
│   └── pitfall-index.md  # Quick reference
├── tests/              # Unit + integration tests
└── data/               # Local data directory
    ├── chroma_db/      # ChromaDB storage
    ├── kuzu_db/        # Kuzu storage
    └── dashboard_snapshot.json  # Dashboard data
```

### Key Files to Know

| File | Purpose | When to Edit |
|------|---------|--------------|
| `src/core/orchestrator.py` | Memory operations | Adding features |
| `src/mcp/server.py` | MCP tool definitions | Adding tools |
| `src/dashboard/server.py` | Dashboard API | Dashboard features |
| `docs/pitfall-index.md` | Quick pitfall reference | New issue found |
| `docs/debug/*-compendium.md` | Detailed post-mortems | Major debugging session |

### Environment Variables

```bash
# Required
ELEFANTE_CONFIG_PATH=/path/to/config.yaml
PYTHONPATH=/path/to/elefante

# Optional
ANONYMIZED_TELEMETRY=False
ELEFANTE_SNAPSHOT_SEMANTIC_EDGES=1  # Enable semantic edges in dashboard
```

### Common Paths

```bash
# Data directory (cross-platform)
~/.elefante/data/

# Lock files
~/.elefante/locks/write.lock

# Dashboard snapshot
~/.elefante/data/dashboard_snapshot.json

# MCP settings (IBM Bob)
C:\Users\<user>\.bob\settings\mcp_settings.json  # Windows
~/.bob/settings/mcp_settings.json                # Linux/Mac
```

---

## 📖 Further Reading

- **Architecture**: [`docs/technical/architecture.md`](docs/technical/architecture.md)
- **Pitfall Index**: [`docs/pitfall-index.md`](docs/pitfall-index.md)
- **AI Behavior**: [`docs/debug/ai-behavior-compendium.md`](docs/debug/ai-behavior-compendium.md)
- **Dashboard**: [`docs/debug/dashboard-compendium.md`](docs/debug/dashboard-compendium.md)
- **Database**: [`docs/debug/database-compendium.md`](docs/debug/database-compendium.md)
- **Memory**: [`docs/debug/memory-compendium.md`](docs/debug/memory-compendium.md)
- **Installation**: [`docs/debug/installation-compendium.md`](docs/debug/installation-compendium.md)

---

## 🎯 The 10 Commandments for Elefante Development

1. **Search Before Code**: Always check Elefante memory + pitfall-index.md first
2. **Verify Before Claim**: Never say "done" without testing
3. **Read Errors Literally**: Don't assume, read what it actually says
4. **Check Config First**: Most issues are configuration, not code
5. **Respect the Lock**: Only ONE process can write to Kuzu at a time
6. **Snapshot is King**: Dashboard reads snapshot, not live database
7. **Restart After Changes**: Servers cache imports, restart to see changes
8. **Hard Refresh Browser**: Browser caches frontend, use Ctrl+Shift+R
9. **Document New Patterns**: Update pitfall-index.md when you find new issues
10. **Test in User Environment**: "Works for me" ≠ "Works for user"

---

**Last Updated**: 2026-03-24  
**Version**: 2.1.5  
**Maintainer**: Add new patterns as discovered