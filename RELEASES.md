# Elefante Releases

This file is a high-level, human-readable index of released versions.
For full detail, see [CHANGELOG.md](CHANGELOG.md).

---

## Current Baseline (recommended)

- **v2.2.1 (2026-02-26)**
  - **Critical fix**: Memory deletion no longer poisons the co-activation graph with stale UUIDs.
  - `_handle_delete_memory()` purges deleted IDs from `_session_retrieval_history`.
  - `record_coactivation()` validates IDs exist in ChromaDB before running O(n^2) graph queries.
  - `scripts/version_counsel.py` added: smart version advisor (MAJOR/MINOR/PATCH classification from staged diff).
  - `bump_version.py` gets `[0-99]` range validation; `CONTRIBUTING.md` versioning rewritten.

## Previous Releases

- **v2.1.3 (2026-02-26)**
  - Windows clean installation: `fcntl` guard, `KUZU_DIR` fix, `install.bat` version parse fix, `py -3.11` launcher support.
  - Windows Golden Path documented in `docs/technical/installation.md`.
  - Windows Pitfalls section added to `docs/pitfall-index.md` (6 entries).
  - Pre-action gate promoted from memory to Directive (unconditional enforcement).
  - `bump_version.py` expanded to cover 25 files; Windows `encoding='utf-8'` fix.
  - All 25 version references updated to 2.1.3 across codebase.

- **v2.1.2 (2026-02-25)**
  - Passive Co-Activation: Automatically generates graph connections between memories retrieved sequentially.
  - Smoothed Vector Baseline: Exponential scaling applied to cognitive context scores, fixing muted heuristic suppression.
  - Response Optimization: Context stripped of nulls to save tokens and prepended with actionable agent summaries.
  - Compliance Gate Hardening: Blocked stateless multi-tool agent bypasses with strict NO GUESSING edicts.
  - Dashboard Validation: Full headless verification of Chroma and Kuzu insight rendering.

- **v2.1.1 (2026-02-19)**
  - Dashboard field mapping fix: categories and usage counts now display correctly
  - Directive System: behavioral constraints separated from memories, always injected into every tool response
  - Tool Response Contract: `MANDATORY_PROTOCOLS_READ_THIS_FIRST`, `DIRECTIVES`, `RELEVANT_CONTEXT` documented as first-class architecture
  - Installation bootstrap: Step 4a validates `copilot-instructions.md` exists
  - Tool count: 17 → 20 (added `elefante-DirectiveAdd`, `elefante-DirectiveList`, `elefante-DirectiveRemove`)

- **v2.1.0 (2026-02-19)**
  - Directive System, Tool Response Contract, installation bootstrap (superseded by v2.1.1)

- **v2.0.0 (2026-02-18)**
  - Memory curation: 13 high-signal memories, zero noise
  - Dashboard v2: Health Score, Knowledge Graph, Usage Intelligence
  - Unified versioning across all components

- **v1.10.0 (2026-01-18)**
  - Behavioral Relevance: system-computed scores (0–100) replace human-assigned importance
  - Tool renaming: `elefanteCamelCase` → `elefante-PascalCase` across all 17 tools + 2 prompts
  - `memory_class` field (fact/directive/state) for contradiction detection
  - Tool consolidation: GraphEntityCreate + GraphRelationshipCreate → GraphConnect, MemoryListAll → MemorySearch (list_all=true), TaskDecompose → TaskCreate (subtasks), ETLStatus → ETLProcess (include_stats=true)
  - Compliance Gate v2: enforced via server, blocks writes until search
  - Automatic context injection on every non-skip tool call
  - Full documentation rewrite for production readiness

---

## Release Index

- **v1.9.1 (2026-02-09)**
  - Tool consolidation: 24 → 17 tools with zero feature loss
  - GraphConnect batch upsert with ref-based linking

- **v1.6.0 (2025-12-28)**
  - Compliance Gate: enforced search-before-write for all write tools
  - Layered defense via `.github/copilot-instructions.md`

- **v1.5.0 (2025-12-28)**
  - V5 cognitive features: retrieval explanations, memory health, conflict detection, proactive surfacing

- **v1.4.0 (2025-12-27)**
  - V4 cognitive retrieval engine: 6-signal composite scoring (replaces raw vector similarity)

- **v1.3.0 (2025-12-27)**
  - Embedding model upgrade shipped: `thenlper/gte-base` (768-dim) and migration path for existing ChromaDB data

- **v1.2.0 (2025-12-27)**
  - Minor fixes and preparation work for schema/migration operations
  - Embedding model evaluation and test batteries across multiple candidates
  - Decision milestone: `thenlper/gte-base` (768-dim) identified as the best option to ship next

- **v1.1.0 (2025-12-26)**
  - Transaction-scoped locking for multi-IDE safety

- **v1.0.1 (2025-12-11)**
  - Protocol enforcement + initial multi-IDE safety mode controls

- **v1.0.0 (2025-12-05)**
  - First production baseline release

---

## Verification (what “version” means)

- Runtime/package version is defined in `src/__init__.py`.
- Dashboard reports versions via `http://127.0.0.1:8000/api/stats`.
