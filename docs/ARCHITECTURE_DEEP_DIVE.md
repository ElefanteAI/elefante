# Elefante: Deep Study & Architecture Analysis

## 1. Executive Summary
**Elefante** is a local, privacy-focused AI memory system designed to provide "perfect memory" for AI agents. It distinguishes itself by using a **triple-layer architecture** that combines:
1.  **Semantic Memory** (ChromaDB) for meaning-based retrieval.
2.  **Structured Memory** (Kuzu Graph DB) for deterministic facts and relationships.
3.  **Conversation Context** for session-aware short-term memory.

The system is built with a clean, modular Python codebase and exposes its functionality via the **Model Context Protocol (MCP)**, making it immediately usable by MCP-compliant agents (like Cursor, Claude Desktop, etc.).

## 2. Architecture Overview

Elefante uses an **Orchestrator** pattern to route queries and manage data consistency across its storage backends.

```mermaid
graph TD
    User[User / AI Agent] -->|MCP Protocol| Server[MCP Server]
    Server --> Orchestrator[Memory Orchestrator]
    
    subgraph "Core Logic"
        Orchestrator --> Plan[Query Planner]
        Orchestrator --> Scorer[Score Normalizer]
        Orchestrator --> Dedup[Deduplicator]
        Orchestrator --> Context[Conversation Context]
    end
    
    subgraph "Storage Layer"
        Orchestrator -->|Semantic Search| Vector[Vector Store (ChromaDB)]
        Orchestrator -->|Graph Query| Graph[Graph Store (Kuzu)]
        Context -->|Recent Msgs| Vector
    end
    
    Vector -->|Embeddings| Embed[Embedding Service]
```

### Key Components
-   **Memory Orchestrator (`src/core/orchestrator.py`)**: The brain of the system. It analyzes incoming queries to decide how to route them (Semantic vs. Structured vs. Hybrid) and how to weight the results.
-   **Vector Store (`src/core/vector_store.py`)**: Wraps **ChromaDB**. Handles embedding generation and similarity search. Used for unstructured text and "fuzzy" matching.
-   **Graph Store (`src/core/graph_store.py`)**: Wraps **Kuzu**. Manages entities and relationships using a Cypher-like query language. Used for hard facts (e.g., "Project A depends on Project B").
-   **Conversation Context (`src/core/conversation_context.py`)**: A specialized retriever that looks at recent messages in the current session to resolve pronouns ("it", "that") and maintain continuity.

## 3. Feature Deep Dive

### 3.1 Hybrid Search & Adaptive Weighting
The most sophisticated part of Elefante is its **Adaptive Weighting** mechanism (`src/core/scoring.py`). Instead of a static formula, it analyzes the user's query to dynamically adjust the importance of each memory source:

| Query Characteristic | Detected Terms | Weight Shift | Rationale |
| :--- | :--- | :--- | :--- |
| **Pronouns** | `it`, `that`, `he`, `she` | **Conversation++** | User is referring to immediate context. |
| **Specific IDs** | `uuid`, `named`, `id` | **Graph++** | User wants precise, structured data. |
| **Questions** | `what`, `how`, `why` | **Semantic++** | User is asking for conceptual information. |
| **General** | (none of above) | **Balanced** | Standard hybrid search. |

### 3.2 Conversation Context (Short-Term Memory)
Elefante implements "Short-Term Memory" not as a separate ephemeral store, but as a **time-weighted query** over the persistent Vector DB.
-   **Mechanism**: Fetches recent messages for the current `session_id`.
-   **Scoring**:
    -   **Recency**: Exponential decay (half-life of 1 hour).
    -   **Role**: User messages > Assistant messages.
    -   **Keywords**: Overlap with current query.
-   **Benefit**: Allows the agent to answer "What did we just talk about?" without polluting the long-term graph with every trivial utterance.

### 3.3 Knowledge Graph Schema
The Kuzu implementation uses a predefined schema with:
-   **Nodes**: `Memory`, `Entity`, `Session`.
-   **Relationships**: `RELATES_TO`, `PART_OF`, `DEPENDS_ON`, `REFERENCES`, `CREATED_IN`.
-   **Integration**: Every memory added to the system creates a `Memory` node in the graph, linked to any extracted `Entity` nodes. This ensures that even unstructured text has a footprint in the structured graph.

## 4. Code Quality & Engineering

-   **Modularity**: Excellent. Storage backends are decoupled from logic. Replacing ChromaDB or Kuzu would be straightforward.
-   **Async/Await**: The entire core is asynchronous, ensuring high performance for I/O-bound database operations.
-   **Type Hinting**: Fully typed (`List`, `Optional`, `UUID`, etc.), making the code robust and easy to refactor.
-   **Testing**: The README claims 73 tests with high coverage. The structure (`tests/`) mirrors the source, which is best practice.
-   **Error Handling**: Comprehensive try/catch blocks with structured logging (`src/utils/logger.py`).

## 5. Strengths & Weaknesses

### ✅ Strengths
1.  **Privacy**: 100% local. No data is sent to OpenAI/Anthropic for storage.
2.  **Zero Cost**: Uses open-source DBs (Chroma, Kuzu) and local embeddings (likely `sentence-transformers` or similar, though I didn't check `embeddings.py` deeply, it's implied).
3.  **Smart Routing**: The adaptive weighting is a significant step up from naive RAG (Retrieval-Augmented Generation).
4.  **MCP Native**: Built specifically for the Model Context Protocol, making it "plug-and-play" for modern agents.

### ⚠️ Weaknesses / Limitations
1.  **Heuristic Context**: The "Conversation Context" relies on embedding similarity and keyword matching. It lacks a true "working memory" buffer that holds the *current* state of reasoning.
2.  **Manual Graph Construction**: Users/Agents must explicitly call `createEntity` or pass entities during `addMemory`. There is no automatic **Entity Extraction** (NER) pipeline built-in yet (though it could be added).
3.  **Deduplication Cost**: Deduplication requires generating embeddings for all candidates and computing N^2 pairwise similarities. For large result sets, this could be slow (though currently limited to small N).
4.  **No "Dreaming"**: There is no background process to consolidate memories, merge duplicate entities, or prune old data (mentioned in Roadmap Phase 3).

## 6. Conclusion
Elefante is a **high-quality, production-ready foundation** for local AI memory. It solves the "stateless agent" problem effectively by bridging the gap between fuzzy semantic search and structured knowledge graphs. Its architecture is sound, and the codebase is clean enough to serve as a reliable component in a larger AI system.
