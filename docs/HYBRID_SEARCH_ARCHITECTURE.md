# Hybrid Search Architecture: Conversation + Stored Memory

## Executive Summary

This document outlines the architecture for enhancing Elefante's `searchMemories` to intelligently search **both** conversation context (short-term, session-scoped) and stored memories (long-term, persistent) with smart merging, deduplication, and scoring.

---

## Current State Analysis

### Existing Implementation
**File:** [`orchestrator.py:194-256`](../src/core/orchestrator.py:194)

**Current Behavior:**
- `search_memories()` only searches **stored memories** (ChromaDB + Kuzu)
- Three modes: SEMANTIC (vector), STRUCTURED (graph), HYBRID (both)
- No awareness of current conversation context
- Returns `List[SearchResult]` with weighted scoring

**Key Strengths:**
- ✅ Solid hybrid search foundation (vector + graph)
- ✅ Weighted scoring with configurable weights
- ✅ Parallel execution of semantic + structured searches
- ✅ Deduplication by memory ID in hybrid mode

**Critical Gap:**
- ❌ **No conversation context awareness** - if user says "fix that error", the system doesn't know what "that" refers to
- ❌ No session-scoped memory retrieval
- ❌ No temporal prioritization (recent conversation vs old memories)

---

## Proposed Architecture

### 1. Three-Source Search Model

```
┌─────────────────────────────────────────────────────────────┐
│                    searchMemories(query)                     │
└─────────────────────────────────────────────────────────────┘
                            │
                ┌───────────┴───────────┐
                │                       │
        ┌───────▼────────┐      ┌──────▼──────────┐
        │  Conversation  │      │  Stored Memory  │
        │    Context     │      │   (Existing)    │
        │  (NEW LAYER)   │      │                 │
        └───────┬────────┘      └──────┬──────────┘
                │                      │
                │                      ├─► Semantic (ChromaDB)
                │                      └─► Structured (Kuzu)
                │                      
        ┌───────▼──────────────────────▼──────────┐
        │      Merge + Score + Deduplicate        │
        └─────────────────┬───────────────────────┘
                          │
                  ┌───────▼────────┐
                  │ Ranked Results │
                  └────────────────┘
```

### 2. Component Design

#### A. Conversation Context Layer (NEW)
**Purpose:** Extract searchable units from current session

**Location:** New file `src/core/conversation_context.py`

**Key Functions:**
```python
class ConversationContext:
    def __init__(self, session_id: UUID):
        self.session_id = session_id
        self.messages: List[Message] = []
        self.max_window = 50  # Last N messages
    
    async def collect_candidates(
        self, 
        query: str, 
        limit: int = 10
    ) -> List[SearchCandidate]:
        """
        Extract relevant conversation snippets
        
        Returns candidates with:
        - text: message content
        - score: recency + keyword overlap
        - source: "conversation"
        - metadata: timestamp, role, message_id
        """
```

**Scoring Strategy:**
- **Recency weight:** 0.5 (newer = higher score)
- **Keyword overlap:** 0.3 (simple term matching)
- **Role weight:** 0.2 (user messages > assistant messages)

**Data Source:**
- Option 1: In-memory session buffer (fast, ephemeral)
- Option 2: Query recent memories with `session_id` filter (persistent)
- **Recommendation:** Start with Option 2 (reuse existing infrastructure)

#### B. Enhanced Search Orchestrator
**File:** [`orchestrator.py`](../src/core/orchestrator.py)

**New Method Signature:**
```python
async def search_memories(
    self,
    query: str,
    mode: QueryMode = QueryMode.HYBRID,
    limit: int = 10,
    filters: Optional[SearchFilters] = None,
    min_similarity: float = 0.3,
    # NEW PARAMETERS
    include_conversation: bool = True,
    include_stored: bool = True,
    session_id: Optional[UUID] = None,
    conversation_weight: float = 0.3,  # Boost recent context
    return_debug: bool = False
) -> List[SearchResult]:
```

**Execution Flow:**
```python
1. Validate inputs
2. Create query plan (existing)
3. Execute searches in parallel:
   - IF include_conversation: collect_conversation_candidates()
   - IF include_stored: _search_hybrid() (existing)
4. Normalize scores across sources
5. Merge + deduplicate by content similarity
6. Apply final limit
7. Log telemetry
8. Return results (+ debug stats if requested)
```

