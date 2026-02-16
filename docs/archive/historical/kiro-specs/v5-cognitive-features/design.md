# Design: V5 Cognitive Retrieval Features (Elefante 1.5.0)

## 1. Overview

V5 adds **transparency** and **self-maintenance** to Elefante. The design builds on the existing `CognitiveRetriever` (already wired in v1.4.0) by:

1. **Surfacing score breakdowns** to explain why memories rank
2. **Computing health status** at snapshot time
3. **Flagging potential conflicts** via concept overlap analysis
4. **Enabling proactive suggestions** without explicit search

All features are **deterministic** (no LLM calls) and **snapshot-first** (computed during dashboard generation, not real-time).

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         MCP Server                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │MemorySearch     │  │ProactiveSuggest │  │ConflictReview   │  │
│  │+ explanation    │  │(NEW)            │  │(Future UI)      │  │
│  └────────┬────────┘  └────────┬────────┘  └─────────────────┘  │
└───────────┼─────────────────────┼───────────────────────────────┘
            │                     │
            ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Orchestrator                               │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ _apply_cognitive_scoring() ──► build_explanation()         ││
│  │ get_proactive_suggestions() (NEW)                          ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   CognitiveRetriever                             │
│  score_candidate() ──► ExplanationBuilder (NEW)                 │
│  build_constellation()                                           │
└─────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Snapshot Generation                             │
│  update_dashboard_data.py                                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │compute_health() │  │detect_conflicts()│  │enrich_nodes()   │  │
│  │(NEW)            │  │(NEW)             │  │                 │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Components and Interfaces

### 3.1 CognitiveRetriever (EXTENDED)

**File**: `src/core/retrieval.py`

The existing `CognitiveRetriever` class gains **two new capabilities**:

| Method | Purpose | Requirements |
|--------|---------|--------------|
| `score_candidate()` | Existing scoring | (already done) |
| `build_explanation()` | NEW: Return why | Req-1 |
| `get_proactive_suggestions()` | NEW: Context-based suggestions | Req-4 |

```python
@dataclass
class RetrievalExplanation:
    """Complete explanation for why a memory was retrieved."""
    composite_score: float
    signals: list[dict]  # [{name, score, weight, weighted, reason, details}]
    
    def to_dict(self) -> dict:
        return {
            "composite_score": round(self.composite_score, 3),
            "signals": self.signals
        }


class CognitiveRetriever:
    """Multi-signal retrieval engine with explanation + proactive support."""
    
    # ... existing __init__, WEIGHTS, analyze_query, compute_* methods ...
    
    def score_candidate(
        self,
        candidate: MemoryCandidate,
        query: QueryAnalysis,
        recent_memory_ids: list[str],
        include_explanation: bool = True  # NEW OPTION
    ) -> tuple[MemoryCandidate, Optional[RetrievalExplanation]]:
        """Score candidate and optionally build explanation."""
        # ... compute all scores (existing logic) ...
        
        explanation = None
        if include_explanation:
            explanation = self._build_explanation(candidate, query)
        
        return candidate, explanation
    
    def _build_explanation(
        self,
        candidate: MemoryCandidate,
        query: QueryAnalysis
    ) -> RetrievalExplanation:
        """Build human-readable explanation from scored candidate."""
        signals = [
            {"name": "vector_similarity", "score": candidate.vector_score, 
             "weight": 0.30, "weighted": candidate.vector_score * 0.30,
             "reason": "Semantic match", "details": {}},
            {"name": "concept_overlap", "score": candidate.concept_score,
             "weight": 0.20, "weighted": candidate.concept_score * 0.20,
             "reason": f"Shared concepts", 
             "details": {"matched": list(set(query.concepts) & set(candidate.concepts))}},
            # ... 4 more signals ...
        ]
        return RetrievalExplanation(candidate.composite_score, signals)
    
    async def get_proactive_suggestions(
        self,
        *,
        file_path: Optional[str] = None,
        error_message: Optional[str] = None,
        conversation_snippet: Optional[str] = None,
        memories: list[MemoryCandidate],  # Pre-fetched from store
        limit: int = 3
    ) -> list[tuple[MemoryCandidate, RetrievalExplanation]]:
        """
        Return memories relevant to context WITHOUT explicit search.
        
        Matches against surfaces_when patterns + concept overlap.
        """
```

**Integration**: Single class handles scoring, explanation, AND proactive. No separate classes.

