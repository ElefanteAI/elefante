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
    - **Method**: `Subject-Aspect-Qualifier` (SAQ) Title Generaton.
    - **Check**: Does a memory with this **SAQ Title** already exist?
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

## Semantic Title Generation (SAQ)

Titles are the Primary Key for deduplication. They must follow the **SAQ Pattern**:

**Format**: `{Subject}-{Aspect}-{Qualifier}`
**Max Length**: 30 chars
**Banned Words**: "Really", "Very", "Favorite", "Update", "New"

### Examples

| Raw Content                      | ❌ Bad Title          | ✅ SAQ Title            |
| :------------------------------- | :-------------------- | :---------------------- |
| "I really prefer dark mode IDEs" | User-Pref-Dark        | `Self-Pref-DarkMode`    |
| "The server listens on 0.0.0.0"  | Server-Config-Listens | `Server-Config-Binding` |
| "Do not use relative paths"      | Rule-Path-Relative    | `Dev-Path-Absolute`     |

---

## Logic-Level Deduplication (The Update Path)

The system distinguishes between **New Knowledge** and **Reinforced Knowledge**.

```python
# Pseudo-code logic in Orchestrator
title = llm.generate_title(content)
existing = vector_store.find_by_title(title)

if existing:
    # REINFORCEMENT PATH
    print(f"♻️ Reinforcing existing memory: {existing.id}")
    orchestrator.update_access(existing.id)
    return existing.id
else:
    # CREATION PATH
    print(f"✨ Creating new memory: {title}")
    return vector_store.add(content, title, ...)
```

**Why this matters**:
This prevents the "Bag of Dots" where 10 memories say "I like Python" in slightly different ways. Instead, we have **1 strong node** for "Python Preference".
