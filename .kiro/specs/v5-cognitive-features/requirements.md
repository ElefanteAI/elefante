## Agent Consumption Guidelines (STAC)

Purpose: Standardize how agents consume V5 `explanation` signals and respond in Simple Terms And Concise (STAC).

Signals: vector_similarity, concept_overlap, domain_match, coactivation, authority, temporal.

Behavior Thresholds (defaults):
- Accept confidently: vector ≥ 0.85 AND (authority ≥ 0.80 OR temporal ≥ 0.90).
- Ask to clarify: concept_overlap = 0 AND domain_match ≤ 0.50 WITH vector ≥ 0.80.
- Prefer recency on conflicts: if two memories disagree, choose the one with temporal ≥ 0.90 unless authority differs by ≥ 0.20.
- Refine query: if top-3 results have concept_overlap = 0, broaden/rename terms; add domain keywords.

Confidence Bands:
- High: composite_score ≥ 0.60 with at least two strong supports (authority ≥ 0.85, temporal ≥ 0.90, concept_overlap > 0).
- Medium: composite_score 0.45–0.59; present with a caveat or ask once.
- Low: composite_score < 0.45; do not assert—summarize and propose next steps.

STAC Response Template (agent output):
- Why surfaced: vector X.X, authority Y.Y, temporal Z.Z; concept overlap: [none|some|strong]; domain: [value].
- Relevance: one line tying signals to the user’s objective.
- Next action: refine query, ask a focused question, or proceed.

Examples:
- Good: "Found 3. Why: vector 0.91, authority 0.88, temporal 0.96; overlap: none; domain: project. Next: add 'protocol' keyword or clarify scope."
- Avoid: Walls of JSON or multi-paragraph justifications—prefer one-liners plus a single next step.

Agent Rules of Engagement:
- Always include a one-line "Why surfaced" and a one-line "Next".
- Prefer recent, authoritative memories; disclose gaps explicitly (UNKNOWN) when signals are weak.
- Do not overfit to a single signal; composite plus support signals drive decisions.

Config (client-side, suggested):
- `elefante.search.thresholds`: { vector_min: 0.85, authority_min: 0.80, temporal_min: 0.90 }
- `elefante.search.bands`: { high: 0.60, medium: [0.45,0.59], low: <0.45 }
- `elefante.search.output`: { show_why: true, show_next: true, max_lines: 3 }

# Requirements: V5 Cognitive Retrieval Features (Elefante 1.5.0)

## 1. Introduction

Elefante V5 transforms the memory system from **passive retrieval** to **active intelligence**. Users currently search and receive results—but don't know WHY a memory surfaced, whether it's still valid, or if it conflicts with other knowledge. V5 adds transparency (explanation), health monitoring (badges), and conflict detection (soft flags) to make memories self-documenting and maintainable.

**Scope**: Features 1-4 (Feature 0 = Wire CognitiveRetriever already shipped in v1.4.0)

---

## 2. Glossary

| Term | Definition |
|------|------------|
| **Elefante** | The Elefante memory system—a cognitive knowledge graph for AI assistants |
| **Memory** | A unit of stored knowledge with content, metadata, and relationships |
| **CognitiveRetriever** | The multi-signal scoring engine that ranks search results |
| **Composite Score** | Final ranking score combining 6 weighted signals (vector, concept, domain, coactivation, authority, temporal) |
| **Signal** | A factor contributing to retrieval score (e.g., vector similarity, concept overlap) |
| **Health Status** | A memory's current state: healthy, stale, at_risk, or orphan |
| **Potential Conflict** | Two memories flagged for user review as possibly contradictory |
| **EARS** | Easy Approach to Requirements Syntax—structured acceptance criteria format |

---

## 3. Requirements

### Req-1: Retrieval Explanation

**User Story**: As a user, I want to see WHY each memory was retrieved, so that I can understand and trust the search results.

**Acceptance Criteria**:

1. WHEN Elefante returns search results, THE system SHALL include an explanation object for each result containing the breakdown of all signal contributions.

2. WHEN concept overlap contributes to a score, THE system SHALL list the specific concepts that matched between query and memory.

3. WHEN domain match contributes to a score, THE system SHALL indicate the matched domain value.

4. WHEN authority contributes to a score, THE system SHALL provide a human-readable reason (e.g., "High importance, frequently used").