---

### 3.2 MemoryHealthAnalyzer (NEW)

**File**: `src/utils/curation.py`

One class handles ALL health + conflict analysis:

```python
from enum import Enum
from typing import Optional
from dataclasses import dataclass

class HealthStatus(str, Enum):
    HEALTHY = "healthy"   # 
    STALE = "stale"       # 
    AT_RISK = "at_risk"   # 
    ORPHAN = "orphan"     # 


@dataclass
class HealthReport:
    """Health analysis result for a memory."""
    status: HealthStatus
    icon: str
    reasons: list[str]


@dataclass
class ConflictReport:
    """Potential conflict between two memories."""
    memory_a_id: str
    memory_b_id: str
    overlap: float
    shared_concepts: list[str]
    reason: str


class MemoryHealthAnalyzer:
    """
    Analyzes memory health and detects potential conflicts.
    
    Used by: update_dashboard_data.py (snapshot generation)
    """
    
    ICONS = {
        HealthStatus.HEALTHY: "",
        HealthStatus.STALE: "",
        HealthStatus.AT_RISK: "",
        HealthStatus.ORPHAN: "",
    }
    
    def __init__(self, stale_days: int = 90, conflict_threshold: float = 0.6):
        self.stale_days = stale_days
        self.conflict_threshold = conflict_threshold
    
    def compute_health(
        self,
        *,
        superseded_by_id: Optional[str],
        potential_conflicts: list[str],
        days_since_access: int,
        connection_count: int
    ) -> HealthReport:
        """Compute health status for a single memory."""
        reasons = []
        
        if superseded_by_id:
            return HealthReport(HealthStatus.AT_RISK, "", ["Superseded by newer memory"])
        if potential_conflicts:
            return HealthReport(HealthStatus.AT_RISK, "", 
                              [f"Has {len(potential_conflicts)} unresolved conflict(s)"])
        if days_since_access > self.stale_days:
            return HealthReport(HealthStatus.STALE, "", 
                              [f"Not accessed in {days_since_access} days"])
        if connection_count == 0:
            return HealthReport(HealthStatus.ORPHAN, "", ["No connections to other memories"])
        
        return HealthReport(HealthStatus.HEALTHY, "", ["Active and connected"])
    
    def detect_potential_conflict(
        self,
        memory_a_id: str,
        memory_a_concepts: list[str],
        memory_a_domain: str,
        memory_b_id: str,
        memory_b_concepts: list[str],
        memory_b_domain: str,
    ) -> Optional[ConflictReport]:
        """
        Check if two memories MIGHT conflict.
        
        Returns ConflictReport if:
        - Same domain AND
        - Concept overlap > threshold (default 60%)
        """
        if memory_a_domain != memory_b_domain:
            return None
        
        set_a = set(memory_a_concepts)
        set_b = set(memory_b_concepts)
        
        if not set_a or not set_b:
            return None
        
        intersection = set_a & set_b
        union = set_a | set_b
        overlap = len(intersection) / len(union)
        
        if overlap < self.conflict_threshold:
            return None
        
        shared = list(intersection)[:3]
        return ConflictReport(
            memory_a_id=memory_a_id,
            memory_b_id=memory_b_id,
            overlap=overlap,
            shared_concepts=shared,
            reason=f"High concept overlap ({overlap:.0%}): {', '.join(shared)}"
        )
    
    def analyze_all(
        self,
        memories: list[dict]  # List of memory dicts with id, concepts, domain, etc.
    ) -> tuple[dict[str, HealthReport], list[ConflictReport]]:
        """
        Batch analyze: compute health for all + detect all conflicts.
        
        Returns:
        - health_map: {memory_id: HealthReport}
        - conflicts: list of ConflictReport
        """
```

**Integration**: Single class used in `update_dashboard_data.py`. Handles both health AND conflicts.

---

## 4. Data Models

### 4.1 Extended SearchResult

```python
@dataclass
class SearchResult:
    memory: Memory
    score: float
    vector_score: float
    source: str
    explanation: Optional[RetrievalExplanation] = None  # NEW
```

### 4.2 Dashboard Node Properties

```json
{
  "id": "mem_abc123",
  "type": "memory",
  "properties": {
    "title": "...",
    "concepts": ["elefante", "config", "paths"],
    "health": "healthy",           // NEW: healthy|stale|at_risk|orphan
    "health_icon": "",           // NEW: Visual badge
    "potential_conflicts": []      // NEW: List of memory IDs
  }
}
```

