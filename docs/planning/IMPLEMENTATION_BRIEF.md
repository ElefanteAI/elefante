# Elefante: Implementation Brief
## The Cohesive Larger Vision — Analysis, Audit, and Agenda

**Date**: 2026-02-18  
**Version Target**: v2.1.0 (Unified)  
**Scope**: Complete codebase audit → gap analysis → ordered implementation agenda  
**For**: A fresh agent that will implement, not plan

---

## 0. The Mandate

> *"The hardest task isn't making a small technical demo, but fitting technology into a cohesive larger vision that can sell billions of dollars of product annually."*

This document exists because Elefante accumulated **four overlapping classification systems** across releases. None were scrapped, each served a purpose, and the result is a codebase where the most powerful features are **built but not wired**, and the most used features are **wired but incomplete**.

The mission is NOT to start over. It is to **complete what was started**: make all the classification machinery actually serve retrieval quality, visible to users, and self-maintaining without manual agent intervention.

---

## 1. System Architecture: What Actually Exists

### 1.1 The Physical Stack

```
MCP Client (VS Code / Cursor / Claude Desktop)
        │  stdio  (20 tools, 2 prompts)
        ▼
src/mcp/server.py          ← Entry point, Compliance Gate, pitfall injection
        │
        ▼
src/core/orchestrator.py   ← Central brain (2020 lines) — ALL operations route here
        │
        ├──► src/core/vector_store.py      ← ChromaDB (cosine similarity)
        ├──► src/core/graph_store.py       ← Kuzu (Cypher, entity/relationship graph)
        ├──► src/core/embeddings.py        ← SentenceTransformers (local, no API key)
        ├──► src/core/retrieval.py         ← CognitiveRetriever (V4/V5 scoring)
        ├──► src/core/etl.py               ← ETL pipeline (Phase 1 raw, Phase 2 classify)
        ├──► src/core/metadata_store.py    ← SQLite (fast session lookups)
        ├──► src/core/refinery.py          ← Deterministic duplicate cleanup
        ├──► src/core/scoring.py           ← Adaptive weight normalization
        ├──► src/core/deduplication.py     ← Deduplication during merge
        └──► src/core/conversation_context.py ← Session message window

Dashboard (standalone FastAPI server, port 8000):
        src/dashboard/server.py            ← Serves static React build
        src/dashboard/ui/                  ← React/TypeScript/Vite (3 tabs)
        scripts/update_dashboard_data.py   ← Generates snapshot JSON

Session Distiller (optional LLM integration):
        src/modules/distiller/engine.py    ← Multi-backend LLM (ollama/openai/anthropic)
        src/modules/distiller/ingester.py  ← Ingests distilled insights via orchestrator

Config:
        config.yaml                        ← All settings (user_profile, db paths, etc.)
        src/utils/config.py                ← Pydantic config loader
```

### 1.2 The Data Schema (What a Memory Actually Is)

A memory lives in **two places** simultaneously:

**ChromaDB** (vector store) — stores:
- `id` (UUID)
- `content` (str, the actual text)
- `embedding` (float[], from SentenceTransformers)
- `metadata` (flat dict — ChromaDB limitation, no nested objects):
  - `memory_type`, `domain`, `category`, `score`, `tags` (JSON string), `status`
  - `title`, `summary`, `concepts` (JSON string), `surfaces_when` (JSON string)
  - `authority_score`, `processing_status`
  - `ring`, `knowledge_type`, `topic` ← V5 fields (often empty)
  - `deprecated`, `archived`, `access_count`, `created_at`, `last_accessed`

**Kuzu** (graph store) — stores:
- `Entity` node (id, name, type, description, properties JSON blob)
- `Relationship` edges (RELATES_TO, CONTRADICTS, SUPERSEDES, CREATED_IN, etc.)
- `Task` nodes (task orchestration)
- Session-memory links

**SQLite** (metadata fast store):
- Session memory index for fast `get_session_metadata()` lookups
- Uses `StandardizedMetadata` model (separate from main `MemoryMetadata`)

---

## 2. The Four Classification Systems

This is the core problem. Four overlapping vocabularies exist simultaneously. Understanding their STATUS is the prerequisite to any implementation work.

---

### SYSTEM 1: V3 Layer/Sublayer (src/core/classifier.py)

**What it is**: Regex-based content classification into a 3-layer ontology:
```
self/identity, self/preference, self/constraint
world/fact, world/failure, world/method
intent/rule, intent/goal, intent/anti-pattern
```
Also: `calculate_importance(content, layer, sublayer) → int 1-10`

**Status: ZOMBIE** [WARNING]