#### C. Scoring & Normalization Layer
**Purpose:** Make scores comparable across heterogeneous sources

**Challenge:**
- Conversation scores: 0-1 (recency + keyword)
- ChromaDB scores: 0-1 (cosine similarity)
- Kuzu scores: importance/10 (0-1)

**Solution: Weighted Linear Combination**
```python
def normalize_and_merge(
    conversation_results: List[SearchCandidate],
    stored_results: List[SearchResult],
    weights: Dict[str, float]
) -> List[SearchResult]:
    """
    weights = {
        "conversation": 0.3,  # Boost recent context
        "semantic": 0.4,      # Primary search
        "graph": 0.3          # Structured facts
    }
    
    final_score = (
        conv_score * weights["conversation"] +
        sem_score * weights["semantic"] +
        graph_score * weights["graph"]
    )
    """
```

**Adaptive Weights:**
- If `session_id` provided → boost conversation weight to 0.5
- If query has pronouns ("it", "that") → boost conversation to 0.6
- If query is specific ("UUID", "named X") → boost graph to 0.5

#### D. Deduplication Strategy
**Current:** Dedup by memory ID (works for stored memories)

**Problem:** Conversation snippets don't have memory IDs yet

**Solution: Embedding-Based Similarity**
```python
async def deduplicate_results(
    results: List[SearchResult],
    similarity_threshold: float = 0.95
) -> List[SearchResult]:
    """
    1. Generate embeddings for all result texts
    2. Compute pairwise cosine similarity
    3. Group results with similarity > threshold
    4. Keep highest-scored result from each group
    5. Merge metadata (sources: ["conversation", "semantic"])
    """
```

**Optimization:** Use existing `EmbeddingService` to avoid redundant API calls

---

## Implementation Plan

### Phase 1: Foundation (Files to Create/Modify)

#### 1.1 Create Conversation Context Module
**File:** `src/core/conversation_context.py` (NEW)

**Classes:**
- `Message`: Represents a conversation message
- `ConversationContext`: Manages session message buffer
- `ConversationSearcher`: Searches conversation for query

**Dependencies:**
- `src/models/memory.py` (reuse Memory model)
- `src/core/embeddings.py` (for similarity)

#### 1.2 Extend Query Models
**File:** `src/models/query.py` (MODIFY)

**Changes:**
```python
class SearchCandidate(BaseModel):
    """Unified candidate from any source"""
    text: str
    score: float
    source: str  # "conversation" | "semantic" | "graph"
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None

class SearchFilters(BaseModel):
    # ADD:
    session_id: Optional[UUID] = None
    include_conversation: bool = True
    include_stored: bool = True
```

#### 1.3 Enhance Orchestrator
**File:** `src/core/orchestrator.py` (MODIFY)

**New Methods:**
```python
async def _collect_conversation_candidates(
    query: str,
    session_id: UUID,
    limit: int
) -> List[SearchCandidate]

async def _normalize_scores(
    candidates: List[SearchCandidate],
    weights: Dict[str, float]
) -> List[SearchCandidate]

async def _deduplicate_by_embedding(
    candidates: List[SearchCandidate],
    threshold: float = 0.95
) -> List[SearchCandidate]
```

**Modified Method:**
```python
async def search_memories(
    # ... existing params ...
    include_conversation: bool = True,
    include_stored: bool = True,
    session_id: Optional[UUID] = None,
    return_debug: bool = False
) -> Union[List[SearchResult], Tuple[List[SearchResult], Dict]]
```

#### 1.4 Update MCP Server
**File:** `src/mcp/server.py` (MODIFY)

**Changes:**
```python
Tool(
    name="searchMemories",
    inputSchema={
        # ... existing fields ...
        "include_conversation": {
            "type": "boolean",
            "default": True,
            "description": "Search current conversation context"
        },
        "include_stored": {
            "type": "boolean", 
            "default": True,
            "description": "Search long-term stored memories"
        },
        "session_id": {
            "type": "string",
            "description": "Session UUID for conversation context"
        },
        "return_debug": {
            "type": "boolean",
            "default": False,
            "description": "Include debug stats in response"
        }
    }
)
```

### Phase 2: Testing Strategy

