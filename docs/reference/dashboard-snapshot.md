# Dashboard Snapshot Contract (`dashboard_snapshot.json`)

This document defines the **required** and **optional** fields for the dashboard snapshot file consumed by the dashboard server.

## Location

- The dashboard server reads from: `DATA_DIR/dashboard_snapshot.json`
- In typical installs, `DATA_DIR` resolves to `~/.elefante/data`.

## Top-level schema

Required:

- `generated_at`: ISO-8601 timestamp (string)
- `nodes`: array of node objects
- `edges`: array of edge objects
- `stats`: object with basic counts

Recommended:

- `curation`: object capturing snapshot curation provenance

### `stats`

Required keys:

- `total_nodes`: integer
- `memories`: integer
- `entities`: integer
- `edges`: integer

## Node schema

Each element of `nodes` is an object:

Required:

- `id`: string (unique)
- `type`: string (typically `memory`, `signal`, `entity`)
- `name`: string (display label; for memories this should be curated)

Optional / recommended:

- `description`: string
- `created_at`: ISO-8601 timestamp string
- `properties`: object (free-form)

### Memory node expectations

For `type == "memory"`, `properties` should include:

- `content`: raw text (may be present but should not be shown by default in UI)
- `title`: curated title (string)
- `summary`: curated one-sentence summary (string)
- `score`: **integer 0-100, ALWAYS live-computed** (see Score Contract below)

Classification (recommended, V5):

- `ring`, `topic`, `knowledge_type`

### Score Contract (CRITICAL)

**`score` MUST be computed live at snapshot generation time. NEVER read from stored `mem.metadata.score`.**

The stored `mem.metadata.score` in ChromaDB is a stale birth-time value that is only updated on retrieval (`record_access()`). Most memories are never retrieved, so their stored score stays at 100 forever.

**Single source of truth:** `src/utils/dashboard_serializer.py`

Two entry points, both converging on `_composite_dashboard_score()`:
- `compute_live_score(mem: Memory)` — from Memory objects (MCP server path)
- `compute_live_score_from_raw(meta: dict)` — from raw ChromaDB metadata (standalone script path)

**Formula:** `composite = vitality * 0.50 + type_weight * 0.25 + engagement * 0.25`

Where:
- `vitality` = `exp(-effective_decay_rate * age_days) * exp(-0.005 * days_since_access)`
- `type_weight` = inherent importance (specification=1.0 ... conversation=0.45)
- `engagement` = `min(1.0, log(access_count + 1) / log(20))`

**Expected distribution:** Avg ~75, Min ~54, Max ~94. Score=100 count should be 0-1.

**All node serialization** must go through `memory_to_dashboard_node()` in the shared module. No inline node-building is permitted anywhere.

## Edge schema

Each element of `edges` is an object:

Required:

- `from` or `source`: node id (string)
- `to` or `target`: node id (string)

Recommended:

- `type`: string (`signal`, `cohesion`, `graph`, `semantic`, etc.)
- `label`: string
- `similarity`: number (only for semantic)

## Invariants

- Every edge endpoint must reference an existing node id.
- Node ids are unique.
- `stats.*` should match actual counts (validator will check and warn).