The functions (`classify_memory()`, `calculate_importance()`, `classify_memory_full()`) are defined in `classifier.py` but **never called from the main pipeline** (`orchestrator.py` does not import or invoke them). The module is dead code performing no function.

**BUT it has three active tentacles:**
1. `curation.py generate_title()` takes `layer` and `sublayer` params → called from `orchestrator.py` STEP 3 as `generate_title(content, layer=memory_type, sublayer="general")` — so it receives the V2 memory_type string in place of V3 layer, producing titles like `preference.general: I prefer black...`
2. `refinery.py _is_preference_like()` checks `metadata.layer == "self"` → this reads a field that NO memory has anymore (V5 dropped layer from schema), so it always returns False
3. `topology.py classify_topology()` accepts `layer`, `sublayer`, `importance` as inputs → these come from the old V3 vocabulary that no longer exists in production data

**Conclusion**: V3 is dead but its shadow shapes title generation (via mismatched param usage) and topology classification (via unused input params). It must be cleanly removed, not just ignored.

---

### SYSTEM 2: V4 Cognitive Retrieval Fields (src/utils/curation.py + src/core/retrieval.py)

**What it is**: Automatic extraction of structured retrieval signals at ingestion time:
```python
concepts: List[str]          # 3-5 keywords for graph clustering (Jaccard overlap during scoring)
surfaces_when: List[str]     # Query trigger patterns ("when discussing Python")
authority_score: float       # importance × access × freshness blended score
co_activated_with: List[UUID] # Memories retrieved together (co-activation matrix)
```

**Status: PARTIAL [OK][WARNING]**

**What's live**: `concepts` and `surfaces_when` are auto-extracted at ingestion (STEP 3.25 in `orchestrator.add_memory()`). `CognitiveRetriever.score_candidate()` IS called from `orchestrator._apply_cognitive_scoring()` and uses `concept_score` (Jaccard overlap between query concepts and memory concepts). This IS running on every search.

**What's broken**:
- `co_activated_with` field exists in `MemoryMetadata` but is NEVER populated. The co-activation matrix is passed as `[]` to `score_candidate()` → the `coactivation_score` signal (15% weight) is **always 0.0** for every memory on every query.
- `ProactiveSurfacer` class (300 lines in `retrieval.py`) is complete with temporal/domain/concept triggers but is **never invoked** from `orchestrator.py` or `server.py`.
- `MemoryConstellation` (primary/supporting/contradicting/context structure) is **defined and scored** in `CognitiveRetriever.build_constellation()` but `build_constellation()` is **never called** — `elefante-MemorySearch` returns a flat list, not a constellation.
- `surfaces_when` patterns are stored on memories but `ProactiveSurfacer.check_temporal_trigger()` which uses them is not connected.

---

### SYSTEM 3: V5 Knowledge Topology (src/core/topology.py + src/core/etl.py)

**What it is**: Agent-driven two-phase ETL for epistemic classification:
```
ring:           core | domain | topic | leaf
knowledge_type: law | principle | method | decision | insight | preference | fact
topic:          coding-standards | communication | workflow | agent-behavior |
                tools-environment | collaboration | general
```

**ETL Flow**:
1. **Phase 1** (automatic at ingestion): memory stored with `processing_status = "raw"`
2. **Phase 2** (manual, agent-driven): agent calls `elefante-ETLProcess` → gets raw memories → classifies with LLM → calls `elefante-ETLClassify` → V5 fields written to `custom_metadata`

**Status: PHANTOM** [WARNING][WARNING]

V5 fields are stored in `custom_metadata` dict (not typed `MemoryMetadata` fields). This means:
- They are **not accessible via search filters** (e.g., `filters.ring = "core"` does not exist in `SearchFilters`)
- They are **invisible to the CognitiveRetriever** (which reads typed `MemoryMetadata` fields, not custom dicts)
- They cannot be used in **Kuzu Cypher queries** without raw JSON parsing of the `props` blob

Phase 2 ETL almost never completes in practice. The result: **most memories in production have `ring=None`, `knowledge_type=None`, `topic=None`**. The Dashboard's "Topics" view in the Explore tab shows empty/incorrect data.

**The `topology.py` module** has fully functional deterministic classifiers (`classify_topology()`, `infer_knowledge_type()`, `infer_ring()`, `infer_topic()`) that require the old V3 `layer`/`sublayer` fields as inputs. These inputs don't exist in the V2 schema. The classifiers therefore work on empty strings and produce low-confidence fallback results.

**The Two-Phase Design Flaw**: The entire rationale for agent-driven Phase 2 was "leverage agent LLM intelligence for better classification." But deterministic keyword classification (topology.py) already handles ~90% of cases correctly. The agent LLM adds value only for ambiguous memories. Meanwhile, requiring agents to manually classify every memory creates friction that results in it never happening.

