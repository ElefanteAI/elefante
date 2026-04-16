# Memory System Debug Compendium

> **Domain:** Memory Retrieval, Storage & Reinforcement
> **Last Updated:** 2026-04-15
> **Total Issues Documented:** 13
> **Status:** Production Reference - All Scoring Flaws Fixed (v2.7.0)
> **Applies to**: v2.9.0+
> **Maintainer:** Add new issues following Issue #N template at bottom
>
> **HISTORICAL NOTE:** Some issues below reference V3 concepts (layer, sublayer, classifier.py, IntentType, importance 1-10) that have since been removed. These entries document the debugging process and lessons learned; the referenced code/fields no longer exist.

---

## CRITICAL LAWS (Extracted from Pain)

| #   | Law                                                                           | Violation Cost    |
| --- | ----------------------------------------------------------------------------- | ----------------- |
| 1   | Use `min_similarity=0` to get ALL memories                                    | Partial exports   |
| 2   | ChromaDB stores memories, Kuzu stores entities - DIFFERENT                    | Data confusion    |
| 3   | Use `collection.get()` for complete export, not `elefante-MemorySearch`       | Missing data      |
| 4   | Search Elefante BEFORE implementing, not after                                | Repeated mistakes |
| 5   | Verify code works BEFORE claiming completion                                  | User frustration  |
| 6   | Memory metadata has 40+ fields - don't assume structure                       | Silent data loss  |
| 7   | V3 Schema: layer/sublayer must be saved in BOTH add_memory AND reconstruct    | 8 hours           |
| 8   | **elefante-MemorySearch returns BLOATED JSON - 90% null fields waste tokens** | Context window    |
| 9   | **Similarity scores 0.3-0.4 for exact matches = embedding quality issue**     | Poor retrieval    |
| 10  | **Trace write→read value spaces for every scored signal before trusting it**  | Phantom signals   |
| 11  | **Global score overrides must be intent-gated, not unconditional**            | Ranking monopoly  |
| 12  | **MCP response lacks actionable summary - agent must parse raw JSON**         | Integration fail  |

---

## Verification Commands

Run these BEFORE investigating. If tests pass, the documented fix is intact.

| Issue | Test Command | What It Proves |
| ----- | ------------ | -------------- |
| #1-#3 Memory retrieval | `pytest tests/test_memory_persistence.py -v` | Persistence, path resolution, scoring |
| #7 Response bloat | `pytest tests/test_integration_smoke.py -v` | Full ADD/SEARCH cycle with 10 scenarios |
| #8 Low similarity | `pytest tests/test_scoring.py -v` | Score normalization and weight math |
| Memory guard | `pytest tests/test_memory_guard.py -v` | Test-tagged memories blocked by default |
| #10 Silent IGNORE | `pytest tests/test_memory_guard.py -v` | Guard blocks test-like memories; response must include rejection reason |
| Full E2E | `.venv/bin/python scripts/verify/verify_e2e_tests.py` | Isolated end-to-end MCP workflow |

---

## Table of Contents

