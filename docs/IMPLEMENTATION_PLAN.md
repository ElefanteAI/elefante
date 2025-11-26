# Hybrid Search Implementation Plan

## Overview
This document provides a step-by-step implementation plan for adding conversation context awareness to Elefante's search system. Each task is atomic, testable, and builds on previous work.

**Reference:** See [`HYBRID_SEARCH_ARCHITECTURE.md`](HYBRID_SEARCH_ARCHITECTURE.md) for architectural details.

---

## Phase 1: Foundation (Core Infrastructure)

### Task 1.1: Create Conversation Context Models
**File:** `src/models/conversation.py` (NEW)

**Objective:** Define data structures for conversation messages and search candidates

**Implementation:**
```python
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

class Message(BaseModel):
    """Represents a single conversation message"""
    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    role: str  # "user" | "assistant" | "system"
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class SearchCandidate(BaseModel):
    """Unified search candidate from any source"""
    text: str
    score: float = Field(ge=0.0, le=1.0)
    source: str  # "conversation" | "semantic" | "graph"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    embedding: Optional[List[float]] = None
    
    # For deduplication
    memory_id: Optional[UUID] = None
```

**Tests:**
- Create message with all fields
- Validate score bounds (0-1)
- Serialize/deserialize to JSON

**Estimated Time:** 30 minutes

---

### Task 1.2: Implement Conversation Context Retriever
**File:** `src/core/conversation_context.py` (NEW)

**Objective:** Extract and score conversation snippets for search

**Implementation:**
```python
from typing import List, Optional
from uuid import UUID
from src.models.conversation import Message, SearchCandidate
from src.core.vector_store import get_vector_store
from src.utils.logger import get_logger

class ConversationSearcher:
    """Searches conversation context for relevant messages"""
    
    def __init__(self, max_window: int = 50):
        self.max_window = max_window
        self.vector_store = get_vector_store()
        self.logger = get_logger(__name__)
    
    async def collect_candidates(
        self,
        query: str,
        session_id: UUID,
        limit: int = 10
    ) -> List[SearchCandidate]:
        """
        Retrieve conversation messages and score by relevance
        
        Scoring:
        - Recency: 0.5 (newer = higher)
        - Keyword overlap: 0.3 (simple term matching)
        - Role weight: 0.2 (user > assistant)
        """
        # 1. Fetch recent memories with session_id filter
        # 2. Score each by recency + keyword overlap
        # 3. Return top N as SearchCandidates
```

**Key Methods:**
- `collect_candidates()`: Main entry point
- `_score_by_recency()`: Time-based scoring
- `_score_by_keywords()`: Simple term matching
- `_score_by_role()`: User messages prioritized

**Tests:**
- Empty conversation returns empty list
- Recent messages score higher
- Keyword matches boost score
- Respects limit parameter

**Estimated Time:** 2 hours

---

### Task 1.3: Extend Query Models
**File:** `src/models/query.py` (MODIFY)

**Objective:** Add conversation-related parameters to search filters

**Changes:**
```python
# ADD to SearchFilters class:
class SearchFilters(BaseModel):
    # ... existing fields ...
    
    # NEW: Conversation context
    session_id: Optional[UUID] = None
    include_conversation: bool = True
    include_stored: bool = True
    conversation_weight: float = Field(default=0.3, ge=0.0, le=1.0)
```

**Tests:**
- Validate weight bounds
- Serialize with new fields
- Backward compatibility (old code still works)

**Estimated Time:** 30 minutes

---

### Task 1.4: Add Scoring Normalization Utilities
**File:** `src/core/scoring.py` (NEW)

**Objective:** Normalize scores across heterogeneous sources

**Implementation:**
```python
from typing import List, Dict
from src.models.conversation import SearchCandidate

class ScoreNormalizer:
    """Normalizes and combines scores from multiple sources"""
    
    @staticmethod
    def normalize_scores(
        candidates: List[SearchCandidate],
        weights: Dict[str, float]
    ) -> List[SearchCandidate]:
        """
        Apply weighted scoring across sources
        
        weights = {
            "conversation": 0.3,
            "semantic": 0.4,
            "graph": 0.3
        }
        """
        # Group by source
        # Apply weights
        # Return normalized candidates
    
    @staticmethod
    def adaptive_weights(
        query: str,
        has_session: bool
    ) -> Dict[str, float]:
        """
        Determine optimal weights based on query characteristics
        
        Rules:
        - Pronouns ("it", "that") → boost conversation
        - Specific terms ("UUID", "named") → boost graph
        - Questions → boost semantic
        """
```

