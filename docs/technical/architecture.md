# Elefante Architecture

**Version:** 1.6.2 | **Status:** Production Ready

## 1. System Overview

Elefante solves the "stateless agent" problem by bridging the gap between fuzzy semantic search and structured knowledge graphs.

### The Triple-Layer Brain

1.  **Semantic Memory (ChromaDB):**
    - **Role:** Handles "fuzzy" queries and meaning-based retrieval.
    - **Model:** Uses `thenlper/gte-base` (Local, 768-dim) for embeddings.
2.  **Structured Memory (Kuzu Graph DB):**
    - **Role:** Manages deterministic facts and relationships.
    - **Schema:** Nodes (`Memory`, `Entity`, `Session`) and Edges (`RELATES_TO`, `DEPENDS_ON`, `CREATED_IN`).
3.  **Conversation Context:**
    - **Role:** Resolves pronouns ("it", "that") using a time-weighted query over recent messages.

### Agent-Brain Classification (ETL)

In v1.1.0, Elefante shifts classification responsibility to the Agent (the "Brain").
- **ETL Pipeline**: Raw memories are ingested and then processed by the agent via `elefanteETLProcess` and `elefanteETLClassify`.
- **V5 Topology**: Memories are classified into Rings (Core, Domain, Topic, Leaf) and Knowledge Types (Law, Principle, Fact, etc.).

## 2. The Orchestrator Logic

The `Memory Orchestrator` (`src/core/orchestrator.py`) is the central decision engine.

### Transaction-Scoped Locking (v1.1.0)

To support multi-IDE usage without deadlocks:
- **Per-Operation Locks**: Locks are acquired only for the duration of a write operation (milliseconds).
- **Auto-Expiry**: Stale locks (>30s) are automatically cleared.
- **No Manual Toggle**: `elefanteSystemEnable` is now a no-op; the system is always ready.

### Adaptive Weighting

Instead of a static RAG formula, Elefante analyzes the query to shift importance:

- **Pronouns found (`it`, `she`):** Boosts Conversation Context weight.
- **Specific IDs (`uuid`, `id`):** Boosts Graph weight.
- **General Questions (`how`, `why`):** Boosts Semantic weight.

### Data Flow: Storing a Memory

1.  **Ingest:** Text received via `elefanteMemoryAdd`.
2.  **Dual-Write:**
    - **Vector:** Content embedded and stored in ChromaDB.
    - **Graph:** A `Memory` node is created in Kuzu.
3.  **Link:** The memory is linked to the current `Session` node for temporal grounding.