---

### SYSTEM 4: V2.0 Core Schema (src/models/memory.py MemoryMetadata)

**What it is**: The actual working schema. What every memory has when stored:
```python
memory_type:     MemoryType (8 active values: conversation/fact/insight/code/decision/task/note/preference)
memory_class:    MemoryClass (fact | directive | state) — controls contradiction behavior
domain:          DomainType (work/personal/learning/project/reference/system)
category:        str — free-form grouping label
score:           int 0-100 — behavioral relevance (system-computed from recency+access+decay)
tags:            List[str]
concepts:        List[str] — V4, auto-extracted
surfaces_when:   List[str] — V4, auto-extracted
authority_score: float — V4, computed at ingestion
status:          MemoryStatus (new/redundant/contradictory/related/deprecated/archived)
title:           str (in custom_metadata)
summary:         str (in custom_metadata)
decay_rate:      float — from TYPE_DECAY_RATES[memory_type]
```

**Status: LIVE [OK]** — This is the foundation everything else must extend.

---

### Parallel Model Problem: StandardizedMetadata (src/models/metadata.py)

A **second MemoryMetadata model** exists in `models/metadata.py`:
```python
CoreMetadata:    memory_type, source, importance (int), tags
ContextMetadata: session_id, project, file_path, line_number, parent_id
SystemMetadata:  created_at, updated_at, version, processing_time_ms, hash
StandardizedMetadata: core + context + system + custom (dict)
```

This model diverged from `MemoryMetadata` in `memory.py`:
- Uses `importance: int` (not `score: int 0-100`)
- Only 8 `MemoryType` values (not 12)
- Used exclusively by `metadata_store.py` (SQLite fast path)
- The `get_session_metadata()` fast path returns `StandardizedMetadata` objects, not real `Memory` objects

**Status: PARALLEL BUG [WARNING]** — The fast path and the full path return different data structures. The `get_context()` method attempts to merge them but produces inconsistent `score` values (SQLite returns `importance` where callers expect `score`).

---

## 3. The Actual Search Pipeline (What Fires on Every Query)

```
elefante-MemorySearch(query, mode="hybrid")
    │
    ▼
orchestrator.search_memories()
    │
    ├── 1. _search_semantic()     ← ChromaDB cosine similarity
    │       └── vector_store.search() → applies temporal decay → updates access_count
    │
    ├── 2. _search_structured()   ← Kuzu MATCH (Entity {type: 'memory'})
    │       └── loads memory from ChromaDB by ID → blends importance score
    │
    ├── 3. _merge_and_deduplicate()
    │       ├── ScoreNormalizer.adaptive_weights() ← query heuristics (pronouns→conversation boost)
    │       └── Deduplicator (cosine threshold 0.95)
    │
    └── 4. _apply_cognitive_scoring()    ← CognitiveRetriever
            │
            ├── analyze_query(query) → extracts concepts, infers domain/intent
            │
            └── score_candidate() per result:
                    vector_score     × 0.30  ← FROM ChromaDB [OK]
                    concept_score    × 0.20  ← Jaccard(query_concepts, memory_concepts) [OK]
                    domain_score     × 0.15  ← USUALLY 0.5 (neutral, no domain inferred) [WARNING]
                    coactivation     × 0.15  ← ALWAYS 0.0 (matrix never populated) [ERROR]
                    authority_score  × 0.10  ← From score + access_count [OK]
                    temporal_score   × 0.10  ← Recency/freshness decay [OK]
```

**Net effect**: The CognitiveRetriever operates at ~70% capacity. The `coactivation` signal (15% weight) is permanently 0. The `domain_match` signal usually contributes only 0.5×0.15 = 0.075 net. The actual discriminating signals are **vector + concept + temporal + authority** (combined weight = 0.70).

---

## 4. The Tool Surface

20 MCP tools exposed to agents:

