# Authoritative Ingestion Protocol

**Target**: `src.core.orchestrator.MemoryOrchestrator`
**Status**: ENFORCED (Law #4)

> **Philosophy**: The Agent is the **BRAIN**, not a scribe. We do not ask "should I add this?". We ingest, process, and structure information authoritatively.

---

## The 5-Step Pipeline

Every memory ingestion (`add_memory`) MUST pass through these five stages:

1.  **EXTRACT (Parse)**

    - **Goal**: Distill raw text into pure intent.
    - **Action**: Remove conversational fluff ("I think...", "Maybe...").

2.  **CLASSIFY (V3 Schema)**

    - **Goal**: Assign absolute truth coordinates.
    - **Input**: Content.
    - **Output**: `Layer` (Self/World/Intent) & `Sublayer` (Fact, Rule, etc.).
    - **Rule**: Never guess. If unsure, default to `World.Fact`.

3.  **INTEGRITY (Logic-Level Deduplication)**

    - **Goal**: Prevent "Bag of Dots" (redundancy).
        - **Method**: Deterministic `Subject-Aspect-Qualifier` (SAQ) key generation.
        - **Check**: Does an ACTIVE memory with this **canonical key** already exist (in the same namespace)?
                - **YES**: Trigger **Reinforcement Protocol**.
                - **NO**: Proceed to Creation.

4.  **WRITE (Storage)**

    - **Goal**: Persist to persistent storage.
    - **Vector Store**: ChromaDB (Embeddings + Metadata).
    - **Graph Store**: Kuzu (Nodes + Edges).
    - **Rule**: Atoms only. One concept per memory.

5.  **REINFORCE (Hebbian Learning)**
    - **Goal**: Strengthen active pathways.
    - **Action**: New memories start with `access_count = 1` (not 0).
    - **Action**: Re-visited memories get `access_count += 1` and `last_accessed = now()`.

---

## Canonical Key Generation (SAQ)

The SAQ string is the canonical key for deduplication. It must follow the **SAQ Pattern**:

**Format**: `{Subject}-{Aspect}-{Qualifier}`
**Max Length**: 30 chars
**Banned Words**: "Really", "Very", "Favorite", "Update", "New"

### Examples

| Raw Content                      |  Bad Title          |  SAQ Title            |
| :------------------------------- | :-------------------- | :---------------------- |
| "I really prefer dark mode IDEs" | User-Pref-Dark        | `Self-Pref-DarkMode`    |
| "The server listens on 0.0.0.0"  | Server-Config-Listens | `Server-Config-Binding` |
| "Do not use relative paths"      | Rule-Path-Relative    | `Dev-Path-Absolute`     |

---

## Logic-Level Deduplication (Reinforce vs Supersede)

The system distinguishes between **New Knowledge** and **Reinforced Knowledge**.

```python
# Pseudo-code logic in Orchestrator (LLM-free)
canonical_key = agent_or_rules_generate_saq(content)
namespace = route_namespace(content, tags, source)

active = vector_store.find_active_by_canonical_key(
    canonical_key=canonical_key,
    namespace=namespace,
)

if active is None:
    return vector_store.add(content, canonical_key=canonical_key, namespace=namespace, ...)

if hash(normalize(content)) == active.content_hash:
    orchestrator.update_access(active.id)
    return active.id

# New version of same concept
new_id = vector_store.add(content, canonical_key=canonical_key, namespace=namespace, supersedes_id=active.id, ...)
vector_store.mark_superseded(active.id, superseded_by_id=new_id)
return new_id
```

**Why this matters**:
This prevents the "Bag of Dots" where 10 memories say "I like Python" in slightly different ways. Instead, we have **1 strong node** for "Python Preference".
