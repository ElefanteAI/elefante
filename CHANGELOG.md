# Changelog

All notable changes to Elefante will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.6.0] - 2025-12-28

### Summary

Compliance Gate - Enforced search-before-write to ensure agents retrieve context before storing memories.

### The Problem Solved

Agents using Elefante MCP tools often skip memory retrieval entirely:
- Memories are stored without checking for duplicates
- Context is ignored because search is never called
- No mechanical enforcement existed - only "instructions" which agents drift from

### The Solution

**Server-Side Compliance Gate** in `src/mcp/server.py`:
- Session state tracks whether `elefanteMemorySearch` has been called
- Write operations (`elefanteMemoryAdd`, `elefanteGraphEntityCreate`, `elefanteGraphRelationshipCreate`, `elefanteGraphConnect`) are **BLOCKED** if no prior search
- Search handler sets `search_performed=True` and returns a compliance stamp
- Gate resets on session end

**Layered Defense** via `.github/copilot-instructions.md`:
- Injected into every GitHub Copilot request in this repository
- Documents the mandatory search-first protocol
- Defines the compliance stamp format

### Compliance Stamp Format

```
[ELEFANTE] Searched: Found {N} relevant memories
[ELEFANTE] Searched: No relevant memories found
```

### Changes

- **NEW**: `_compliance_state` dict in ElefanteMCPServer (`search_performed`, `search_count`, `search_timestamp`, `last_query`)
- **NEW**: `_check_compliance_gate()` method - returns error if search not performed
- **NEW**: `_reset_compliance_gate()` method - resets session state
- **MODIFIED**: `_handle_search_memories` - sets compliance flag and adds stamp to response
- **MODIFIED**: `_handle_add_memory` - gate check before write
- **MODIFIED**: `_handle_create_entity` - gate check before write
- **MODIFIED**: `_handle_create_relationship` - gate check before write  
- **MODIFIED**: `_handle_set_elefante_connection` - gate check before write
- **NEW**: `.github/copilot-instructions.md` - Copilot-injected protocol instructions

### Gated Tools

| Tool | Gate Enforced |
|------|---------------|
| `elefanteMemoryAdd` | ✅ Yes |
| `elefanteGraphEntityCreate` | ✅ Yes |
| `elefanteGraphRelationshipCreate` | ✅ Yes |
| `elefanteGraphConnect` | ✅ Yes |
| `elefanteMemorySearch` | ❌ No (this unlocks the gate) |
| `elefanteContextGet` | ❌ No (read-only) |
| `elefanteGraphQuery` | ❌ No (read-only) |

### Error Response (Gate Blocked)

```json
{
  "success": false,
  "error": "⛔ COMPLIANCE GATE: Search required before write operations.",
  "gate_status": "BLOCKED",
  "action_required": "Call elefanteMemorySearch first to check for existing/related memories.",
  "reason": "This prevents duplicate memories and ensures you have full context before adding new knowledge."
}
```

---

## [1.5.0] - 2025-12-27

### Summary

V5 Cognitive Features - Retrieval Explanation, Memory Health, Conflict Detection, Proactive Surfacing.

### The Problem Solved

V4 returns cognitive scores but doesn't explain WHY. Users can't audit the system:
- Why did this memory rank higher than another?
- Which memories are stale or orphaned?
- Are any memories contradicting each other?
- What should surface proactively based on context?

### The Solution

4 new features via 2 consolidated components:

**CognitiveRetriever Extensions** (`src/core/retrieval.py`):
- `RetrievalExplanation` - Full breakdown of 6 signals with reasons
- `ProactiveSurfacer` - Suggests memories based on temporal/domain/concept triggers

**MemoryHealthAnalyzer** (`src/utils/curation.py`):
- `compute_health()` - 4 states: 🟢 healthy, 🟡 stale, 🔴 at_risk, ⚪ orphan
- `detect_potential_conflict()` - Flags same-domain memories with 60%+ concept overlap

### Property-Based Testing

8 properties verified with Hypothesis (700+ test iterations):
- P1: Explanation completeness (6 signals always present)
- P2: Explanation accuracy (matched concepts correct)
- P3: Health exhaustiveness (exactly 4 states)
- P4: Health determinism (same inputs → same output)
- P5: Conflict symmetry (conflict(a,b) ⇔ conflict(b,a))
- P6: Threshold monotonicity (higher threshold → fewer conflicts)
- P7: Trigger types (exactly 3: temporal, domain, recurring_concept)
- P8: Confidence bounds (always 0.0-1.0)

