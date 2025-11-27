# Elefante - Local AI Memory System Architecture

**Version:** 1.0.0
**Date:** 2025-11-26
**Status:** Production Ready

---

## 1. Executive Summary

**Elefante** is a local, private, and zero-cost persistent memory system designed to give AI assistants (like Bob, Cursor, Claude) stateful intelligence. It implements a **triple-layer architecture** combining semantic search (Vector DB), structured knowledge (Graph DB), and session context.

### Core Principles

- **Privacy First**: All data stored locally on user's machine.
- **Zero Cost**: Free, open-source components only.
- **Triple Intelligence**: Semantic + Structured + Contextual memory.
- **MCP Native**: Built for Model Context Protocol integration.
- **Failure-Proof**: Redundant storage, graceful degradation.

---

## 2. System Architecture Overview

```mermaid
flowchart TB
    subgraph IDE ["AI Assistant (Client)"]
        Agent[AI Agent]
        MCP_Client[MCP Client]
    end

    subgraph Elefante ["Elefante System"]
        MCP_Server[MCP Server]
        Orchestrator[Hybrid Orchestrator]

        subgraph MemoryLayers ["Memory Layers"]
            Vector[ChromaDB (Semantic)]
            Graph[Kuzu (Structured)]
            Context[Session Context]
        end

        Profile[User Profile]
    end

    Agent -->|Tool Calls| MCP_Client
    MCP_Client -->|MCP Protocol| MCP_Server
    MCP_Server -->|Route Query| Orchestrator

    Orchestrator -->|Search| Vector
    Orchestrator -->|Query| Graph
    Orchestrator -->|Filter| Context

    Orchestrator -->|Inject| Profile

    Vector -->|Results| Orchestrator
    Graph -->|Results| Orchestrator

    Orchestrator -->|Merged & Ranked| MCP_Server
    MCP_Server -->|Response| MCP_Client
```

---

## 3. Component Specifications

### 3.1 ChromaDB (Vector Database)

**Purpose**: Semantic memory for fuzzy, meaning-based retrieval.

- **Storage**: `data/chroma/`
- **Model**: `all-MiniLM-L6-v2` (Local, 384-dim)
- **Role**: Handles "vague" queries like "What did we talk about regarding Python?"

### 3.2 Kuzu Graph Database

**Purpose**: Structured memory for deterministic facts and relationships.

- **Storage**: `data/kuzu/`
- **Schema**: Nodes (`Memory`, `Entity`, `Session`) and Edges (`RELATES_TO`, `CREATED_IN`).
- **Role**: Handles specific queries like "What projects depend on Elefante?"

### 3.3 Hybrid Orchestrator

**Purpose**: The "Brain" that routes queries and merges results.

- **Adaptive Weighting**: Dynamically adjusts importance of Vector vs. Graph based on query type (e.g., "who" questions favor Graph, "about" questions favor Vector).
- **Deduplication**: Merges similar results from different sources.
- **Score Normalization**: Ensures fair ranking between different algorithms.

### 3.4 User Profiling & Episodic Memory

**Purpose**: Contextual awareness.

- **User Profile**: Automatically detects and stores user facts ("I am a developer") in a dedicated `User` node.
- **Episodic Memory**: Links every interaction to a `Session` node for temporal grounding.

---

## 4. Data Flow

### 4.1 Storing a Memory (`addMemory`)

1.  **Ingest**: Receive text content.
2.  **Embed**: Generate vector embedding locally.
3.  **Vector Store**: Save to ChromaDB.
4.  **Graph Store**: Create `Memory` node in Kuzu.
5.  **Entity Extraction**: (Optional) Create `Entity` nodes and link them.
6.  **Profile Check**: If "I" statement, link to `User` node.
7.  **Session Link**: Link to current `Session` node.

### 4.2 Searching (`searchMemories`)

1.  **Analyze**: Determine query intent (Fact? Concept? Temporal?).
2.  **Plan**: Assign weights to Vector vs. Graph.
3.  **Execute**: Run parallel queries against ChromaDB and Kuzu.
4.  **Context**: Fetch recent session history.
5.  **Merge**: Combine results, remove duplicates.
6.  **Rank**: Sort by final weighted score.
7.  **Return**: Send top N results to agent.

---

## 5. Security & Privacy

- **Local Storage**: Data never leaves `data/` directory.
- **No Telemetry**: No usage data sent to cloud.
- **Open Source**: Fully auditable code.

---

## 6. Future Roadmap (V2.0+)

- [ ] **Memory Consolidation**: Background process to summarize old memories.
- [ ] **Multi-User Support**: Namespaces for different users.
- [ ] **Visual Dashboard**: Web UI to explore the Knowledge Graph.
- [ ] **Cloud Sync**: Optional encrypted backup.
