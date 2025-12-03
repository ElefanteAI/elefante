# Elefante Architecture

**Version:** 1.0.0 | **Status:** Production Ready

## 1. System Overview

Elefante solves the "stateless agent" problem by bridging the gap between fuzzy semantic search and structured knowledge graphs.

### The Triple-Layer Brain

1.  **Semantic Memory (ChromaDB):**
    - **Role:** Handles "fuzzy" queries and meaning-based retrieval.
    - **Model:** Uses `all-MiniLM-L6-v2` (Local, 384-dim) for embeddings.
2.  **Structured Memory (Kuzu Graph DB):**
    - **Role:** Manages deterministic facts and relationships.
    - **Schema:** Nodes (`Memory`, `Entity`, `Session`) and Edges (`RELATES_TO`, `DEPENDS_ON`, `CREATED_IN`).
3.  **Conversation Context:**
    - **Role:** Resolves pronouns ("it", "that") using a time-weighted query over recent messages.

## 2. The Orchestrator Logic

The `Memory Orchestrator` (`src/core/orchestrator.py`) is the central decision engine.

### Adaptive Weighting

Instead of a static RAG formula, Elefante analyzes the query to shift importance:

- **Pronouns found (`it`, `she`):** Boosts Conversation Context weight.
- **Specific IDs (`uuid`, `id`):** Boosts Graph weight.
- **General Questions (`how`, `why`):** Boosts Semantic weight.

### Data Flow: Storing a Memory

1.  **Ingest:** Text received via `addMemory`.
2.  **Dual-Write:**
    - **Vector:** Content embedded and stored in ChromaDB.
    - **Graph:** A `Memory` node is created in Kuzu.
3.  **Link:** The memory is linked to the current `Session` node for temporal grounding.