### Changes

- **NEW**: `RetrievalExplanation` dataclass in retrieval.py
- **NEW**: `ProactiveSuggestion` + `ProactiveSurfacer` in retrieval.py
- **NEW**: `HealthStatus`, `HealthReport`, `ConflictReport`, `MemoryHealthAnalyzer` in curation.py
- **MODIFIED**: `score_candidate()` now returns `(candidate, explanation)` tuple
- **MODIFIED**: Orchestrator attaches explanations to SearchResult
- **NEW**: tests/test_v5_explanation.py (7 tests)
- **NEW**: tests/test_v5_health.py (14 tests)
- **NEW**: tests/test_v5_proactive.py (14 tests)

---

## [1.4.0] - 2025-12-27

### Summary

V4 Cognitive Retrieval Engine - 6-signal composite scoring replaces raw vector similarity.

### The Problem Solved

Raw vector similarity alone is naive. A memory can be semantically similar but:
- Temporally stale (hasn't been accessed in months)
- Low authority (user never reinforced it)
- Disconnected (no graph relationships)

### The Solution

`CognitiveRetriever` in `src/core/retrieval.py` applies 6 weighted signals:

| Signal | Weight | Source |
|--------|--------|--------|
| Vector Similarity | 0.35 | ChromaDB cosine distance |
| Concept Match | 0.15 | Keyword/concept overlap |
| Domain Alignment | 0.10 | Domain field match |
| Coactivation | 0.15 | Graph relationship density |
| Authority | 0.15 | Reinforcement history |
| Temporal Recency | 0.10 | Decay-adjusted freshness |

### Verified Results

- Composite scores differ from vector scores by -0.32 to -0.45
- High-authority, recently-accessed memories rank higher
- Graph-connected memories get coactivation boost

### Changes

- **NEW**: `src/core/retrieval.py` - CognitiveRetriever class
- **MODIFIED**: `src/core/orchestrator.py` - Wired `_apply_cognitive_scoring()`
- **CLEANUP**: Archived 40+ one-off scripts to `scripts/archive/historical/`
- **CLEANUP**: Removed 26 old data exports from `data/`

---

## [1.3.0] - 2025-12-27

### Summary

Embedding model upgrade to `thenlper/gte-base` (768-dim) for improved semantic search quality.

### The Problem Solved

The previous embedding model (`all-MiniLM-L6-v2`, 384-dim) had lower semantic precision:
- Fuzzy queries often missed relevant memories
- Similar concepts had weak similarity scores
- Edge cases (version numbers, acronyms) performed poorly

### The Solution

Rigorous benchmarking of 10 embedding models (1485 queries) identified `thenlper/gte-base` as the optimal choice:

| Model | Dimensions | MRR | Hit@5 | Latency |
|-------|------------|-----|-------|---------|
| **thenlper/gte-base** | 768 | **0.337** | 49.8% | ~15ms |
| all-MiniLM-L6-v2 | 384 | 0.310 | 45.2% | ~8ms |
| BAAI/bge-base-en-v1.5 | 768 | 0.328 | 48.1% | ~14ms |

Live testing (35 queries, 24 memories) confirmed:
- **Global Avg Similarity: 0.803** (excellent)
- **Hit Rate: 100%** (all queries returned relevant results)
- **Fuzzy query handling**: "remember that thing about the database lock" → 0.845 similarity

### Changes

#### Configuration Updates
- **`config.yaml`**: `embedding_model: "thenlper/gte-base"`, `embedding_dimension: 768`
- **`src/utils/config.py`**: Updated `VectorStoreConfig` and `EmbeddingsConfig` defaults
- **`.env.example`**: Updated example value
- **`docs/technical/architecture.md`**: Model reference updated

#### Migration Script
- **`scripts/migrate_embeddings_gte_base.py`**: Re-embeds all memories with new model
  - Creates timestamped backup before migration
  - Batch processing with progress indication
  - Verification of count match

#### Documentation Fixes (Ghost Links)
During workspace audit, discovered v2 schema files were archived Dec 11 but documentation still linked to them:
- **`docs/README.md`**: v2 schema → v3/v4/v5 references
- **`docs/technical/README.md`**: Removed dead v2 links
- **`docs/debug/memory-neural-register.md`**: v2 → v3
- **`docs/technical/temporal-memory-decay.md`**: v2 → v3

#### Safeguards Added
- **`docs/pitfall-index.md`**: Added Documentation category with "archive without index update" pitfall
- **`docs/technical/developer-etiquette.md`**: Added LAW 6.5 (mandatory grep-before-archive rule)

#### Test Tooling
- **`scripts/test_embedding_battery.py`**: 35-query test battery across 8 categories
  - Identity, Preferences, Project, Technical, Decisions, Workflow, Fuzzy, Edge

### Migration

**BREAKING**: Existing ChromaDB databases have 384-dim embeddings incompatible with new 768-dim model.

To migrate:
```bash
PYTHONPATH=. .venv/bin/python scripts/migrate_embeddings_gte_base.py
```

The script:
1. Creates backup: `memories_backup_YYYYMMDD_HHMMSS`
2. Re-embeds all memories with `gte-base`
3. Verifies count match

To delete backup after verification:
```bash
python -c "import chromadb; c=chromadb.PersistentClient('~/.elefante/data/chroma'); c.delete_collection('memories_backup_...')"
```

---

## [Unreleased]

### Planned
- Auto-classification of domain/category via agent
- Smart UPDATE (merge instead of duplicate)
- Automatic relationship inference
- Knowledge clustering
- Dashboard semantic zoom
- Improved label rendering

---

## [1.1.0] - 2025-12-26

### Summary

Transaction-scoped locking for true multi-IDE safety. Fixes the fundamental lock deadlock problem where stale locks from crashed/closed IDEs would block other instances indefinitely.

### The Problem Solved

v1.0.1 used **session-based locking**:
- `elefanteSystemEnable` acquired locks → held indefinitely
- `elefanteSystemDisable` released locks only on explicit call
- Crashed processes left stale locks forever (e.g., PID 4563 from Dec 14 blocking all access on Dec 26)
- Multiple IDEs could never interleave operations

### The Solution

v1.1.0 uses **transaction-scoped locking**:
- Each write operation acquires lock → does work → releases lock (milliseconds)
- Read operations are lock-free
- Stale locks auto-expire after 30 seconds
- Multiple IDEs can interleave operations safely

### Changes

#### Transaction-Scoped Locking (`src/utils/elefante_mode.py`)
- **NEW**: `TransactionLock` class - short-lived, auto-releasing locks
- **NEW**: `write_lock()` context manager for write operations
- **NEW**: `read_lock()` context manager (no-op - reads are lock-free)
- **NEW**: Stale lock detection (dead PID or timeout > 30s)
- **CHANGED**: `is_enabled` always returns `True` (no more enable/disable ceremony)
- **CHANGED**: `enable()`/`disable()` are now no-ops for backward compatibility
- **REMOVED**: Session-based lock files (`chroma.lock`, `kuzu.lock`)
- **ADDED**: Single `write.lock` file with PID/timestamp tracking

#### MCP Server Updates (`src/mcp/server.py`)
- **CHANGED**: Write operations wrapped in `write_lock()`:
  - `_handle_add_memory`
  - `_handle_create_entity`
  - `_handle_create_relationship`
  - `_handle_consolidate_memories`
  - `_handle_set_elefante_connection`
  - `_handle_etl_classify`
  - `_handle_migrate_memories_v3`
- **REMOVED**: Blocking mode check that returned "disabled" response
- **ADDED**: Graceful retry response when lock unavailable

### Migration

No migration needed. v1.1.0 is backward compatible:
- `elefanteSystemEnable` still works (now a no-op that returns success)
- `elefanteSystemDisable` still works (clears resources)
- All existing tool calls work unchanged

### Versioning Logic

Elefante follows [Semantic Versioning](https://semver.org/):
- **MAJOR** (x.0.0): Breaking changes requiring user action
- **MINOR** (1.x.0): New features, backward compatible
- **PATCH** (1.0.x): Bug fixes, documentation

This release is **1.1.0** (minor) because:
- New feature (transaction-scoped locking)
- Backward compatible (existing tools work unchanged)
- No user migration required

---

## [1.0.1] - 2025-12-11

### Summary

Critical update addressing protocol enforcement and multi-IDE safety.

### Changes

#### Auto-Inject Pitfalls (Protocol Enforcement)
- MCP Server now injects mandatory protocols (`MANDATORY_PROTOCOLS_READ_THIS_FIRST`) directly into every tool response
- Context-Aware Warnings for `addMemory` (integrity), `searchMemories` (bias), and graph tools (consistency)
- Updated `ai-behavior-compendium.md` with Issue #6 (Passive Protocol Enforcement Failure)

#### ELEFANTE_MODE (Multi-IDE Safety)
- **Problem**: Multiple IDEs accessing same databases caused crashes/lock conflicts
- **Solution**: Server starts OFF by default, user must explicitly enable

##### New MCP Tools
- `elefanteSystemEnable` - Acquires exclusive locks, enables memory operations
- `elefanteSystemDisable` - Releases locks, cleans up, returns to OFF state
- `elefanteSystemStatusGet` - Shows current mode, lock status, holder info (and stats when enabled)

##### New Files
- `src/utils/elefante_mode.py` - Lock management singleton
- `config.yaml` -> `elefante_mode:` section added

##### Behavior
- When **OFF**: Memory tools return graceful "disabled" response with instructions
- When **ON**: Full functionality with exclusive database access
- Lock files stored in `~/.elefante/locks/` with PID/timestamp tracking
- Safe tools (`elefanteSystemEnable`, `elefanteSystemDisable`, `elefanteSystemStatusGet`, `elefanteDashboardOpen`) always available

##### Usage
```
User: "Enable Elefante"
Agent calls: elefanteSystemEnable -> Acquires locks -> Memory tools now work

User: "Disable Elefante" (before switching IDEs)
Agent calls: elefanteSystemDisable -> Releases locks -> Safe for other IDE
```

---

## [1.0.0] - 2025-12-06

### Summary
First stable production release with comprehensive documentation cleanup.

### Core Features
- **Triple-Layer Memory Architecture**
  - ChromaDB for semantic/vector search
  - Kuzu for knowledge graph relationships
  - Session context for conversation continuity

- **MCP Server with 15 Tools**
  - `addMemory` - Store with intelligent ingestion (NEW/REDUNDANT/RELATED/CONTRADICTORY)
  - `searchMemories` - Hybrid search (semantic + structured + context)
  - `queryGraph` - Execute Cypher queries on knowledge graph
  - `getContext` - Retrieve comprehensive session context
  - `createEntity` - Create nodes in knowledge graph
  - `createRelationship` - Link entities with relationships
  - `getEpisodes` - Browse past sessions with summaries
  - `getSystemStatus` - Mode + lock info + (when enabled) system stats
  - `consolidateMemories` - Merge duplicates & resolve contradictions
  - `listAllMemories` - Export/inspect all memories
  - `getElefanteDashboard` - Launch visual Knowledge Garden UI (optionally refresh)
  - `setElefanteConnection` - Upsert entities + create relationships in one call
  - `migrateMemoriesV3` - Admin schema migration to V3

- **Cognitive Memory Model**
  - Agent-managed enrichment of emotions, intent, entities, relationships (no internal LLM calls)
  - Strategic insight generation
  - ADD/UPDATE/IGNORE action logic

- **Temporal Memory Decay**
  - Memories decay over time
  - Reinforced on access
  - Configurable decay rate

- **Visual Dashboard**
  - React/Vite frontend at http://127.0.0.1:8000
  - Force-directed graph visualization
  - Node inspector with full details

- **Automated Installation**
  - Pre-flight checks for common issues
  - Kuzu 0.11+ compatibility handling
  - IDE auto-configuration (VS Code, Cursor)

### Documentation
- Neural Register architecture (5 master registers)
- Domain compendiums for issue tracking
- Technical reference documentation
- Planning roadmaps

### Known Limitations
- Memory Schema V2 taxonomy (domain/category) requires manual input - auto-classification planned for v1.1.0
- Dashboard UX needs improvement - semantic zoom planned
- Smart UPDATE (merge) not yet implemented

---

## Pre-1.0 Development History

Development prior to v1.0.0 used inflated version numbers during rapid iteration.
These have been consolidated into this baseline release.

| Date | Internal Label | What Happened |
|------|----------------|---------------|
| 2025-11-27 | "v1.1.0" | Initial repository setup |
| 2025-12-02 | "v1.2.0" | User profile integration |
| 2025-12-04 | "v1.2.0" | Kuzu reserved word fix (`properties` -> `props`) |
| 2025-12-05 | "v1.3.0" | Documentation cleanup |
| 2025-12-06 | **v1.0.0** | Official baseline release |

---

## Migration Notes

### From Pre-1.0 Development
If upgrading from internal development versions:
1. Database schema changed (`properties` -> `props`)
2. Run `python scripts/init_databases.py` to reinitialize
3. Documentation restructured into `technical/`, `debug/`, `planning/`, `archive/`

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.