#### 2.1 Unit Tests
**File:** `tests/test_conversation_context.py` (NEW)

**Test Cases:**
- Extract messages from session
- Score candidates by recency
- Handle empty conversation
- Respect message window limit

#### 2.2 Integration Tests
**File:** `tests/test_hybrid_search.py` (MODIFY)

**Test Scenarios:**
1. **Conversation-only search**
   - Setup: 5 conversation messages
   - Query: "what did I say about X?"
   - Assert: Returns conversation results only

2. **Stored-only search**
   - Setup: 10 stored memories
   - Query: "facts about Y"
   - Assert: Returns stored results only

3. **Hybrid search with deduplication**
   - Setup: Same content in conversation + stored
   - Query: "tell me about Z"
   - Assert: Single result with merged sources

4. **Pronoun handling**
   - Setup: Conversation mentions "Elefante", query says "it"
   - Query: "how do I install it?"
   - Assert: Conversation results ranked higher

### Phase 3: Observability

#### 3.1 Logging Enhancements
**File:** `src/core/orchestrator.py`

**Log Events:**
```python
logger.info(
    "hybrid_search_executed",
    query=query[:100],
    conversation_count=len(conv_results),
    stored_count=len(stored_results),
    dedup_removed=dedup_count,
    final_count=len(final_results),
    top_source=final_results[0].source if final_results else None,
    elapsed_ms=elapsed
)
```

#### 3.2 Debug Response Format
```json
{
  "results": [...],
  "debug": {
    "query": "original query",
    "sources": {
      "conversation": {"count": 3, "avg_score": 0.75},
      "semantic": {"count": 5, "avg_score": 0.82},
      "graph": {"count": 2, "avg_score": 0.65}
    },
    "deduplication": {
      "before": 10,
      "after": 7,
      "removed": 3
    },
    "weights": {
      "conversation": 0.3,
      "semantic": 0.4,
      "graph": 0.3
    },
    "elapsed_ms": 245
  }
}
```

---

## Migration Strategy

### Backward Compatibility
- All new parameters have defaults (`include_conversation=True`, `include_stored=True`)
- Existing callers get enhanced behavior automatically
- Can disable conversation search with `include_conversation=False`

### Rollout Plan
1. **Phase 1:** Implement conversation context layer (no breaking changes)
2. **Phase 2:** Add to orchestrator with feature flag
3. **Phase 3:** Enable by default after testing
4. **Phase 4:** Update MCP tool schema

### Performance Considerations
- **Conversation search:** Fast (in-memory or indexed by session_id)
- **Deduplication:** O(n²) worst case, but n is small (limit=10-50)
- **Embedding generation:** Cached by EmbeddingService
- **Target latency:** <500ms for typical queries

---

## Success Metrics

### Functional
- ✅ Conversation context included in search results
- ✅ Deduplication prevents redundant results
- ✅ Scores normalized across sources
- ✅ Debug mode provides observability

### Performance
- ✅ Search latency <500ms (p95)
- ✅ No memory leaks from conversation buffer
- ✅ Embedding cache hit rate >80%

### Quality
- ✅ Pronoun queries return relevant conversation context
- ✅ Specific queries prioritize stored facts
- ✅ Recent conversation ranked higher than old memories

---

## Open Questions

1. **Session Management:** How to track active sessions?
   - Option A: MCP server maintains session registry
   - Option B: Caller provides session_id explicitly
   - **Recommendation:** Option B (stateless server)

2. **Conversation Persistence:** Store conversation in ChromaDB?
   - Pro: Unified storage, automatic persistence
   - Con: Clutters long-term memory with ephemeral data
   - **Recommendation:** Store with `memory_type=conversation` + TTL

3. **Query Expansion:** Should we auto-expand pronouns?
   - Pro: Better search quality
   - Con: Adds LLM call latency
   - **Recommendation:** Phase 2 feature (after basic hybrid works)

---

## Next Steps

1. **Review this architecture** with user
2. **Create detailed file-by-file implementation plan**
3. **Implement Phase 1** (conversation context + orchestrator)
4. **Write tests** (Phase 2)
5. **Add observability** (Phase 3)
6. **Update documentation** (README, API docs)

---

**Document Status:** Draft for Review  
**Author:** IBM Bob (Architect Mode)  
**Date:** 2025-11-25  
**Version:** 1.0