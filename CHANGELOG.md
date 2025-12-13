# Changelog

All notable changes to Elefante will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- Agent-managed enrichment architecture: Elefante never calls an LLM; agents pass enrichment via tool inputs.

### Changed
- MCP tool names standardized with an `elefante*` prefix (see MCP tool list in `src/mcp/server.py`).
- Protocol injection key standardized to `MANDATORY_PROTOCOLS_READ_THIS_FIRST`.

### Removed
- Internal LLM connectivity and config/env overrides for LLM providers.
- OpenAI-based embeddings provider path (embeddings are local-only via sentence-transformers).

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

## [Unreleased]

### Planned for v1.1.0
- Auto-classification of domain/category via LLM
- Smart UPDATE (merge instead of duplicate)
- Dashboard semantic zoom
- Improved label rendering

### Planned for v1.2.0
- Automatic relationship inference
- Knowledge clustering
- Contradiction detection

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