**Tests:**
- Weights sum to 1.0
- Adaptive weights adjust correctly
- Edge cases (empty candidates, single source)

**Estimated Time:** 1.5 hours

---

### Task 1.5: Implement Embedding-Based Deduplication
**File:** `src/core/deduplication.py` (NEW)

**Objective:** Remove near-duplicate results using embedding similarity

**Implementation:**
```python
from typing import List
from src.models.conversation import SearchCandidate
from src.core.embeddings import get_embedding_service

class ResultDeduplicator:
    """Deduplicates search results using embedding similarity"""
    
    def __init__(self, threshold: float = 0.95):
        self.threshold = threshold
        self.embedding_service = get_embedding_service()
    
    async def deduplicate(
        self,
        candidates: List[SearchCandidate]
    ) -> List[SearchCandidate]:
        """
        1. Generate embeddings for all candidates (if not present)
        2. Compute pairwise cosine similarity
        3. Group candidates with similarity > threshold
        4. Keep highest-scored candidate from each group
        5. Merge metadata (sources array)
        """
```

**Tests:**
- Identical text deduplicates
- Different text preserved
- Metadata merged correctly
- Respects threshold parameter

**Estimated Time:** 2 hours

---

## Phase 2: Orchestrator Integration

### Task 2.1: Extend Orchestrator Search Method
**File:** `src/core/orchestrator.py` (MODIFY)

**Objective:** Add conversation search to existing hybrid search

**Changes to `search_memories()` signature:**
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
    return_debug: bool = False
) -> Union[List[SearchResult], Tuple[List[SearchResult], Dict]]:
```

**Implementation Steps:**
1. Extract new parameters from filters if provided
2. Determine adaptive weights based on query
3. Execute searches in parallel:
   - Conversation search (if enabled)
   - Stored search (existing logic)
4. Normalize scores
5. Deduplicate
6. Apply limit
7. Log telemetry
8. Return results (+ debug if requested)

**Tests:**
- Conversation-only search works
- Stored-only search works (backward compat)
- Hybrid search merges correctly
- Debug mode returns stats

**Estimated Time:** 3 hours

---

### Task 2.2: Add Private Helper Methods
**File:** `src/core/orchestrator.py` (MODIFY)

**New Methods:**
```python
async def _collect_conversation_candidates(
    self,
    query: str,
    session_id: UUID,
    limit: int
) -> List[SearchCandidate]:
    """Wrapper for ConversationSearcher"""

async def _convert_to_search_results(
    self,
    candidates: List[SearchCandidate]
) -> List[SearchResult]:
    """Convert SearchCandidate to SearchResult"""

async def _merge_and_deduplicate(
    self,
    conversation_candidates: List[SearchCandidate],
    stored_results: List[SearchResult],
    weights: Dict[str, float]
) -> List[SearchResult]:
    """Core merging logic"""
```

**Tests:**
- Each method tested in isolation
- Integration test for full flow

**Estimated Time:** 2 hours

---

### Task 2.3: Add Telemetry and Logging
**File:** `src/core/orchestrator.py` (MODIFY)

**Objective:** Comprehensive observability for hybrid search

**Log Events:**
```python
# At start
logger.info(
    "hybrid_search_started",
    query=query[:100],
    mode=mode.value,
    include_conversation=include_conversation,
    include_stored=include_stored,
    session_id=str(session_id) if session_id else None
)

# After each source
logger.debug(
    "conversation_search_completed",
    count=len(conv_candidates),
    avg_score=avg_score,
    elapsed_ms=elapsed
)