- [Issue #1: Partial Memory Export](#issue-1-partial-memory-export)
- [Issue #2: Wrong Data Store Queried](#issue-2-wrong-data-store-queried)
- [Issue #3: Memory Not Used for Decision Making](#issue-3-memory-not-used-for-decision-making)
- [Issue #4: Temporal Decay Implementation Failure](#issue-4-temporal-decay-implementation-failure)
- [Issue #5: Memory Schema Mismatch](#issue-5-memory-schema-mismatch)
- [Issue #6: V3 Layer Metadata Not Persisting](#issue-6-v3-layer-metadata-not-persisting)
- [Issue #7: elefante-MemorySearch Response Bloat](#issue-7-elefantememorysearch-response-bloat-token-waste) FIXED
- [Issue #8: Low Similarity Scores](#issue-8-low-similarity-scores-for-exact-matches) FIXED
- [Issue #9: No Actionable Integration](#issue-9-no-actionable-integration-in-search-results) FIXED
- [Issue #10: MemoryAdd Silent IGNORE](#issue-10-memoryadd-silent-ignore--opaque-test-memory-guard-rejection) OPEN
- [Memory Export Guide](#memory-export-guide)
- [Reinforcement Protocol](#reinforcement-protocol)
- [Prevention Protocol](#prevention-protocol)
- [Appendix: Issue Template](#appendix-issue-template)

---

## Issue #1: Partial Memory Export

**Date:** 2025-12-05  
**Duration:** Recurring problem  
**Severity:** HIGH  
**Status:** DOCUMENTED

### Problem

Attempts to export "all memories" return only a subset (3-10 instead of 71).

### Symptom

```python
# User expects 71 memories
result = elefante-MemorySearch("all memories", limit=1000)
# Returns only 3-10 memories
```

### Root Cause

`elefante-MemorySearch` uses **semantic similarity filtering**:

- Default `min_similarity=0.3`
- Query "all memories" only matches memories semantically similar to that phrase
- Most memories have similarity < 0.3 to "all memories"

### Solution

```python
#  CORRECT: Use min_similarity=0 to disable filtering
result = await mcp_client.call_tool("elefante-MemorySearch", {
    "query": "*",
    "limit": 1000,
    "min_similarity": 0.0  # CRITICAL: Disable filtering!
})

#  BEST: Direct ChromaDB access
collection = vector_store._collection
results = collection.get(include=["metadatas", "documents"])
```

### Why This Keeps Happening

- `elefante-MemorySearch` name implies "find memories" not "filter memories"
- Default min_similarity not obvious
- API designed for relevance, not completeness

### Lesson

> **Semantic search ≠ List all. Use `collection.get()` for complete export.**

---

## Issue #2: Wrong Data Store Queried

**Date:** 2025-12-05  
**Duration:** 2 hours  
**Severity:** CRITICAL  
**Status:** FIXED

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
#  WRONG
query = "MATCH (e:Entity) RETURN e"  # Returns entities, NOT memories
```

### Solution

```python
#  CORRECT
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
**Status:** DOCUMENTED (Behavioral)

### Problem

AI has Elefante access but treats it as storage, not decision support.

### Symptom

- Repeated mistakes that are documented in memory
- "I should have checked Elefante first"
- User frustration: "Why do you keep making the same mistake?"

### Root Cause

**Wrong Mental Model:**

```
Current: Task -> Implement -> Store lessons (POST-HOC)
Correct: Task -> Search Elefante -> Implement with context -> Update
```

### Solution

**The 5-Phase Reinforcement Protocol:**

```
Phase 1: PRE-TASK SEARCH (MANDATORY)
├── elefante-MemorySearch("verification checklist for {task}")
├── elefante-MemorySearch("common mistakes when {task}")
├── elefante-MemorySearch("user preferences for {task}")
└── elefante-MemorySearch("lessons learned from {similar task}")

Phase 2: DURING IMPLEMENTATION
├── elefante-MemorySearch("how to implement {feature}")
├── elefante-MemorySearch("known issues with {technology}")
└── Periodically re-check relevant memories

Phase 3: PRE-COMPLETION SEARCH (MANDATORY)
├── elefante-MemorySearch("verification steps for {task}")
├── elefante-MemorySearch("testing requirements")
└── elefante-MemorySearch("definition of done")

Phase 4: POST-COMPLETION DOCUMENTATION
├── elefante-MemoryAdd("What worked: {approach}")
├── elefante-MemoryAdd("Challenges overcome: {problems}")
└── elefante-MemoryAdd("Lessons learned: {insights}")

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
**Status:** FIXED

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
**Status:** DOCUMENTED

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
#  WRONG: Direct access
importance = result["metadata"]["importance"]

#  CORRECT: Use model class
memory = MemoryModel.from_chromadb_result(result)
importance = memory.importance
```

### Memory Metadata Fields (9 Categories)

| Category           | Fields                                                                        |
| ------------------ | ----------------------------------------------------------------------------- |
| **Core**           | id, content, created_at, created_by                                           |
| **Classification** | domain, category, memory_type, subcategory, intent                            |
| **Importance**     | relevance_score (0-100, system-computed), urgency, confidence                 |
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
**Status:** FIXED

### Problem

V3 Schema fields (`layer`, `sublayer`) not persisting through memory lifecycle despite being set by classifier.

### Symptom

```python
# Classifier correctly returns:
classify_memory("I am a developer") -> ("self", "identity")

# But ChromaDB shows:
metadata["layer"] -> "world"  # Wrong!
metadata["sublayer"] -> "fact"  # Wrong!
```

### Root Cause

**Two missing field mappings:**

1. **VectorStore.add_memory()** - metadata dict construction missed layer/sublayer:

```python
#  BEFORE: Fields not in dict
metadata = {
    "domain": memory.metadata.domain,
    "category": memory.metadata.category,
    # layer/sublayer MISSING!
}

#  AFTER: Added explicitly
metadata = {
    "layer": memory.metadata.layer,
    "sublayer": memory.metadata.sublayer,
    # ... other fields
}
```

2. **VectorStore.\_reconstruct_memory()** - reconstruction didn't read layer/sublayer:

```python
#  BEFORE: Not reading from metadata
MemoryMetadata(
    domain=metadata.get("domain"),
    # layer/sublayer MISSING!
)

#  AFTER: Reading back
MemoryMetadata(
    layer=metadata.get("layer", "world"),
    sublayer=metadata.get("sublayer", "fact"),
)
```

### Solution

1. **Added layer/sublayer to add_memory()** metadata dict (lines 123-128)
2. **Added layer/sublayer to \_reconstruct_memory()** constructor (lines 362-367)
3. **Created standalone migration script** `scripts/migrate_memories_v3_direct.py` to bypass MCP cache
4. **Expanded classifier.py** with 20+ regex patterns and `calculate_importance()` function

### Why This Took So Long

- **Migration tool lied**: Reported "78 migrated, 0 errors" but data unchanged (used cached code)
- **Assumption**: Assumed if field was in `Memory.metadata`, it would be saved automatically
- **No roundtrip test**: Never verified `add_memory()` -> `get_memory()` preserved fields

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

### DO: Complete Memory Export

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
result = await mcp_client.call_tool("elefante-MemorySearch", {
    "query": "*",
    "limit": 1000,
    "min_similarity": 0.0  # CRITICAL!
})
```

### DON'T: Common Export Mistakes

```python
#  Using elefante-MemorySearch with default min_similarity
elefante-MemorySearch("all memories")  # Returns ~3-10, not 71

#  Querying Kuzu instead of ChromaDB
"MATCH (e:Entity) RETURN e"  # Returns 17 entities, not 71 memories

#  Using dashboard snapshot
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
  results = elefante-MemorySearch(q, min_similarity=0.2)
    if results:
        print(f"Found guidance: {results}")
```

### During Implementation

```python
# Periodic checks:
if stuck_for_more_than_5_minutes:
  elefante-MemorySearch(f"troubleshooting {current_error}")
  elefante-MemorySearch(f"workarounds for {technology}")
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
  guidance = elefante-MemorySearch(q)
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

## Issue #7: elefante-MemorySearch Response Bloat (Token Waste)

**Date:** 2025-12-10  
**Duration:** Observed in production testing  
**Severity:** CRITICAL  
**Status:** FIXED

### Problem

elefante-MemorySearch returns ~500 tokens of metadata per memory, 90% of which is null/default values.

### Symptom

```json
// Query: "Developer Etiquette Standards"
// Response per memory (~500 tokens EACH):
{
  "memory": {
    "id": "d6636cc1-...",
    "content": "Actual useful content here",
    "metadata": {
      "created_at": "2025-12-10",
      "subcategory": null, // WASTED
      "verified": false, // WASTED
      "verified_by": null, // WASTED
      "verified_at": null, // WASTED
      "session_id": null, // WASTED
      "project": null, // WASTED
      "workspace": null, // WASTED
      "file_path": null, // WASTED
      "line_number": null, // WASTED
      "url": null, // WASTED
      "location": null // WASTED
      // ... 30+ more null fields
    }
  }
}
```

**Token math:** 3 memories × 500 tokens = 1500 tokens. Useful content: ~150 tokens. **90% waste.**

### Root Cause

1. Memory model has 60+ fields for extensibility
2. MCP tool serializes ENTIRE metadata dict including nulls
3. No response filtering or compression
4. No "slim" response mode

### Solution (IMPLEMENTED - v2.1.2)

**Mathematical Null Stripping in MCP Response Payload:**

```python
# In src/mcp/server.py _handle_search_memories
def strip_nulls(data):
    if isinstance(data, dict):
        return {k: strip_nulls(v) for k, v in data.items()
                if v is not None and v != [] and v != {}}
    elif isinstance(data, list):
        return [strip_nulls(item) for item in data if item is not None]
    return data

# Applied recursively to every SearchResult before returning to LLM
```

### Why This Matters

- Agent context window is FINITE
- Every wasted token = less room for actual work
- 3 memories already consume 1500+ tokens
- At scale (10+ memories), search results dominate context

### Lesson

> **Every null field in MCP response is a stolen token. Filter aggressively.**

---

## Issue #8: Low Similarity Scores for Exact Matches

**Date:** 2025-12-10  
**Duration:** Observed in production testing  
**Severity:** HIGH  
**Status:** FIXED (v2.1.2)

### Problem

Query for "Developer Etiquette Standards" returns memories ABOUT developer etiquette with only 0.37-0.39 similarity scores.

### Symptom

```python
# Query: "Developer Etiquette Standards Project Hydro Documentation"
# Results:
# Memory 1: "ELEFANTE_DEVELOPER_CORE_V4 Agent Etiquette..." -> similarity: 0.392
# Memory 2: "Collaboration Rules: Bus Factor..." -> similarity: 0.377
# Memory 3: "Technical Best Practices Checklist..." -> similarity: 0.377

# Expected: 0.7+ for topic-relevant memories
# Actual: 0.37-0.39 (barely above default min_similarity of 0.3!)
```

### Root Cause

**Possible causes (need investigation):**

1. **Embedding model mismatch**: all-MiniLM-L6-v2 may not capture domain terminology
2. **Query too long**: Multi-word queries dilute embedding focus
3. **Content structure**: Long markdown content embeds poorly vs short queries
4. **No query expansion**: System doesn't try synonyms or related terms

### Solution (IMPLEMENTED - v2.1.2)

**Smoothed Vector Baseline in Cognitive Retriever:**

The root cause was NOT the embedding model (`sentence-transformers/gte-base` returns `0.85+` for exact matches). The bug was the **V4 Cognitive Multi-Signal Scoring** algorithm. If a document lacked metadata (like `concepts` or `surfaces_when`), the formula brutally multiplied those missing signals by their weights (e.g., `0.20 * 0.0`), chemically suppressing the raw vector match down to `0.39`.

**The Fix:** We established the semantic vector score as the mathematical floor. Heuristics can only boost relevance, never destroy semantic ground truth.

```python
# In src/core/retrieval.py (score_candidate)
vector_baseline = candidate.vector_score * 0.85
if candidate.composite_score < vector_baseline:
    candidate.composite_score = vector_baseline
```

### Why This Matters

- Memories exist but aren't found reliably
- Agent may miss critical guidance
- Default min_similarity=0.3 barely catches relevant results
- System feels "dumb" despite having knowledge

### Lesson

> **Similarity 0.3-0.4 for exact topic match = retrieval is broken. Investigate embedding quality.**

---

## Issue #9: No Actionable Integration in Search Results

**Date:** 2025-12-10  
**Duration:** Observed in production testing  
**Severity:** HIGH  
**Status:** FIXED (v2.1.2)

### Problem

elefante-MemorySearch returns raw JSON that agent must parse and interpret. No guidance on WHAT TO DO with results.

### Symptom

```
Agent receives:
{
  "success": true,
  "count": 3,
  "results": [{ huge json }, { huge json }, { huge json }]
}

Agent must then:
1. Parse JSON
2. Extract content from each memory
3. Identify which memories are relevant
4. Determine how to apply them
5. Actually apply them (often forgotten!)
```

### Root Cause

MCP tool designed as "data retrieval" not "decision support":

- Returns data, not guidance
- No summary of findings
- No suggested actions
- No conflict detection between memories

### Solution (IMPLEMENTED - v2.1.2)

**Hardcoded Actionable Directive Header:**

We inject a loud, unmissable `suggested_action` header at the very top of every returned search payload. This acts as an inescapable system prompt that forces the LLM to process and obey the rules it just retrieved.

```json
{
  "suggested_action": "CRITICAL DIRECTIVE: You have retrieved constraints from the user's permanent memory. You MUST format your response and execute your actions in strict compliance with the rules and parameters defined in these memories.",
  "results": [...]
}
```

    {
      "memory_a": "uuid-1",
      "memory_b": "uuid-2",
      "conflict_type": "contradictory_rules",
      "resolution": "Memory A is more recent, prefer it"
    }

]
}

````

**Option 3: Agent-friendly format**

```json
{
  "for_agent": {
    "key_facts": ["Fact 1", "Fact 2"],
    "rules_to_follow": ["Rule 1", "Rule 2"],
    "warnings": ["Don't do X"],
    "apply_to": "current task context"
  }
}
````

### Why This Matters

- Agent retrieves knowledge but doesn't USE it
- "Knowledge Gap" vs "Application Gap" - this is Application Gap
- Raw data ≠ actionable intelligence
- Users frustrated: "You have the memory, why didn't you follow it?"

### Lesson

> **Data retrieval without action guidance = useless. Memory system must DIRECT agent behavior.**

---

## Issue #10: MemoryAdd Silent IGNORE -- Opaque Test-Memory Guard Rejection

**Date:** 2026-04-15  
**Duration:** 1 debugging cycle  
**Severity:** HIGH  
**Status:** OPEN

### Problem

`elefante-MemoryAdd` silently drops memories that match a broad "test-like" heuristic and returns only a generic `"Memory filtered by Intelligence Pipeline"` message with no indication of which condition triggered the rejection. The calling agent cannot diagnose or correct the input.

### Symptom

An agent calls MemoryAdd with legitimate diagnostic content and tags `["bug-010", "diagnostic", "test"]`:

```json
{
  "status": "ignored",
  "classification": "IGNORE",
  "entity_count": 0,
  "relationship_count": 0,
  "embedding_id": null,
  "graph_ids": [],
  "message": "Memory filtered by Intelligence Pipeline"
}
```

No field explains **why** the memory was filtered. The agent sees success-shaped JSON (no `error` field, no `isError` flag) with `status: ignored` but no actionable information. The same content without the `"test"` tag stores successfully.

During installation, this same guard silently blocked the seed passcode memory (logged as `blocked_test_memory_submission`) while the installer reported "Successfully injected seed memory" -- a false-positive success claim.

### Root Cause

The test-memory guard in `src/core/orchestrator.py` (lines ~207-241) applies 9 heuristic conditions that flag a memory as "test-like":

| Condition | Source |
|---|---|
| `namespace == "test"` | metadata |
| `category == "test"` | metadata |
| `category.startswith("hybrid_test_")` | metadata |
| `"test" in tags` | tags |
| `"e2e" in tags` | tags |
| any tag starts with `"hybrid_test_"` | tags |
| content starts with `"elefante e2e test memory"` | content |
| content starts with `"hybrid search test memory"` | content |
| `" test memory"` appears in content | content |

When any condition matches and `ELEFANTE_ALLOW_TEST_MEMORIES` is not set, the orchestrator returns `None`. The MCP server handler at `src/mcp/server.py` (lines ~1284-1294) translates this `None` into the generic IGNORE response.

**Two contract violations:**

1. **No rejection reason in the response.** The detailed reason (`blocked_test_memory_submission` with the matching tags) is only written to `self.logger.warning` on stderr -- invisible to the calling agent via the MCP tool response.

2. **Overly broad heuristic.** The word `"test"` in any tag matches legitimate use cases: "test passcode", "diagnostic test", "load test results", "A/B test findings". The guard was designed for E2E test isolation but its blast radius covers normal operational tags.

### Solution

**Pending.** The fix should:

1. **Include the rejection reason in the MCP response.** Add a `"rejection_reason"` field (e.g., `"tag 'test' matched test-memory guard"`) so the calling agent can correct and retry.
2. **Narrow the heuristic.** Replace the broad `"test" in tags` with more specific patterns that only match actual test-framework artifacts (e.g., `"e2e_test"`, `"pytest"`, `"test_fixture"`) rather than any tag containing the word "test".
3. **Fix the installer false-positive.** `scripts/setup/init_databases.py` should check the return value and not claim "Successfully injected seed memory" when the guard blocked it.

**Files to change:** `src/core/orchestrator.py`, `src/mcp/server.py`, `scripts/setup/init_databases.py`, `tests/test_memory_guard.py`

### Why This Took So Long

- The IGNORE response has no `error` field and no `isError` flag, so it superficially looks like a non-error result. An agent that doesn't read the `status` field carefully will assume the operation succeeded.
- The generic message "Memory filtered by Intelligence Pipeline" gives no hint that a specific tag was the trigger. The agent would need to guess which of the 9 conditions fired.
- The installer's false "Successfully injected seed memory" claim masked the guard rejection during the original installation, so the passcode was never actually stored.

### Lesson

> **A tool that silently drops input without explaining why is worse than a tool that throws an error. MCP tool responses must include the rejection reason when refusing to act, not just a generic classification.**

---

## Appendix: Issue Template

```markdown
## Issue #N: [Short Descriptive Title]

**Date:** YYYY-MM-DD  
**Duration:** X hours/minutes  
**Severity:** LOW | MEDIUM | HIGH | CRITICAL  
**Status:** OPEN | IN PROGRESS | FIXED | DOCUMENTED

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

_Last verified: 2026-04-15 | Issues: 13 | Status: All scoring flaws fixed (v2.7.0)_

---

## Issue #11: Domain Signal Value-Space Disjunction — 15% of Scoring Weight Is Dysfunctional

**Date:** 2026-04-15  
**Duration:** 45 minutes (discovery via source trace)  
**Severity:** HIGH  
**Status:** FIXED — v2.7.0

### Problem

The domain signal (15% of composite score) can never return 1.0 under normal use. The query-side value space and the memory-side value space do not intersect.

### Symptom

Three real `elefante-MemorySearch` queries ("installer environment virtual", "scoring formula behavioral relevance", "what should I remember about debugging") all returned the same top 4 specification memories with identical scores. Non-spec results were suppressed.

### Root Cause

**Write path:** `orchestrator.py:497` defaults domain to `"reference"`. `memory.py:128` sets `DomainType.REFERENCE` as default. Most memories stored with domain=`"reference"`.

**Read path:** `retrieval.py:138-148` infers query domain from 3 hardcoded keyword groups:
- `"elefante"` → `"project:elefante"`
- `"work"/"job"/"meeting"/"deadline"` → `"work"`
- `"personal"/"home"/"family"` → `"personal"`
- Everything else → `None`

**The mismatch:** `"reference"` is never inferred. `None` → `compute_domain_match` returns 0.5 (neutral). When a keyword does match → inferred domain is `"work"` or `"personal"` → memory domain is `"reference"` → returns 0.0 (penalty). The signal hurts more than it helps.

**Math:** 15% weight × 0.5 = 0.075 constant offset for most queries. 15% weight × 0.0 = penalty when keywords trigger. Never 15% × 1.0 = 0.15 boost.

### Solution

Removed domain signal from `WEIGHTS` dict in `retrieval.py`. Redistributed 0.15 weight to vector (+0.05 → 0.35) and concept (+0.10 → 0.30). Removed domain from composite formula and explanation builder. Left `compute_domain_match()` method intact for Phase 2 re-introduction when real domain inference is built.

**Files changed:** `src/core/retrieval.py` (WEIGHTS, `score_candidate()`, `_build_explanation()`)

### Why This Took So Long

Nobody traced the write path (`DomainType.REFERENCE` default) against the read path (`analyze_query()` keyword inference) before v2.7.0. The 6-signal design was assumed correct because it was documented. The documentation described the architecture faithfully — it just didn't note that the value spaces can't intersect.

### Lesson

> **For every scored signal, trace the write path (where values are set) and the read path (where they're consumed). If the value spaces don't intersect, the signal is dysfunctional regardless of its weight.**

---

## Issue #12: Unconditional Spec Override Dominates All Queries

**Date:** 2026-04-15  
**Duration:** 30 minutes (discovery via ARAA analysis with live queries)  
**Severity:** HIGH  
**Status:** FIXED — v2.7.0

### Problem

The `+0.30` specification/directive boost in `score_candidate()` is unconditional — applied regardless of whether the query has anything to do with system architecture, rules, or specifications. This mathematically guarantees specifications rank above non-spec memories for ANY query.

### Symptom

Asking "what should I remember about debugging" returns system specifications about "Temporal Memory Decay", "Cognitive Multi-Signal Scoring", and "Response Compression Contract" as the top results — none of which help with debugging. The override places specs 0.30 points above their natural composite score, making it impossible for a relevant non-spec fact to outrank an irrelevant spec.

### Root Cause

`retrieval.py:301-302`:
```python
if candidate.memory_type in ("specification", "directive"):
    candidate.composite_score = min(1.0, candidate.composite_score + 0.30)
```

No intent check. No query analysis. Every specification gets +0.30 on every query.

Combined with the vector baseline floor (0.85), a specification with vector_score=0.60 gets: `max(0.60 × 0.85, composite) + 0.30 = ~0.81`. A perfectly relevant non-spec fact with vector_score=0.95 gets: `0.95 × 0.85 = ~0.81` at best (if composite is low). The override makes specs and non-specs effectively equal even when the non-spec is a much better semantic match.

### Solution

Intent-gated the override. Added `"system"` intent detection to `analyze_query()` — queries containing "spec", "directive", "rule", "requirement", "architecture", "constraint", "sdd", "compliance" → `intent="system"`. The +0.30 boost now only fires when `query.inferred_intent == "system"`.

```python
# Before (unconditional):
if candidate.memory_type in ("specification", "directive"):
    candidate.composite_score = min(1.0, candidate.composite_score + 0.30)

# After (intent-gated):
if candidate.memory_type in ("specification", "directive") and query.inferred_intent == "system":
    candidate.composite_score = min(1.0, candidate.composite_score + 0.30)
```

**Files changed:** `src/core/retrieval.py` (`analyze_query()` intent detection, `score_candidate()` guard)

### Why This Took So Long

The override was designed as a correctness guarantee for the SDD (Spec-Driven Development) workflow where specifications must always be visible. That requirement is valid — but only when the query is about the system/architecture. The override was never tested against non-system queries. The assumption was "specifications are always important" rather than "specifications are important when you're asking about the system."

### Lesson

> **Global score overrides must be intent-gated. An unconditional boost is a ranking monopoly, not a relevance signal.**

---

## Issue #13: Co-Activation Cold-Start — Session History Lost on Restart

**Date:** 2026-04-15  
**Duration:** 20 minutes (discovery via source trace)  
**Severity:** MEDIUM  
**Status:** FIXED — v2.7.0

### Problem

Co-activation scoring (15% of composite weight) requires `_session_retrieval_history` from the MCP server to populate the Kuzu query. This list resets to `[]` on every server restart. The first query of every session always gets 0.0 co-activation for all results.

### Symptom

After restarting the MCP server, no search result ever shows co-activation > 0.0 until at least 2 queries have been made in the same server session. For users who restart their IDE frequently (which restarts the MCP server), co-activation is effectively dead.

### Root Cause

`server.py:101`:
```python
self._session_retrieval_history: list[str] = []
```

Initialized empty on every `ElefanteMCPServer.__init__()`. The co-activation architecture is otherwise correct:
- **Write path works:** `record_coactivation()` (`orchestrator.py:976`) validates IDs in ChromaDB, then writes `CO_ACTIVATED` edges to Kuzu via `MERGE` on Entity nodes.
- **Read path works:** `search_memories()` (`orchestrator.py:808-820`) pre-fetches the co-activation matrix from Kuzu using the recent IDs.
- **Schema is correct:** Memories are created as Entity nodes (`orchestrator.py:622`, `EntityType.MEMORY`), and `CO_ACTIVATED` is defined as `FROM Entity TO Entity` (`graph_store.py:392`).

The only gap: `_session_retrieval_history` is the source of IDs for the read path, and it's volatile.

### Solution

Persist `_session_retrieval_history` to `DATA_DIR/session_retrieval_history.json` after every update (search, context injection, delete). Load on server startup with 7-day expiry pruning. Format: `{"ids": [...], "saved_at": "ISO-8601"}`.

**Files changed:** `src/mcp/server.py` (`_load_session_history()`, `_save_session_history()`, `__init__`, context injection block, `_handle_search_memories`, `_handle_memory_delete`)

### Why This Took So Long

The co-activation system was initially diagnosed as "dead" because real queries showed 0.0 co-activation scores. The incorrect assumption was that the Kuzu schema was wrong (`CO_ACTIVATED FROM Entity TO Entity` but memories might be stored as `Memory` nodes). Source tracing proved memories ARE stored as Entity nodes (`orchestrator.py:622`). The real problem is simpler: volatile state that doesn't survive restarts.

### Lesson

> **Before declaring a feature "dead," trace the full write path AND read path. A system that writes correctly but reads from volatile state isn't broken — it's cold.**
