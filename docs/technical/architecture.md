# Elefante Architecture: The Second Brain

**Version:** 2.1.4 | **Status:** Production Ready (Windows validated)

## 1. System Overview

Elefante is the **Second Brain** for AI agents. It solves the "stateless agent" problem by bridging the gap between fuzzy semantic search and structured knowledge graphs, providing a persistent cognitive layer that persists across sessions.

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

- **ETL Pipeline**: Raw memories are ingested and then processed by the agent via `elefante-ETLProcess` and `elefante-ETLClassify`.
- **V5 Fields**: Memories can be classified with Ring (Core, Domain, Topic, Leaf), Knowledge Type (Law, Principle, Fact, etc.), and Topic via agent ETL.

## 2. The Orchestrator Logic

The `Memory Orchestrator` (`src/core/orchestrator.py`) is the central decision engine.

### Transaction-Scoped Locking (v1.1.0)

To support multi-IDE usage without deadlocks:

- **Per-Operation Locks**: Locks are acquired only for the duration of a write operation (milliseconds).
- **Auto-Expiry**: Stale locks (>30s) are automatically cleared.
- **No Manual Toggle**: `elefante-System` with `action="enable"` is now a no-op; the system is always ready.

### Cognitive Multi-Signal Scoring (V4)

Instead of a static RAG formula, Elefante uses a multi-faceted 6-signal behavioral model:

- **Vector Match** (0.30)
- **Concept Overlap** (0.20)
- **Domain Match** (0.15)
- **Co-Activation** (0.15) — Passive graphing of what memories are retrieved together in the same session
- **Authority** (0.10)
- **Temporal Freshness** (0.10)

**Smoothed Vector Baseline:** To prevent valid semantic matches from suffering a mathematical cliff when heuristics are missing, the cognitive retriever enforces a static floor: `composite_score` can never fall below `0.85 * vector_score`.

### Data Flow: Storing a Memory

1.  **Ingest:** Text received via `elefante-MemoryAdd`.
2.  **Dual-Write:**
    - **Vector:** Content embedded and stored in ChromaDB.
    - **Graph:** A `Memory` node is created in Kuzu.
3.  **Link:** The memory is linked to the current `Session` node for temporal grounding.

---

## 3. The Enhanced Signal Flow (The "Hijack")

Elefante is designed for **Cognitive Interception**. Instead of a passive database lookup, it follows a four-stage signal processing loop:

1.  **Signal Interception**: The system (or agent orchestrator, eg. Agent Zero) "hijacks" the raw user input before it reaches the reasoning layer.
2.  **Contextual Decanting**: The orchestrator decants the query using **Adaptive Weighting** (Semantic + Graph + Context).
3.  **Signal Processing**: The raw signal is fused with the retrieved context (Laws, Preferences, Pitfalls).
4.  **Enhanced Output**: The agent generates an "Enhanced Answer" that is technically grounded and historically consistent.