5. WHEN temporal recency contributes to a score, THE system SHALL indicate days since last access.

6. THE system SHALL format explanations as structured JSON with `signal_name`, `score`, and `reason` fields.

---

### Req-2: Memory Health Score

**User Story**: As a user, I want every memory to display a health indicator, so that I can quickly identify memories that need attention.

**Acceptance Criteria**:

1. THE system SHALL assign exactly one health status to every memory: `healthy`, `stale`, `at_risk`, or `orphan`.

2. WHEN a memory has been superseded (has `superseded_by_id`), THE system SHALL assign `at_risk` status.

3. WHEN a memory has unresolved potential conflicts, THE system SHALL assign `at_risk` status.

4. WHEN a memory has not been accessed in more than 90 days, THE system SHALL assign `stale` status.

5. WHEN a memory has zero graph connections (no edges to other nodes), THE system SHALL assign `orphan` status.

6. WHEN a memory meets none of the above conditions, THE system SHALL assign `healthy` status.

7. THE system SHALL compute health during the dashboard snapshot generation process.

8. THE system SHALL display health as a visual badge:  healthy,  stale,  at_risk,  orphan.

---

### Req-3: Potential Conflict Detection

**User Story**: As a user, I want the system to flag memories that might contradict each other, so that I can review and resolve knowledge inconsistencies.

**Acceptance Criteria**:

1. WHEN two memories share more than 60% concept overlap AND belong to the same domain, THE system SHALL flag them as a potential conflict.

2. WHEN a potential conflict is detected, THE system SHALL store the pair in a `potential_conflicts` field—NOT in `contradicts`.

3. THE system SHALL display potential conflicts in the dashboard with a " Review conflict?" badge.

4. WHEN a user reviews a potential conflict, THE system SHALL offer three resolution options: confirm conflict, dismiss, or mark as contextual exception.

5. IF the user confirms a conflict, THEN THE system SHALL move the pair to the `contradicts` field.

6. IF the user dismisses a conflict, THEN THE system SHALL remove the flag from `potential_conflicts`.

7. THE system SHALL render potential conflict edges as dashed lines (distinct from confirmed contradictions).

8. THE system SHALL NOT auto-assert contradictions—soft detection only.

---

### Req-4: Proactive Memory Surfacing

**User Story**: As a user, I want relevant memories to appear before I search, so that important context is available without explicit queries.

**Acceptance Criteria**:

1. THE system SHALL provide an MCP tool `elefanteProactiveSuggestions` that returns memories relevant to current context.

2. WHEN a file path is provided as context, THE system SHALL return memories with matching `surfaces_when` patterns.

3. WHEN an error message is provided as context, THE system SHALL return memories with matching error patterns in `surfaces_when`.

4. WHEN a conversation snippet is provided, THE system SHALL return memories with concept overlap.

5. THE system SHALL limit proactive suggestions to a maximum of 3 by default.

6. THE system SHALL rank proactive suggestions using the same composite score as search results.

7. THE system SHALL NOT require explicit user search to trigger proactive suggestions.

---

## 4. Out of Scope (V5)

The following are explicitly **NOT** part of V5 requirements:

- **LLM-based classification**: All detection must be deterministic
- **Auto-resolution of conflicts**: System flags only; user decides
- **Feature 5 (Signal Hub Enrichment)**: Deferred to V6
- **Multi-user support**: Single-user system only
- **Real-time conflict detection**: Computed at snapshot time, not on add

---

## 5. Technical Constraints

1. **No LLM calls** — All classification must be deterministic and fast
2. **Backward compatible** — Existing memories must continue working
3. **Snapshot-first** — Dashboard reads from static JSON (no live DB queries)
4. **Single-writer** — Kuzu database lock constraints remain
5. **Soft detection** — Flag for review, never auto-assert

---

## 6. Requirements Traceability Matrix

| Req ID | Feature | Priority | Complexity |
|--------|---------|----------|------------|
| Req-1 | Retrieval Explanation | P0 | Low |
| Req-2 | Memory Health Score | P0 | Low |
| Req-3 | Potential Conflict Detection | P1 | Medium |
| Req-4 | Proactive Memory Surfacing | P1 | Medium |

---

*Document Version: 1.0*  
*Created: 2025-12-27*  
*Methodology: Kiro Spec-Driven Development*