| Tool | Purpose | Status |
|------|---------|--------|
| `elefante-System` | Enable/disable mode, acquire DB locks | [OK] Live |
| `elefante-SystemStatusGet` | Stats from both DBs | [OK] Live |
| `elefante-MemoryAdd` | Store new memory | [OK] Live |
| `elefante-MemorySearch` | Semantic/structured/hybrid search | [OK] Live |
| `elefante-MemoryUpdate` | Amend existing memory | [OK] Live |
| `elefante-MemoryDelete` | Delete with audit reason | [OK] Live |
| `elefante-MemoryConsolidate` | Deterministic dedup cleanup | [OK] Live |
| `elefante-ContextGet` | Session context with graph traversal | [OK] Live |
| `elefante-GraphQuery` | Raw Cypher on Kuzu | [OK] Live |
| `elefante-GraphConnect` | Batch entity/relationship upsert | [OK] Live |
| `elefante-SessionsList` | Recent session summaries | [OK] Live |
| `elefante-DashboardOpen` | Launch dashboard browser | [OK] Live |
| `elefante-TaskCreate` | Create task with optional subtasks | [OK] Live |
| `elefante-TaskUpdate` | Update task status/output | [OK] Live |
| `elefante-TaskGraph` | View task hierarchy | [OK] Live |
| `elefante-ETLProcess` | Get unclassified memories for agent | [OK] Live (rarely invoked) |
| `elefante-ETLClassify` | Submit V5 classification | [OK] Live (rarely invoked) |
| `_inject_context` | Auto context injection on every tool call | [OK] Live (internal) |
| `_inject_pitfalls` | Protocol enforcement injection | [OK] Live (internal) |
| `_compliance_gate` | Search-before-write enforcement | [OK] Live |

**Note**: The response format for `elefante-MemorySearch` currently returns a **flat list of memory objects** with the full metadata JSON. Known issue: ~500 tokens per memory result (90% null fields). No structured grouping into constellation (primary/supporting/contradicting/context).

---

## 5. The Distiller (Separate Module — Not Connected to V5)

`src/modules/distiller/` is a standalone LLM integration layer:

```python
DistillerEngine(backend="ollama"|"openai"|"anthropic"|"lmstudio")
    .distill(ChatSession) → DistillationResult(insights: List[DistilledInsight])

DistilledInsight:
    insight_type: InsightType (fact/preference/decision/rule/pattern/relationship/warning)
    content: str
    importance: int 1-10   ← STILL USES V3 1-10 SCALE
    confidence: float
    suggested_tags: List[str]
```

**Critical observation**: The Distiller uses its own `InsightType` enum (7 types) and `importance` on 1-10 scale — NOT connected to V5 topology. When `ingester.py` calls `orchestrator.add_memory()` with distilled insights, it maps `insight_type` → `memory_type` but discards the distiller's `importance` value (orchestrator ignores it per v1.10.0 design). The mapping:
```python
InsightType.RULE → memory_type="preference"
InsightType.PATTERN → memory_type="insight"
InsightType.WARNING → memory_type="note"
# etc.
```

The Distiller is the **LLM brain** of the system and produces the highest-quality memories. But it runs as a standalone CLI/scanner and is not integrated with the ETL topology pipeline.

---

## 6. Dead Code Inventory

Code that is defined, takes up cognitive space, and produces zero user value:

| File | Dead Code | Reason Dead |
|------|-----------|-------------|
| `src/core/classifier.py` | Entire file (classify_memory, calculate_importance, classify_memory_full) | Not imported anywhere in production pipeline |
| `src/core/consolidation.py` | Entire file (MemoryConsolidator.consolidate_recent returns []) | Stub only, no implementation |
| `src/core/retrieval.py` | `MemoryConstellation`, `build_constellation()` | Defined but never called |
| `src/core/retrieval.py` | `ProactiveSurfacer` (entire class) | Defined but never invoked from orchestrator or server |
| `src/core/topology.py` | `classify_topology()` with layer/sublayer/importance params | Inputs (V3 fields) don't exist in production data |
| `src/models/memory.py` | `co_activated_with`, `supports`, `contradicts` in MemoryMetadata | Never populated, query logic doesn't use them |
| `src/models/memory.py` | `urgency` (int 0-10), `intent` (IntentType) | Set to defaults, no code reads or uses them for ranking |
| `src/models/memory.py` | `question`, `answer`, `hypothesis`, `observation` in MemoryType | Never used in practice |
| `src/models/cognitive.py` | Entire file (CognitiveAnalysis, CognitiveIntent, etc.) | Not connected to any running pipeline |
| `src/models/metadata.py` | `StandardizedMetadata.core.importance` (int) | Uses 1-10 scale, conflicts with score (0-100) in MemoryMetadata |
| `src/utils/curation.py` | `classify_memory_type()` | Not called anywhere |
| `src/utils/curation.py` | `generate_title(layer, sublayer)` with V3 params | Called with `layer=memory_type, sublayer="general"` — produces V3-style titles |

---

## 7. The Gap Map: Vision vs Reality