# After merge
logger.info(
    "hybrid_search_completed",
    conversation_count=conv_count,
    stored_count=stored_count,
    dedup_removed=dedup_count,
    final_count=len(results),
    top_source=results[0].source if results else None,
    elapsed_ms=total_elapsed
)
```

**Debug Response Format:**
```python
if return_debug:
    return results, {
        "query": query,
        "sources": {
            "conversation": {"count": X, "avg_score": Y},
            "semantic": {"count": X, "avg_score": Y},
            "graph": {"count": X, "avg_score": Y}
        },
        "deduplication": {
            "before": X,
            "after": Y,
            "removed": Z
        },
        "weights": weights,
        "elapsed_ms": elapsed
    }
```

**Tests:**
- Logs captured in test mode
- Debug response structure validated

**Estimated Time:** 1 hour

---

## Phase 3: MCP Server Updates

### Task 3.1: Update searchMemories Tool Schema
**File:** `src/mcp/server.py` (MODIFY)

**Objective:** Expose new parameters via MCP tool

**Changes to Tool definition:**
```python
Tool(
    name="searchMemories",
    description="""...(existing description)...""",
    inputSchema={
        "type": "object",
        "properties": {
            # ... existing fields ...
            
            # NEW FIELDS
            "include_conversation": {
                "type": "boolean",
                "default": True,
                "description": "Search current conversation context (session-scoped, recent messages)"
            },
            "include_stored": {
                "type": "boolean",
                "default": True,
                "description": "Search long-term stored memories (persistent, cross-session)"
            },
            "session_id": {
                "type": "string",
                "description": "Session UUID for conversation context. If not provided, searches stored memories only."
            },
            "return_debug": {
                "type": "boolean",
                "default": False,
                "description": "Include debug statistics in response (source counts, scores, dedup info)"
            }
        },
        "required": ["query"]
    }
)
```

**Tests:**
- Tool schema validates
- MCP server accepts new parameters
- Backward compatibility (old calls still work)

**Estimated Time:** 1 hour

---

### Task 3.2: Update Tool Handler
**File:** `src/mcp/server.py` (MODIFY)

**Objective:** Pass new parameters to orchestrator

**Changes to `_handle_search_memories()`:**
```python
async def _handle_search_memories(self, args: Dict[str, Any]) -> Dict[str, Any]:
    # Parse mode (existing)
    mode_str = args.get("mode", "hybrid")
    mode = QueryMode(mode_str)
    
    # Parse filters (existing)
    filters = None
    if "filters" in args:
        # ... existing filter parsing ...
    
    # NEW: Parse session_id
    session_id = None
    if "session_id" in args:
        session_id = UUID(args["session_id"])
    
    # NEW: Parse conversation flags
    include_conversation = args.get("include_conversation", True)
    include_stored = args.get("include_stored", True)
    return_debug = args.get("return_debug", False)
    
    # Search with new parameters
    result = await self.orchestrator.search_memories(
        query=args["query"],
        mode=mode,
        limit=args.get("limit", 10),
        filters=filters,
        min_similarity=args.get("min_similarity", 0.3),
        include_conversation=include_conversation,
        include_stored=include_stored,
        session_id=session_id,
        return_debug=return_debug
    )
    
    # Handle debug response
    if return_debug:
        results, debug_stats = result
        return {
            "success": True,
            "count": len(results),
            "results": [r.to_dict() for r in results],
            "debug": debug_stats
        }
    else:
        return {
            "success": True,
            "count": len(result),
            "results": [r.to_dict() for r in result]
        }
