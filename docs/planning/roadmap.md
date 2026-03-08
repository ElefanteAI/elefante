# Elefante Development Roadmap

**Current Version**: v2.2.0  
**Last Updated**: 2026-02-26

---

## v2.0.0 — Production Release

v2.0.0 established the production baseline. All core infrastructure is implemented, tested, and documented.

### Shipped Features

| Feature                                                         | Status     | Since  |
| --------------------------------------------------------------- | ---------- | ------ |
| Dual storage (ChromaDB + Kuzu)                                  | Production | v1.0.0 |
| MCP server (20 tools + 2 prompts)                               | Production | v2.1.0 |
| Transaction-scoped locking                                      | Production | v1.1.0 |
| Compliance Gate (search-before-write)                           | Production | v1.6.0 |
| Behavioral Relevance scoring (0-100)                            | Production | v2.0.0 |
| Temporal memory decay with type-based rates                     | Production | v1.0.0 |
| Cognitive retrieval (V4: concepts, authority, surfaces_when)    | Production | v1.6.3 |
| Agent ETL classification pipeline (ring, topic, knowledge_type) | Production | v1.6.3 |
| Dashboard (React + SVG, 3-tab architecture)                     | Production | v2.0.0 |
| Context injection (auto-surfaces top 3 memories)                | Production | v1.0.0 |
| Session Distiller (scan, parse, ingest from VS Code chat)       | Production | v2.0.0 |
| Actionable Integration (behavioral forcing headers)             | Production | v2.1.2 |
| Response Compression (null stripping, token efficiency)         | Production | v2.1.2 |
| Smoothed Vector Baseline (fixes low similarity scores)          | Production | v2.1.2 |
| Autonomous Co-Activation (passive graph wiring)                 | Production | v2.1.2 |

### Known Design Flaws (Open)

| Issue                                          | Severity | Reference                                  |
| ---------------------------------------------- | -------- | ------------------------------------------ |
| Response Bloat: ~500 tokens/memory (90% nulls) | CRITICAL | `docs/debug/memory-compendium.md` Issue #7 |
| Low Similarity: exact matches score 0.37-0.39  | HIGH     | `docs/debug/memory-compendium.md` Issue #8 |
| No Action Guidance: raw JSON, no summary       | HIGH     | `docs/debug/memory-compendium.md` Issue #9 |

---

## Next Phase (Planned)

### Priority 1: Response Compression (Shipped - v2.1.2)

Fixed Issue #7 and #9. Search returns are now mathematically compressed, stripping all null/empty structures before serializing to MCP. Appends a strict behavioral directive header to ensure LLM usage.

### Priority 2: Retrieval Explanation

Every search result should include WHY it was retrieved — breakdown of vector similarity, concept overlap, domain match, authority, and temporal signals.

**Files**: `src/core/retrieval.py`, `src/mcp/server.py`

### Priority 3: Memory Health Score

Every memory gets a health indicator: healthy, stale (90+ days untouched), at-risk (contradicted/superseded), or orphan (no connections).

**Files**: `src/utils/curation.py`, `scripts/update_dashboard_data.py`

### Priority 4: Potential Conflict Detection

Flag memories with high concept overlap and opposing patterns for user review. Soft detection — system suggests, user confirms.

**Files**: `src/utils/curation.py`, `src/core/orchestrator.py`

### Priority 5: Dashboard UX

- Color by memory type or domain
- Show only high-relevance nodes by default
- Health indicators on nodes

**Files**: `src/dashboard/ui/src/components/`

---

## Future Phases

### Smart UPDATE (Merge)

Merge new info with existing memories instead of duplicating. Track version history.

### Proactive Memory Surfacing

System suggests relevant memories without user searching, based on file context, error patterns, and conversation keywords.

### Co-Activation Tracking (Shipped - v2.1.2)

Tracks which memories are frequently retrieved together and automatically constructs `CO_ACTIVATED` graph edges to naturally boost future semantic retrieval groupings.

### Multi-Modal

Image memory support. Audio transcription integration.

---

## Full Feature Requirements

See [`v5-cognitive-retrieval-requirements.md`](v5-cognitive-retrieval-requirements.md) for detailed specifications of planned features.

---

For project vision, see [`vision.md`](vision.md)
