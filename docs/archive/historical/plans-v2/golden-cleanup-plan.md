# Elefante Golden Memories Cleanup Plan

## ZLCTP CONTEXT PACKAGE — Golden Demo Cleanup

### 1. The "North Star" Definition
* **The Goal:** Transform 121 raw memories into a "golden demo" dataset where every memory has a meaningful topic, a calculated score, and correct status — making the dashboard insightful and demonstrating Elefante's best capabilities.
* **The "Why":** 91% of memories are tagged "general," all scores are 0, and 25 memories are falsely marked "contradictory." The dashboard shows "28% health" because the metadata is broken, not the data itself. Fix the metadata = fix the dashboard = prove the product works.
* **Current Phase:** Plan approved by user. Build the cleanup script.

---

### 2. Data Audit Summary (Hard Numbers)

| Metric | Current State | Target State |
|---|---|---|
| Total memories | 121 | 121 (no deletions) |
| Topic: "general" | 110 (91%) | ~4 (3%) |
| Topics in use | 7 | 12+ |
| All scores | 0 (every single one) | Calculated 1-10 |
| Status: "contradictory" | 25 | 0 |
| Status: "related" | 80 | 80 (unchanged) |
| Status: "new" | 16 | 16 (unchanged) |
| Connectivity | 121/121 (100%) | 121/121 (unchanged) |
| Content quality | All have titles + summaries | Unchanged (already clean) |

#### Topic Reclassification Map (from content analysis)

106 of 110 "general" memories are classifiable by keyword matching:

| Proposed Topic | Count | Sample Keywords |
|---|---|---|
| `debugging` | 41 | debug, error, fix, bug, crash, deadlock, corruption |
| `documentation` | 21 | doc., readme, compendium, neural-register, docs/ |
| `architecture` | 17 | architecture, design, pattern, pipeline, retriev, system |
| `agent-behavior` | 10 | agent, loop, protocol, behavior, cognitive, retrieval |
| `database` | 6 | kuzu, chroma, schema, query, graph store, reserved word |
| `tools-environment` | 4 | vscode, terminal, install, path, config, setup |
| `user-profile` | 3 | preference, user background, identity, model |
| `testing` | 3 | test, pytest, e2e, verify, validation |
| `coding-standards` | 1 | code, style, format, naming, convention |
| **Unclassifiable** | **4** | Will remain "general" |

Already-classified memories (11 total across communication, tools-environment, coding-standards, agent-behavior, workflow, collaboration) stay unchanged.

---

### 3. The 4-Step Cleanup (Metadata Only — No Content Changes)

#### Step 1: Re-Topic (110 → ~4 "general")
- Read each memory's `content` + `title` from ChromaDB
- Run keyword classifier (the map above) to assign best-fit topic
- Only change `topic` field in metadata — content is untouched
- 4 memories that don't match any keyword pattern stay as "general"

#### Step 2: Re-Score (all 0 → calculated 1-10)
Formula:
```
score = (
    content_length_score    # 0-3: short=1, medium=2, long=3
  + has_specific_topic      # 0-2: general=0, specific=2
  + has_connections          # 0-2: orphan=0, connected=2 (all are connected, so all get 2)
  + freshness_score         # 0-2: >90d=0, 30-90d=1, <30d=2
  + type_value              # 0-1: insight/decision=1, fact=0.5, preference=0.5
)
# Clamped to 1-10 range
```

#### Step 3: Fix Contradictory Status (25 → 0)
- These 25 memories were flagged by the consolidation pipeline as "contradictory" but content review shows they are valid facts/decisions/laws
- Set `status` from "contradictory" to "active"
- This is a known pipeline false-positive issue

#### Step 4: Regenerate Snapshot
- Run `python scripts/update_dashboard_data.py` to rebuild `dashboard_snapshot.json`
- Restart dashboard server
- Verify dashboard shows healthy metrics

---

### 4. Script Architecture: `scripts/golden_cleanup.py`

```
Usage:
  python scripts/golden_cleanup.py --dry-run    # Preview all changes (NO writes)
  python scripts/golden_cleanup.py --apply      # Write changes to ChromaDB
```

**Key design decisions:**
- Reads/writes directly to ChromaDB (not the snapshot JSON)
- `--dry-run` is the default — shows a table of proposed changes
- `--apply` requires explicit flag to write
- Backs up ChromaDB metadata before writing (JSON dump to `data/pre_golden_backup.json`)
- Only modifies 3 metadata fields: `topic`, `score`, `status`
- Never touches `content`, `title`, `summary`, `memory_type`, or any other field

**ChromaDB access pattern:**
```python
import chromadb
client = chromadb.PersistentClient(path=str(Path.home() / ".elefante" / "data" / "chroma_db"))
collection = client.get_collection("memories")
# Read: collection.get(ids=[...], include=["metadatas", "documents"])
# Write: collection.update(ids=[id], metadatas=[{...updated metadata...}])
```

---

### 5. Expected Dashboard Result After Cleanup

| Metric | Before | After |
|---|---|---|
| Overall Health | ~28% | ~65-75% |
| Freshness | unchanged | unchanged (date-dependent) |
| Topic Coverage | 9% | ~97% |
| Connectivity | 100% | 100% |
| Topics visible in treemap | 7 unbalanced | 12+ balanced |
| Score distribution | all 0 | spread across 1-10 |
| Contradictory count | 25 | 0 |

---

### 6. Instructions for the Next Agent

* **Persona:** Python backend developer familiar with ChromaDB
* **Tone/Style:** Direct, technical, no fluff
* **Task:** Build `scripts/golden_cleanup.py` following the architecture above
* **Key files to reference:**
  - [scripts/audit_golden_deep.py](scripts/audit_golden_deep.py) — the audit that produced the numbers above
  - [scripts/update_dashboard_data.py](scripts/update_dashboard_data.py) — snapshot regeneration script
  - [src/dashboard/ui/src/hooks/useVisualizationData.ts](src/dashboard/ui/src/hooks/useVisualizationData.ts) — health score formula (frontend)
  - ChromaDB path: `~/.elefante/data/chroma_db`, collection name: `"memories"`
* **Critical constraints:**
  - NEVER modify memory content, title, or summary
  - NEVER delete memories
  - NEVER fabricate new memories
  - Only modify: `topic`, `score`, `status`
  - Always backup before writing
  - `--dry-run` must be default mode
* **After building:** Run `--dry-run` and show the output to the user for approval

---

**STATUS:** Plan approved. Ready to build `scripts/golden_cleanup.py`.