```

**Tests:**
- Handler passes parameters correctly
- Debug mode returns extra stats
- Error handling for invalid session_id

**Estimated Time:** 1 hour

---

## Phase 4: Testing & Validation

### Task 4.1: Unit Tests
**Files:** `tests/test_*.py` (NEW/MODIFY)

**Test Coverage:**

1. **`tests/test_conversation_context.py`** (NEW)
   - Message creation and validation
   - Candidate scoring (recency, keywords, role)
   - Empty conversation handling
   - Window limit enforcement

2. **`tests/test_scoring.py`** (NEW)
   - Score normalization
   - Adaptive weight calculation
   - Edge cases (empty, single source)

3. **`tests/test_deduplication.py`** (NEW)
   - Identical text deduplication
   - Near-duplicate detection
   - Metadata merging
   - Threshold sensitivity

4. **`tests/test_orchestrator.py`** (MODIFY)
   - Conversation-only search
   - Stored-only search
   - Hybrid search with both sources
   - Debug mode output

**Estimated Time:** 4 hours

---

### Task 4.2: Integration Tests
**File:** `tests/integration/test_hybrid_search.py` (NEW)

**Test Scenarios:**

1. **Scenario: Pronoun Resolution**
   ```python
   # Setup
   - Add conversation: "I'm working on Elefante"
   - Add stored memory: "Elefante is a memory system"
   
   # Query: "how do I install it?"
   # Expected: Conversation result ranked higher (pronoun context)
   ```

2. **Scenario: Deduplication**
   ```python
   # Setup
   - Add conversation: "Clean code is important"
   - Add stored memory: "Clean code is important"
   
   # Query: "clean code"
   # Expected: Single result with sources=["conversation", "semantic"]
   ```

3. **Scenario: Temporal Prioritization**
   ```python
   # Setup
   - Old stored memory: "Use Python 3.8"
   - Recent conversation: "Use Python 3.12"
   
   # Query: "which Python version?"
   # Expected: Conversation result ranked higher (recency)
   ```

4. **Scenario: Specific Query**
   ```python
   # Setup
   - Conversation: "I like clean folders"
   - Stored memory with entity: "Jaime prefers clean development folders"
   
   # Query: "Jaime's development preferences"
   # Expected: Stored result ranked higher (specific entity match)
   ```

**Estimated Time:** 3 hours

---

### Task 4.3: Performance Testing
**File:** `tests/performance/test_search_latency.py` (NEW)

**Metrics to Measure:**
- Search latency (p50, p95, p99)
- Embedding cache hit rate
- Deduplication overhead
- Memory usage

**Target SLAs:**
- p95 latency < 500ms
- Cache hit rate > 80%
- Memory growth < 10MB per 1000 searches

**Estimated Time:** 2 hours

---

## Phase 5: Documentation & Deployment

### Task 5.1: Update README
**File:** `README.md` (MODIFY)

**Sections to Add:**
- Conversation context feature overview
- Usage examples with `session_id`
- Debug mode explanation
- Performance characteristics

**Estimated Time:** 1 hour

---

### Task 5.2: Create Usage Guide
**File:** `docs/USAGE_GUIDE.md` (NEW)

**Content:**
- How to use conversation context
- When to use conversation-only vs stored-only
- Interpreting debug output
- Best practices for session management

**Estimated Time:** 1.5 hours

---

### Task 5.3: Update API Documentation
**File:** `docs/API.md` (MODIFY)

**Changes:**
- Document new `searchMemories` parameters
- Add examples for each search mode
- Explain scoring and deduplication

**Estimated Time:** 1 hour

---

## Summary

### Total Estimated Time
- **Phase 1 (Foundation):** 8.5 hours
- **Phase 2 (Orchestrator):** 6 hours
- **Phase 3 (MCP Server):** 2 hours
- **Phase 4 (Testing):** 9 hours
- **Phase 5 (Documentation):** 3.5 hours

**Total:** ~29 hours (approximately 4 working days)

### Critical Path
1. Task 1.1 → 1.2 → 1.3 (Models + Context)
2. Task 1.4 → 1.5 (Scoring + Dedup)
3. Task 2.1 → 2.2 → 2.3 (Orchestrator)
4. Task 3.1 → 3.2 (MCP Server)
5. Task 4.1 → 4.2 → 4.3 (Testing)
6. Task 5.1 → 5.2 → 5.3 (Docs)

### Dependencies
- All Phase 1 tasks must complete before Phase 2
- Phase 2 must complete before Phase 3
- Phase 3 must complete before Phase 4
- Phase 5 can run in parallel with Phase 4

### Risk Mitigation
- **Risk:** Deduplication too slow
  - **Mitigation:** Implement caching, limit candidate pool
- **Risk:** Conversation context clutters long-term memory
  - **Mitigation:** Use TTL, separate collection, or memory_type filter
- **Risk:** Backward compatibility breaks
  - **Mitigation:** All new parameters have defaults, extensive testing

---

**Document Status:** Ready for Implementation  
**Author:** IBM Bob (Architect Mode)  
**Date:** 2025-11-25  
**Version:** 1.0