| Vision Feature | Built | Wired | Working | Gap |
|---------------|-------|-------|---------|-----|
| Behavioral scoring (score 0-100) | [OK] | [OK] | [OK] | None |
| Semantic search via ChromaDB | [OK] | [OK] | [OK] | None |
| Graph search via Kuzu | [OK] | [OK] | [OK] | None |
| Temporal decay by memory type | [OK] | [OK] | [OK] | None |
| Compliance Gate | [OK] | [OK] | [OK] | None |
| Auto context injection | [OK] | [OK] | [OK] | None |
| Concept extraction (V4) | [OK] | [OK] | [OK] | None |
| Concept-overlap scoring (V4) | [OK] | [OK] | [OK] | None |
| Co-activation scoring (V4) | [OK] | [OK] | [ERROR] | Matrix never populated |
| Proactive memory surfacing (V4) | [OK] | [ERROR] | [ERROR] | ProactiveSurfacer unconnected |
| Memory constellation (V4) | [OK] | [ERROR] | [ERROR] | build_constellation never called |
| V5 topology (ring/type/topic) | [OK] | [WARNING] | [WARNING] | Stored in custom_metadata, mostly empty |
| V5 auto-classification | [OK] code | [ERROR] | [ERROR] | topology.py isolated from pipeline |
| V5 topology as search filter | [ERROR] | [ERROR] | [ERROR] | SearchFilters has no ring/topic fields |
| Memory health indicators | [OK] | [WARNING] | [WARNING] | MemoryHealthAnalyzer in dashboard only |
| Conflict detection | [OK] | [WARNING] | [WARNING] | Dashboard only, not surfaced in search |
| Retrieval explanation (V5 Req-1) | [OK] | [OK] | [OK] | Works, included in result.explanation |
| Flat list search response | [OK] | [OK] | [OK] | Works but verbose (500 tokens/memory) |
| Constellation search response | [OK] | [ERROR] | [ERROR] | MCP still returns flat list |
| Distiller LLM integration | [OK] | [OK] | [OK] | Standalone, runs on demand |
| Distiller → V5 topology | [ERROR] | [ERROR] | [ERROR] | Distiller uses own InsightType vocabulary |

---

## 8. The Cohesive Vision: How All Pieces Unify

The fundamental problem is **three classification vocabularies trying to describe the same truth**:

```
V3 (dead): self/world/intent × identity/preference/failure/method/...
V5 (phantom): ring × knowledge_type × topic
Distiller (isolated): InsightType × importance(1-10)
```

All three describe the **epistemic weight and retrieval context** of a memory. They need to be **one vocabulary**.

### The Unified Topology (The Single Truth)

```
ring:           WHERE in the cognitive hierarchy (core/domain/topic/leaf)
knowledge_type: WHAT KIND of knowledge (law/principle/method/decision/insight/preference/fact)
topic:          WHAT DOMAIN it belongs to (coding-standards/workflow/agent-behavior/...)
memory_type:    HOW it decays (conversation/fact/insight/code/decision/task/note/preference)
```

`ring + knowledge_type + topic` → **epistemic classification** (how important and how clustered)  
`memory_type` → **temporal classification** (how fast it ages)  
`score` → **behavioral classification** (how used and how recent)

These three axes are **orthogonal and complementary**. They don't overlap. They never should have been four systems.

### The Unified Flow That Should Exist

```
elefante-MemoryAdd(content, memory_type, domain, category)
    │
    ├── STEP 1: Dedup check → title-based + semantic similarity
    ├── STEP 2: Preference re-assertion merge
    ├── STEP 3: V4 auto-extract → concepts, surfaces_when, authority_score
    ├── STEP 4: V5 auto-classify → topology.classify_topology()
    │           (deterministic, instant, no LLM needed for 90% of memories)
    │           ring, knowledge_type, topic → stored as TYPED schema fields
    ├── STEP 5: Write to ChromaDB + Kuzu
    └── STEP 6: Return memory with full classification populated
```

**No Phase 2 ETL needed** for deterministic classification. Phase 2 ETL becomes an **optional enhancement** path (agent can override auto-classification when it knows better).

---

## 9. Implementation Agenda

Ordered by impact and safety. Each item is self-contained and testable.

---

### PHASE A: REMOVE THE DEAD (No risk, pure cleanup)

**A1. Retire classifier.py**

`src/core/classifier.py` — delete or move to `src/core/archive/`. Remove any lingering imports.

```python
# Remove these from any file that imports them:
from src.core.classifier import classify_memory, calculate_importance, classify_memory_full
```

After removal, verify no tests break (the test files already removed V3 fields in v2.0.0 cleanup).

**A2. Remove skeleton consolidation.py**

`src/core/consolidation.py` returns `[]` and has no implementation. The `MemoryConsolidate` MCP tool routes through `orchestrator.consolidate_memories()` which calls `MemoryRefinery.run()` directly. Remove `consolidation.py` and clean up the import in orchestrator.