### 4.3 Dashboard Edge Types

| Type | Style | Meaning |
|------|-------|---------|
| `SHARES_CONCEPT` | Solid gray | Same concepts |
| `SUPPORTS` | Solid green | Reinforces |
| `CONTRADICTS` | Solid red | Confirmed conflict |
| `POTENTIAL_CONFLICT` | **Dashed orange** (NEW) | Needs user review |

---

## 5. Correctness Properties

> A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.

### Property 1: Explanation Completeness
> For any search result with a composite score, the explanation SHALL contain exactly 6 signal entries (vector, concept, domain, coactivation, authority, temporal) and the sum of weighted_scores SHALL equal composite_score ± 0.001.
> 
> Validates: Req-1.1, Req-1.6

### Property 2: Explanation Accuracy
> For any search result where concept_score > 0, the explanation details SHALL list at least one matching concept that exists in both query and memory.
> 
> Validates: Req-1.2

### Property 3: Health Exhaustiveness
> For any memory in the system, exactly one health status SHALL be assigned from {healthy, stale, at_risk, orphan}.
> 
> Validates: Req-2.1

### Property 4: Health Determinism
> For any memory with identical inputs (superseded_by_id, potential_conflicts, days_since_access, connection_count), compute_health() SHALL return identical output on every invocation.
> 
> Validates: Req-2.2, Req-2.3, Req-2.4, Req-2.5, Req-2.6

### Property 5: Conflict Symmetry
> For any two memories A and B, if detect_potential_conflict(A, B) returns a reason, then detect_potential_conflict(B, A) SHALL also return a reason.
> 
> Validates: Req-3.1

### Property 6: Conflict Soft-Flag
> For any detected potential conflict, the pair SHALL be stored in potential_conflicts and NOT in contradicts.
> 
> Validates: Req-3.2, Req-3.8

### Property 7: Proactive Relevance
> For any proactive suggestion returned, the memory SHALL have at least one surfaces_when pattern matching the input context OR concept overlap > 0.3.
> 
> Validates: Req-4.2, Req-4.3, Req-4.4

### Property 8: Proactive Limit
> For any call to get_proactive_suggestions(), the result list length SHALL be ≤ the limit parameter (default 3).
> 
> Validates: Req-4.5

---

## 5.5 Cognitive Consumption Strategy (Agent-side)

V5 adds `explanation` so an agent can improve effectiveness via **calibration**, **context shaping**, and **self-correction**.

This section defines agent-side logic. It is intentionally **model-agnostic** and **UI-agnostic**.

### Goals

1. Reduce false positives from pure semantic match
2. Improve confidence calibration (know when to assert vs ask)
3. Improve context enhancement (what to add to the working set)
4. Improve query refinement (how to search better next)
5. Preserve truthfulness: avoid over-claiming when evidence is weak

### Core Principles (Rules)

1. **Evidence over rank**: Use rank/order as a hint; decisions should be explained using signals.
2. **Two-step reasoning**:
    - Step A: Decide *whether the memory is relevant now*.
    - Step B: Decide *how to use it* (apply, caveat, ask, or ignore).
3. **Triangulate**: Avoid acting on a single strong signal (e.g., vector) when other signals disagree.
4. **Context-first**: A memory is valuable only if it tightens the current objective, constraints, or next action.
5. **Explicit uncertainty**: If signals do not support confident use, downgrade output to a question or a next-step.

### Interpreting the Signals (General Semantics)

- `vector_similarity`: “Same language / topic neighborhood” (high recall, can be noisy)
- `concept_overlap`: “Shared explicit concepts” (precision booster)
- `domain_match`: “Same operating domain” (reduces cross-domain leakage)
- `coactivation`: “Historically used together” (workflow prior)
- `authority`: “Worth trusting / stable” (importance + reuse)
- `temporal`: “Recently accessed/updated” (freshness prior)

### Agent Decisions: A Minimal Algorithm

Given a query/context and search results with explanations, the agent SHOULD:

1. **Classify the request**: decision vs how-to vs debugging vs preference vs policy.
2. **Select candidates** (top-k) but immediately run a *relevance gate*:
    - If vector is high but concept+domain are weak, treat as “possible lead”, not “answer”.
