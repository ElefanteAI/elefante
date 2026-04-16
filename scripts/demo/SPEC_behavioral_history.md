# SPEC: Behavioral History Pass for Demo Dataset

> **Status:** Implemented and verified (8/8 criteria pass)
> **Traces to:** `src/models/memory.py` (MemoryMetadata fields), `src/core/vector_store.py` (update_memory, replace_memory)
> **Implements:** Dashboard demo completeness — making 100 memories look like a real 6-month workspace

---

## Problem

The current 100-memory dataset is temporally spread but behaviorally flat:
- `access_count` = 0 on every memory (zero reinforcement signal)
- `last_accessed` = `created_at` (no recency-of-access differentiation)
- No `session_id` on conversations
- `conflict_ids` not cross-linked on contradiction pairs
- No `related_memory_ids` links between topically related memories
- No `parent_id` hierarchies
- `status` = NEW on everything (no ACTIVE/ARCHIVED variance)
- `authority_score` = default 0.5 everywhere

The dashboard renders a smooth decay curve but every memory is indistinguishable from a write-once-never-read artifact.

## Solution: Post-Injection Behavioral History Pass

After the 100 memories are injected, run a deterministic second pass that simulates 6 months of realistic usage.

### Phase 1: Session IDs on Conversations (20 memories)

Group the 20 conversation memories into 5 sessions of 4 conversations each.
- Generate 5 deterministic UUIDs (seeded).
- Assign `session_id` to each conversation memory via `replace_memory`.

### Phase 2: Conflict Cross-Links (10 memories)

For each contradiction pair (5 pairs, indices tracked at creation):
- Set `conflict_ids = [other_id]` on both memories in the pair.
- Set `status = MemoryStatus.ACTIVE` on both (they've been seen, conflict detected).

### Phase 3: Related Memory Links (topical clusters)

Create 4 clusters of 3-5 memories each based on content affinity:
- Backend infrastructure facts → link 4 related
- CI/CD conversations → link 4 related
- Security specs + decisions → link 3 related
- Tooling supersession group → link 4 related

Set `related_memory_ids` on each memory in a cluster to point to the others.

### Phase 4: Access Pattern Simulation

Distribute access counts following a power law (Zipf-like, seeded):
- **Hot memories** (top 10): access_count 15-30, last_accessed within 3 days
- **Warm memories** (next 20): access_count 5-14, last_accessed within 14 days
- **Cool memories** (next 30): access_count 1-4, last_accessed within 60 days
- **Cold memories** (remaining 35): access_count 0, last_accessed = created_at

Update `last_accessed`, `access_count`, and `status` (ACTIVE for accessed, NEW for untouched).

### Phase 5: Authority Score Computation

For each surviving memory, compute:
```
authority_score = clamp(0.0, 1.0, (score/100) * log(access_count + 1) * freshness)
```
Where `freshness = exp(-0.005 * days_since_access)`.

### Phase 6: Rescore

Rerun `calculate_relevance_score()` with the updated access patterns.
Hot memories should now score significantly higher than cold ones of similar age.

## Verification Criteria

After the pass completes, assert:
1. `access_count > 0` for at least 60 memories
2. `last_accessed != created_at` for at least 60 memories
3. `session_id IS NOT NULL` for exactly 20 memories (conversations)
4. `conflict_ids` non-empty for exactly 10 memories (5 contradiction pairs)
5. `related_memory_ids` non-empty for at least 15 memories
6. `status = ACTIVE` for at least 60 memories
7. Score variance: `max(scores) - min(scores) >= 40`
8. `authority_score` variance: `max - min >= 0.3`

## Fields Touched (from src/models/memory.py MemoryMetadata)

| Field | Source | Method |
|-------|--------|--------|
| `access_count` | Phase 4 | `update_memory` |
| `last_accessed` | Phase 4 | `update_memory` |
| `status` | Phase 2, 4 | `replace_memory` (status not in update_memory) |
| `session_id` | Phase 1 | `replace_memory` |
| `conflict_ids` | Phase 2 | `replace_memory` |
| `related_memory_ids` | Phase 3 | `replace_memory` |
| `authority_score` | Phase 5 | `replace_memory` |
| `score` | Phase 6 | `update_memory` |

## API Constraints (verified from src/core/vector_store.py)

- `update_memory(id, dict)` supports: score, tags, status, deprecated, archived, supersedes_id, superseded_by_id, last_accessed, last_modified, access_count, content, custom_metadata
- `replace_memory(memory)` does full delete+add — needed for fields NOT in update_memory (session_id, conflict_ids, related_memory_ids, authority_score)
- `conflict_ids` stored as comma-joined UUIDs at add time (line 170)
- `session_id` stored via `_prepare_metadata` at add time
- All replace_memory calls must re-embed if content changed (we won't change content)
