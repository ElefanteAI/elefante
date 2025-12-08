# Memory System Debug Compendium

> **Domain:** Memory Retrieval, Storage & Reinforcement  
> **Last Updated:** 2025-12-07  
> **Total Issues Documented:** 6  
> **Status:** Production Reference  
> **Maintainer:** Add new issues following Issue #N template at bottom

---

## 🚨 CRITICAL LAWS (Extracted from Pain)

| #   | Law                                                                        | Violation Cost    |
| --- | -------------------------------------------------------------------------- | ----------------- |
| 1   | Use `min_similarity=0` to get ALL memories                                 | Partial exports   |
| 2   | ChromaDB stores memories, Kuzu stores entities - DIFFERENT                 | Data confusion    |
| 3   | Use `collection.get()` for complete export, not `searchMemories`           | Missing data      |
| 4   | Search Elefante BEFORE implementing, not after                             | Repeated mistakes |
| 5   | Verify code works BEFORE claiming completion                               | User frustration  |
| 6   | Memory metadata has 40+ fields - don't assume structure                    | Silent data loss  |
| 7   | V3 Schema: layer/sublayer must be saved in BOTH add_memory AND reconstruct | 8 hours           |

---

## Table of Contents

- [Issue #1: Partial Memory Export](#issue-1-partial-memory-export)
- [Issue #2: Wrong Data Store Queried](#issue-2-wrong-data-store-queried)
- [Issue #3: Memory Not Used for Decision Making](#issue-3-memory-not-used-for-decision-making)
- [Issue #4: Temporal Decay Implementation Failure](#issue-4-temporal-decay-implementation-failure)
- [Issue #5: Memory Schema Mismatch](#issue-5-memory-schema-mismatch)
- [Issue #6: V3 Layer Metadata Not Persisting](#issue-6-v3-layer-metadata-not-persisting)
- [Memory Export Guide](#memory-export-guide)
- [Reinforcement Protocol](#reinforcement-protocol)
- [Prevention Protocol](#prevention-protocol)
- [Appendix: Issue Template](#appendix-issue-template)

---

## Issue #1: Partial Memory Export

**Date:** 2025-12-05  
**Duration:** Recurring problem  
**Severity:** HIGH  
**Status:** ✅ DOCUMENTED

### Problem

Attempts to export "all memories" return only a subset (3-10 instead of 71).

### Symptom

```python
# User expects 71 memories
result = searchMemories("all memories", limit=1000)
# Returns only 3-10 memories
```

### Root Cause

`searchMemories` uses **semantic similarity filtering**:

- Default `min_similarity=0.3`
- Query "all memories" only matches memories semantically similar to that phrase
- Most memories have similarity < 0.3 to "all memories"

### Solution

```python
# ✅ CORRECT: Use min_similarity=0 to disable filtering
result = await mcp_client.call_tool("searchMemories", {
    "query": "*",
    "limit": 1000,
    "min_similarity": 0.0  # CRITICAL: Disable filtering!
})

# ✅ BEST: Direct ChromaDB access
collection = vector_store._collection
results = collection.get(include=["metadatas", "documents"])
```

### Why This Keeps Happening

- `searchMemories` name implies "find memories" not "filter memories"
- Default min_similarity not obvious
- API designed for relevance, not completeness

### Lesson

> **Semantic search ≠ List all. Use `collection.get()` for complete export.**

---

## Issue #2: Wrong Data Store Queried

**Date:** 2025-12-05  
**Duration:** 2 hours  
**Severity:** CRITICAL  
**Status:** ✅ FIXED

### Problem

Dashboard/export code queried Kuzu instead of ChromaDB, returning entities instead of memories.

### Symptom

```
Expected: 71 memories
Got: 17 entities
```

### Root Cause

Confusion between data stores:

| Store    | Contains | Count | Purpose                          |
| -------- | -------- | ----- | -------------------------------- |
| ChromaDB | Memories | 71    | Semantic search, content storage |
| Kuzu     | Entities | 17    | Graph relationships, concepts    |

Code was doing:

```python
# ❌ WRONG
query = "MATCH (e:Entity) RETURN e"  # Returns entities, NOT memories
```

### Solution

```python
# ✅ CORRECT
collection = vector_store._collection
results = collection.get(include=["metadatas", "documents"])
```

### Why This Happened

- Both stores are "databases" in the system
- Entity extraction creates Kuzu entries from memories
- Easy to confuse "17 entities" with "17 memories"

### Lesson

> **ChromaDB = memories (user content). Kuzu = entities (extracted concepts).**

---

## Issue #3: Memory Not Used for Decision Making

**Date:** 2025-12-03  
**Duration:** Systemic issue  
**Severity:** CRITICAL  
**Status:** ⚠️ DOCUMENTED (Behavioral)

### Problem

AI has Elefante access but treats it as storage, not decision support.

### Symptom

- Repeated mistakes that are documented in memory
- "I should have checked Elefante first"
- User frustration: "Why do you keep making the same mistake?"

### Root Cause

**Wrong Mental Model:**

```
Current: Task → Implement → Store lessons (POST-HOC)
Correct: Task → Search Elefante → Implement with context → Update
```

### Solution

**The 5-Phase Reinforcement Protocol:**

```
Phase 1: PRE-TASK SEARCH (MANDATORY)
├── searchMemories("verification checklist for {task}")
├── searchMemories("common mistakes when {task}")
├── searchMemories("user preferences for {task}")
└── searchMemories("lessons learned from {similar task}")

Phase 2: DURING IMPLEMENTATION
├── searchMemories("how to implement {feature}")
├── searchMemories("known issues with {technology}")
└── Periodically re-check relevant memories

Phase 3: PRE-COMPLETION SEARCH (MANDATORY)
├── searchMemories("verification steps for {task}")
├── searchMemories("testing requirements")
└── searchMemories("definition of done")

Phase 4: POST-COMPLETION DOCUMENTATION
├── addMemory("What worked: {approach}")
├── addMemory("Challenges overcome: {problems}")
└── addMemory("Lessons learned: {insights}")

Phase 5: REINFORCEMENT
└── Update importance of memories that prevented mistakes
```

### Why This Pattern Persists

- Easier to implement than to research
- Time pressure favors action over preparation
- Memory system feels like "extra step"

### Lesson

> **Elefante should be the FIRST tool, not the last resort.**

---

## Issue #4: Temporal Decay Implementation Failure

**Date:** 2025-12-03  
**Duration:** 4 hours  
**Severity:** CRITICAL  
**Status:** ✅ FIXED

### Problem

Claimed temporal decay was "ready" without verification, discovered critical errors.

### Symptom

```python
# Code claimed complete, but:
# - Had merge conflict markers in source
# - Missing dependency (aiosqlite)
# - Invalid enum values from LLM output
```

### Root Cause

**Premature completion claims.** Specific failures:

1. **Merge conflict markers not detected:**

   ```python
   <<<<<<< HEAD
   old_code()
   =======
   new_code()
   >>>>>>> branch
   ```

2. **Import not tested:**

   ```python
   # Never ran:
   python -c "from src.core.orchestrator import MemoryOrchestrator"
   ```

3. **LLM output not validated:**
   ```python
   # LLM returned: "REFERENCE_INFO"
   # Enum expected: "REFERENCE"
   intent_value = IntentType(intent)  # ValueError!
   ```

### Solution

**Verification Checklist (MANDATORY before claiming done):**

```bash
# Phase 1: Syntax & Structure
grep -r "<<<<<<< HEAD" src/  # No merge conflicts
python -m py_compile src/**/*.py  # Valid syntax

# Phase 2: Dependencies
pip install -r requirements.txt
python -c "from src.core.orchestrator import MemoryOrchestrator"

# Phase 3: Functionality
python -c "
from src.core.orchestrator import MemoryOrchestrator
orchestrator = MemoryOrchestrator()
results = orchestrator.search_memories('test', limit=5)
print(f'Found {len(results)} results')
"

# Phase 4: Real Data
# Test with user's actual memories
```

### Why This Took So Long

- Assumed "I wrote it, it works"
- Didn't run basic import test
- Ignored merge conflict possibility
- Trusted LLM output without validation

### Lesson

> **VERIFY, DON'T ASSUME. Code is not done until tests pass.**

---

## Issue #5: Memory Schema Mismatch

**Date:** 2025-12-04  
**Duration:** Documentation time  
**Severity:** MEDIUM  
**Status:** ⚠️ DOCUMENTED

### Problem

Memory model has 40+ fields but code often assumes simpler structure.

### Symptom

```python
# Code assumes:
memory.importance  # Direct attribute

# Reality:
memory["metadata"]["importance"]  # Nested in metadata dict
```

### Root Cause

ChromaDB stores everything in flat structure:

```python
{
    "id": "uuid",
    "document": "content text",
    "metadata": {  # ALL fields here
        "importance": 8,
        "domain": "technical",
        "created_at": "...",
        # ... 37 more fields
    }
}
```

### Solution

Always use model helpers:

```python
# ❌ WRONG: Direct access
importance = result["metadata"]["importance"]

# ✅ CORRECT: Use model class
memory = MemoryModel.from_chromadb_result(result)
importance = memory.importance
```

### Memory Metadata Fields (9 Categories)

| Category           | Fields                                                                        |
| ------------------ | ----------------------------------------------------------------------------- |
| **Core**           | id, content, created_at, created_by                                           |
| **Classification** | domain, category, memory_type, subcategory, intent                            |
| **Importance**     | importance (1-10), urgency, confidence                                        |
| **Relationship**   | relationship_type, parent_id, related_memory_ids, conflict_ids, supersedes_id |
| **Temporal**       | last_accessed, last_modified, access_count, decay_rate, reinforcement_factor  |
| **Source**         | source, source_detail, source_reliability, verified, verified_by              |
| **Context**        | session_id, author, project, workspace, file_path, line_number, url           |
| **Lifecycle**      | version, deprecated, archived, status                                         |
| **Extensibility**  | tags, keywords, entities, summary, sentiment, quality_score                   |

### Lesson

> **Always use model classes for data translation. Never assume field structure.**

---

## Issue #6: V3 Layer Metadata Not Persisting

**Date:** 2025-12-07  
**Duration:** 8+ hours (shared with dashboard debugging)  
**Severity:** CRITICAL  
**Status:** ✅ FIXED

### Problem

V3 Schema fields (`layer`, `sublayer`) not persisting through memory lifecycle despite being set by classifier.

### Symptom

```python
# Classifier correctly returns:
classify_memory("I am a developer") → ("self", "identity")

# But ChromaDB shows:
metadata["layer"] → "world"  # Wrong!
metadata["sublayer"] → "fact"  # Wrong!
```

### Root Cause

**Two missing field mappings:**

1. **VectorStore.add_memory()** - metadata dict construction missed layer/sublayer:

```python
# ❌ BEFORE: Fields not in dict
metadata = {
    "domain": memory.metadata.domain,
    "category": memory.metadata.category,
    # layer/sublayer MISSING!
}

# ✅ AFTER: Added explicitly
metadata = {
    "layer": memory.metadata.layer,
    "sublayer": memory.metadata.sublayer,
    # ... other fields
}
```

2. **VectorStore.\_reconstruct_memory()** - reconstruction didn't read layer/sublayer:

```python
# ❌ BEFORE: Not reading from metadata
MemoryMetadata(
    domain=metadata.get("domain"),
    # layer/sublayer MISSING!
)

# ✅ AFTER: Reading back
MemoryMetadata(
    layer=metadata.get("layer", "world"),
    sublayer=metadata.get("sublayer", "fact"),
)
```

### Solution

1. **Added layer/sublayer to add_memory()** metadata dict (lines 123-128)
2. **Added layer/sublayer to \_reconstruct_memory()** constructor (lines 362-367)
3. **Created standalone migration script** `scripts/migrate_v3_direct.py` to bypass MCP cache
4. **Expanded classifier.py** with 20+ regex patterns and `calculate_importance()` function

### Why This Took So Long

- **Migration tool lied**: Reported "78 migrated, 0 errors" but data unchanged (used cached code)
- **Assumption**: Assumed if field was in `Memory.metadata`, it would be saved automatically
- **No roundtrip test**: Never verified `add_memory()` → `get_memory()` preserved fields

### Lesson

> **Every metadata field must be explicitly mapped in BOTH add_memory (write) AND \_reconstruct_memory (read). Test roundtrip preservation.**

### V3 Schema Reference

| Layer    | Sublayers                        | Meaning             |
| -------- | -------------------------------- | ------------------- |
| `self`   | identity, preference, constraint | Who the user IS     |
| `world`  | fact, failure, method            | What the user KNOWS |
| `intent` | rule, goal, anti-pattern         | What the user DOES  |

---

## Memory Export Guide

### ✅ DO: Complete Memory Export

```python
# Method 1: Direct ChromaDB Access (RECOMMENDED)
from src.core.vector_store import VectorStore

vector_store = VectorStore()
collection = vector_store._collection
results = collection.get(include=["metadatas", "documents", "embeddings"])

memories = []
for i, doc_id in enumerate(results["ids"]):
    memories.append({
        "id": doc_id,
        "content": results["documents"][i],
        "metadata": results["metadatas"][i],
    })

print(f"Exported {len(memories)} memories")  # Should be 71
```

```python
# Method 2: MCP with min_similarity=0
result = await mcp_client.call_tool("searchMemories", {
    "query": "*",
    "limit": 1000,
    "min_similarity": 0.0  # CRITICAL!
})
```

### ❌ DON'T: Common Export Mistakes

```python
# ❌ Using searchMemories with default min_similarity
searchMemories("all memories")  # Returns ~3-10, not 71

# ❌ Querying Kuzu instead of ChromaDB
"MATCH (e:Entity) RETURN e"  # Returns 17 entities, not 71 memories

# ❌ Using dashboard snapshot
json.load(open("data/dashboard_snapshot.json"))  # May be stale
```

---

## Reinforcement Protocol

### Before ANY Task

```python
# Mandatory pre-task queries:
queries = [
    f"verification checklist for {task_type}",
    f"common mistakes when {task_type}",
    f"lessons learned from similar tasks",
    f"user preferences for {project}",
]

for q in queries:
    results = searchMemories(q, min_similarity=0.2)
    if results:
        print(f"Found guidance: {results}")
```

### During Implementation

```python
# Periodic checks:
if stuck_for_more_than_5_minutes:
    searchMemories(f"troubleshooting {current_error}")
    searchMemories(f"workarounds for {technology}")
```

### Before Claiming Done

```python
# MANDATORY verification:
verification_queries = [
    "verification steps before claiming completion",
    f"testing requirements for {feature}",
    "what to check before saying done",
]

for q in verification_queries:
    guidance = searchMemories(q)
    # FOLLOW the guidance
```

---

## Prevention Protocol

### Memory System Checklist

```bash
# Daily health check
python -c "
from src.core.vector_store import VectorStore
vs = VectorStore()
count = vs._collection.count()
print(f'Memory count: {count}')
assert count > 0, 'No memories found!'
"
```

### When Memory Search Returns Few Results

1. Check `min_similarity` parameter (should be 0 for complete results)
2. Verify querying ChromaDB, not Kuzu
3. Try direct `collection.get()` to bypass search
4. Check if memories actually exist: `collection.count()`

### When Adding New Memories

1. Verify memory was stored: search by exact content
2. Check metadata was preserved: inspect returned object
3. Test retrieval: search with related terms

---

## Appendix: Issue Template

```markdown
## Issue #N: [Short Descriptive Title]

**Date:** YYYY-MM-DD  
**Duration:** X hours/minutes  
**Severity:** LOW | MEDIUM | HIGH | CRITICAL  
**Status:** 🔴 OPEN | 🟡 IN PROGRESS | ✅ FIXED | ⚠️ DOCUMENTED

### Problem

[One sentence: what is broken]

### Symptom

[What the user sees / exact error message]

### Root Cause

[Technical explanation of WHY it broke]

### Solution

[Code changes or steps that fixed it]

### Why This Took So Long

[Honest reflection on methodology mistakes]

### Lesson

> [One-line takeaway in blockquote format]
```

---

_Last verified: 2025-12-05 | Memory count: 71 | ChromaDB version: check requirements.txt_