**A3. Fix generate_title() V3 legacy param usage**

In `src/utils/curation.py`, `generate_title(content, layer, sublayer, max_len)` creates titles like `preference.general: I prefer black formatter`. This is V3 vocabulary bleeding into V5 output.

Change the function signature to use V5 vocabulary:
```python
# Before:
def generate_title(*, content: str, layer: str, sublayer: str, max_len: int = 90) -> str:

# After:
def generate_title(*, content: str, memory_type: str = "fact", max_len: int = 90) -> str:
```

The title format should be the V5 naming convention `[TYPE] Core::Concept` pattern. Update the call site in `orchestrator.add_memory()` accordingly.

**A4. Fix refinery.py dead layer check**

In `src/core/refinery.py`, `_is_preference_like()` checks:
```python
layer = str(getattr(m.metadata, "layer", "") or "").strip().lower()
```
`metadata.layer` doesn't exist in V2 schema. Replace with:
```python
try:
    mem_type = str(m.metadata.memory_type)
except Exception:
    mem_type = ""
return mem_type.lower() == "preference"
```

---

### PHASE B: PROMOTE V5 TOPOLOGY TO FIRST-CLASS FIELDS

This is the most impactful change. V5 fields (`ring`, `knowledge_type`, `topic`) need to be first-class typed fields in `MemoryMetadata`, not buried in `custom_metadata`.

**B1. Add V5 fields to MemoryMetadata**

In `src/models/memory.py`, add to `MemoryMetadata`:
```python
# V5 Topology (promoted from custom_metadata)
ring: Optional[str] = Field(default=None, description="core | domain | topic | leaf")
knowledge_type: Optional[str] = Field(default=None, description="law | principle | method | decision | insight | preference | fact")
topic: Optional[str] = Field(default=None, description="coding-standards | communication | workflow | agent-behavior | tools-environment | collaboration | general")
```

**B2. Add V5 fields to SearchFilters**

In `src/models/query.py`, add to `SearchFilters`:
```python
ring: Optional[str] = None
knowledge_type: Optional[str] = None
topic: Optional[str] = None
```

And propagate to `VectorStore.search()` in `vector_store.py` where metadata filters are built (ChromaDB supports `where={"ring": {"$eq": "core"}}`).

**B3. Add V5 fields to VectorStore serialization**

In `src/core/vector_store.py`, in `add_memory()`, ensure `ring`, `knowledge_type`, `topic` from `MemoryMetadata` are serialized as top-level Chroma metadata fields (not only inside `custom_metadata`). Similarly in `_result_to_memory()`, deserialize them back.

**B4. Migrate existing memories**

Create `scripts/migrate_v5_fields.py`:
- Load all memories from ChromaDB
- For each memory, check if `ring`, `knowledge_type`, `topic` are in `custom_metadata` but not in top-level metadata
- Promote them to top-level fields
- Re-write the memory

---

### PHASE C: WIRE AUTO-CLASSIFICATION AT INGESTION

**C1. Fix topology.py to use V5 inputs (not V3)**

`src/core/topology.py` `classify_topology()` currently takes `layer`, `sublayer`, `importance` (V3 schema). Change it to take V2/V5 inputs:

```python
def classify_topology(
    content: str,
    title: str = "",
    memory_type: str = "",     # V2: maps directly to knowledge hint
    domain: str = "",          # V2: domain maps to ring hint
    category: str = "",        # V2: category maps to topic hint
    tags: str = "",
    score: int = 50,           # V2: replaces importance
) -> Dict[str, Any]:
```

Update `infer_ring()`, `infer_knowledge_type()` to use these V2 fields as hints instead of V3 layer/sublayer.

**C2. Wire auto-classification in orchestrator.py STEP 3.5**

In `orchestrator.add_memory()`, after STEP 3.25 (V4 cognitive fields), add STEP 3.5 auto-classification:

```python
# STEP 3.5: AUTO-CLASSIFY V5 TOPOLOGY (deterministic, instant)
# ETL Phase 2 is still available for agent override, but 90% of cases are handled here.
from src.core.topology import classify_topology

topology = classify_topology(
    content=content,
    title=title,
    memory_type=memory_type,
    domain=str(domain),
    category=str(category),
    tags=" ".join(tags or []),
    score=50,  # Initial score
)

# Populate typed fields directly
memory_metadata = MemoryMetadata(
    ...
    ring=topology["ring"],
    knowledge_type=topology["knowledge_type"],
    topic=topology["topic"],
    ...
)
```

**C3. Mark auto-classified memories appropriately**