3. **Choose an action per memory**:
    - **Apply** if at least two independent supports align with the objective (e.g., concept+domain, or authority+domain).
    - **Caveat** if only one support is strong (often vector-only).
    - **Ask** if the memory might matter but missing a disambiguator (domain, timeframe, scope).
    - **Ignore** if signals indicate mismatch or it would expand context without tightening the task.
4. **Synthesize**:
    - Prefer summarizing a small set (1–3) of “actionable constraints” vs dumping retrieved text.
    - When multiple memories agree: merge into a single rule.
    - When they disagree: surface the conflict and prefer the most recent *unless* authority strongly favors the older canonical rule.
5. **Refine search**:
    - If top results look “vector-only”, rewrite query using explicit concepts/domains from the user’s task.
    - If results cluster in the wrong domain, add domain keywords or filter.
    - If conflicts appear, explicitly search for “decision”, “superseded”, “updated”, or canonical keys.

### Context Enhancement (What to Add to Working Context)

The agent SHOULD convert retrieved memories into one of these context artifacts:

1. **Constraints** (must/never/only) — highest leverage
2. **Definitions** (what terms mean in this project)
3. **Defaults** (preferred style, workflow expectations)
4. **Risks** (known pitfalls, conflicts, stale areas)
5. **Next actions** (tests to run, files to inspect)

The agent SHOULD NOT add raw memory bodies into context unless needed; prefer distilled artifacts.

### Output Contract (Human-Facing)

To improve adoption and trust, agent outputs SHOULD include:

- One line: “Why this memory surfaced” (signals, not raw JSON)
- One line: “How it changes the next step” (apply / caveat / ask / ignore)

This contract is compatible with STAC but not dependent on it.

---

## 6. Error Handling

### 6.1 Missing Metadata
- If memory lacks `concepts`: Use empty list, concept_score = 0
- If memory lacks `domain`: Default to "general", domain_score = 0.5
- If memory lacks `created_at`/`last_accessed`: Use current time, temporal_score = 0.5

### 6.2 Conflict Detection Failures
- If concepts are empty for either memory: Skip conflict check (return None)
- If domain is None: Treat as non-matching domain (no conflict)

### 6.3 Proactive Suggestions Edge Cases
- If all context inputs are None/empty: Return empty list
- If no memories match: Return empty list (not an error)
- If ChromaDB unavailable: Log error, return empty list

### 6.4 Health Computation Fallbacks
- If days_since_access cannot be computed: Assume 0 (healthy)
- If connection_count unavailable: Assume 0 (orphan)

---

## 7. Testing Strategy

### 7.1 Property-Based Testing
- **Library**: `hypothesis` (Python)
- **Iterations**: Minimum 100 per property
- **Generators**: Custom strategies for memories, queries, concept lists

### 7.2 Test Categories

| Category | Tool | Coverage |
|----------|------|----------|
| Property tests | hypothesis | Properties 1-8 |
| Unit tests | pytest | Individual functions |
| Integration tests | pytest | MCP tool → Orchestrator → Store |
| Snapshot tests | pytest | Dashboard JSON structure |

### 7.3 Test Tagging Convention
```python
@pytest.mark.property
@pytest.mark.v5
class TestExplanationCompleteness:
    """Property 1: Explanation Completeness
    Validates: Req-1.1, Req-1.6
    """
```

---

## 8. Files to Modify

| File | Changes |
|------|---------|
| `src/core/retrieval.py` | Extend `CognitiveRetriever`: add `_build_explanation()`, `get_proactive_suggestions()`, add `RetrievalExplanation` dataclass |
| `src/utils/curation.py` | Add `MemoryHealthAnalyzer` class (health + conflicts in one place) |
| `src/core/orchestrator.py` | Pass `include_explanation=True` to scorer, attach to results |
| `src/mcp/server.py` | Add `elefanteProactiveSuggestions` tool, include explanation in search response |
| `scripts/update_dashboard_data.py` | Use `MemoryHealthAnalyzer.analyze_all()` for health + conflict edges |

---

## 9. Implementation Order

1. **Req-1 (Explanation)**: Lowest risk, builds on existing scoring
2. **Req-2 (Health)**: Standalone computation in snapshot script
3. **Req-3 (Conflicts)**: Depends on concept overlap already computed
4. **Req-4 (Proactive)**: New MCP tool, highest complexity

---

*Document Version: 1.0*  
*Created: 2025-12-27*  
*Methodology: Kiro Spec-Driven Development*