Set `processing_status = "auto_classified"` (new status in `ProcessingStatus`) for deterministic auto-classification. Agent-driven classification (ETL Phase 2) sets `processing_status = "processed"`. This distinguishes them and still allows agents to refine auto-classified memories.

Add to `ProcessingStatus`:
```python
class ProcessingStatus:
    RAW = "raw"
    PROCESSING = "processing"
    AUTO_CLASSIFIED = "auto_classified"  ← NEW
    PROCESSED = "processed"
    FAILED = "failed"
```

---

### PHASE D: WIRE THE CONSTELLATION

**D1. Call build_constellation() in search**

In `orchestrator._apply_cognitive_scoring()`, after scoring all candidates, call `CognitiveRetriever.build_constellation()`:

```python
constellation = self.cognitive_retriever.build_constellation(
    candidates=scored_candidates,
    query=query_analysis,
)
```

**D2. Return constellation format from elefante-MemorySearch**

In `server.py`, the `elefante-MemorySearch` handler currently builds a flat results dict. Change it to return the constellation format when `limit > 1`:

```json
{
  "primary": {"id": "...", "title": "...", "score": 0.87, "role": "primary"},
  "supporting": [...],
  "contradicting": [...],
  "context": [...],
  "synthesis": "Primary: [X] | Supported by: [Y] | Note: conflict in [Z]"
}
```

This is the **core user-visible gain**. Instead of a flat list of raw memory blobs (500 tokens each, 90% nulls), the agent sees a curated, structured answer with explicit relationships.

**D3. Keep backward compatibility**

Add a `format` parameter to `elefante-MemorySearch`:
```python
"format": {"type": "string", "enum": ["flat", "constellation"], "default": "constellation"}
```

---

### PHASE E: TRIM RESPONSE BLOAT

**Known issue** from roadmap: `elefante-MemorySearch` returns ~500 tokens per memory result (90% null fields).

**E1. Define a SearchResultSummary model**

In `src/models/query.py`, add a compact result format:
```python
class SearchResultSummary(BaseModel):
    id: str
    title: str
    summary: str
    content: str                    # truncated to 200 chars
    score: float
    memory_type: str
    ring: Optional[str]
    knowledge_type: Optional[str]
    topic: Optional[str]
    tags: List[str]
    explanation: Optional[Dict]    # Why it surfaced (V5 Req-1)
```

**E2. Use SearchResultSummary in MCP response**

In `server.py` `elefante-MemorySearch` handler, serialize results using `SearchResultSummary` instead of `Memory.to_dict()`. Full memory content available via a separate lookup if needed.

**Target**: Reduce from ~500 tokens per result to ~80 tokens per result. With top 5 results, that's 2500 → 400 tokens.

---

### PHASE F: BUILD CO-ACTIVATION

Co-activation (15% weight in CognitiveRetriever) is permanently 0. This is fixable without architectural changes.

**F1. Add co-activation tracking to orchestrator**

In `orchestrator.search_memories()`, after returning results, record the session of co-retrieved memories:
```python
# After scoring, track co-activations for future queries
retrieved_ids = [str(r.memory.id) for r in results[:5]]
for mem_id in retrieved_ids:
    for other_id in retrieved_ids:
        if mem_id != other_id:
            # Increment co-activation count in-memory or ChromaDB custom_metadata
            pass
```

The simplest storage approach: update `custom_metadata["coactivation_counts"]` as a JSON dict `{other_id: count}` on each memory.

**F2. Load co-activation matrix into CognitiveRetriever at query time**

Before calling `score_candidate()`, build the co-activation matrix from recent search session context (pass last 5-10 retrieved IDs from the current session).

---

### PHASE G: WIRE PROACTIVE SURFACING

**G1. Invoke ProactiveSurfacer in elefante-ContextGet**

`ProactiveSurfacer.get_proactive_surfaces()` takes a current context string and returns memories that SHOULD surface. Wire it in `elefante-ContextGet`:

```python
surfacer = ProactiveSurfacer()
proactive = surfacer.get_proactive_surfaces(
    memories=memory_dicts,
    current_context=session_query_or_recent_messages,
    conversation_domain=inferred_domain,
    recent_concepts=recent_query_concepts,
)
if proactive:
    context["proactive_surfaces"] = [
        {"title": s.memory_title, "reason": s.reason, "confidence": s.confidence}
        for s in proactive
    ]
```

This surfaces relevant memories **without the user asking** — the core value proposition.

---

### PHASE H: UNIFY THE DISTILLER WITH V5

**H1. Map InsightType to V5 knowledge_type**

In `src/modules/distiller/ingester.py`, after distillation, enrich the memory metadata with V5 topology:

```python
INSIGHT_TYPE_TO_KNOWLEDGE_TYPE = {
    InsightType.RULE:         "law",
    InsightType.PREFERENCE:   "preference",
    InsightType.DECISION:     "decision",
    InsightType.PATTERN:      "method",
    InsightType.FACT:         "fact",
    InsightType.RELATIONSHIP: "insight",
    InsightType.WARNING:      "law",
}
```

Pass as `metadata["knowledge_type"]` when calling `orchestrator.add_memory()`.

**H2. Retire importance(1-10) in Distiller output**

The `DistilledInsight.importance` (1-10 scale) is ignored by orchestrator. Remove it from `DistillationResult` to eliminate the V3 vestige. The orchestrator score starts at 50 and emerges from behavior — this is the right design.

---

### PHASE I: UNIFY THE TWO METADATA MODELS

**I1. Retire StandardizedMetadata**

`src/models/metadata.py` is a parallel model that diverges from `MemoryMetadata`. The `metadata_store` (SQLite fast path) uses it. 

Migrate `metadata_store.py` to use `MemoryMetadata` directly (or a proper projection of it). Remove `StandardizedMetadata`, `CoreMetadata`, `ContextMetadata`. Unify the `MemoryType` enum to the single definition in `memory.py`.

---

## 10. Implementation Priority Matrix

| Phase | Impact | Risk | Effort | Priority |
|-------|--------|------|--------|----------|
| A: Remove dead code | Medium (clarity) | Zero | Low | **START HERE** |
| B: V5 first-class fields | High (enables filtering) | Low | Medium | Immediate next |
| C: Auto-classification at ingestion | Very High | Low | Medium | **Core gain** |
| D: Wire constellation | Very High (UX) | Medium | Medium | **Core gain** |
| E: Trim response bloat | High (token efficiency) | Low | Low | Quick win |
| F: Co-activation tracking | Medium (scoring quality) | Low | Medium | After B/C |
| G: Proactive surfacing | Very High (vision) | Medium | Low | After C |
| H: Unify distiller | Medium (consistency) | Low | Low | After C |
| I: Unify metadata models | Medium (maintenance) | Medium | High | Last |

---

## 11. Invariants — What Must NOT Change

These are working, valuable, and should not be modified:

1. **Behavioral scoring (score 0-100)** — The single source of relevance truth. Every memory starts at 50, earns through access, decays through neglect. Do not add back any manual importance assignment.

2. **memory_class (fact/directive/state)** — The contradiction branching logic in `orchestrator.add_memory()` STEP 2 is correct and valuable. Directives (user preferences) coexist; facts supersede. This is non-trivial to get right.

3. **Compliance Gate** — Search-before-write enforcement. Do not remove or weaken.

4. **two-DB architecture** — ChromaDB for semantic similarity, Kuzu for structured relationships. Both are necessary. Do not collapse to one.

5. **TYPE_DECAY_RATES** — Different memory types decay at different rates. This is the correct design for context hygiene.

6. **Auto context injection** — The `_inject_context()` mechanism that auto-surfaces top 3 memories on every tool call is valuable ambient memory recall.

7. **Elefante Mode locking** — The file-based lock for multi-IDE safety. Do not remove.

---

## 12. The Single Metric for Success

After implementing phases A through E, run this verification:

```python
# Store a preference memory
orchestrator.add_memory(
    "I always use black formatter for Python projects. Never configure it differently.",
    memory_type="preference"
)

# Verify V5 topology was auto-classified
assert memory.metadata.ring == "domain"
assert memory.metadata.knowledge_type in ("law", "preference")  
assert memory.metadata.topic == "coding-standards"

# Search for it
results = orchestrator.search_memories("Python code formatting rules")

# Verify constellation format
assert results["primary"]["title"] is not None
assert results["primary"]["score"] > 0.5
assert len(results["synthesis"]) > 0
```

If this passes, the cohesive vision is operational: memories classify themselves, surface in the right context, and narrate their own relevance.

---

## 13. What This Achieves for the User

Before (current state):
- Store memory → gets `processing_status=raw`, V5 fields empty
- Search → flat list of raw JSON blobs, 500 tokens each, no structure
- Context injection → works but silent

After (with all phases):
- Store memory → **automatically** gets `ring/knowledge_type/topic` populated, named correctly
- Search → **constellation** with primary, supporting, contradicting, context + synthesis sentence
- Context injection → **proactive** suggestions appear when relevant, before you ask

The user never says "you already know this" because the system tells you what it knows, organized, with confidence, at the exact moment of relevance.

---

*"The value isn't in what you store — it's in what you retrieve at the moment of need."*
