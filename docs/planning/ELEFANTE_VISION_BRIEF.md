# Elefante Vision Brief: Comprehensive Implementation Guide

> **Purpose:** This document captures the cohesive larger vision of Elefante for a new agent to implement without requiring clarification. Every file, function, variable, and architectural decision is documented here.
>
> **Generated:** 2026-02-18
> **Version:** v2.0.0

---

## Table of Contents

1. [The Ultimate Purpose](#1-the-ultimate-purpose)
2. [The Three Unchangeable Laws](#2-the-three-unchangeable-laws)
3. [Architecture Overview](#3-architecture-overview)
4. [Behavioral Relevance Model](#4-behavioral-relevance-model)
5. [Memory Lifecycle Pipeline](#5-memory-lifecycle-pipeline)
6. [MCP Tools Reference](#6-mcp-tools-reference)
7. [Cognitive Retrieval System](#7-cognitive-retrieval-system)
8. [ETL Pipeline: Agent-Brain Architecture](#8-etl-pipeline-agent-brain-architecture)
9. [Compliance Gate](#9-compliance-gate)
10. [Dashboard Architecture](#10-dashboard-architecture)
11. [Data Models](#11-data-models)
12. [Key Files Reference](#12-key-files-reference)
13. [Known Pitfalls](#13-known-pitfalls)
14. [Implementation Guidance](#14-implementation-guidance)

---

## 1. The Ultimate Purpose

**Elefante is the machine-resident nervous system that allows AI agents to stop restarting and start evolving.**

The core insight:

> "The value isn't in what you store-it's in what you retrieve at the moment of need."

Elefante bridges the cognitive gap between human intent and agentic execution through **Persistent Cognitive Continuity**. It gives your agent a second brain-one that learns what matters from your behavior, not from labels you assign.

### What Elefante Does

- **Stores** facts, preferences, decisions, code patterns, and tasks
- **Searches** using hybrid retrieval: semantic vectors + knowledge graph + session context
- **Scores** every memory automatically based on recency, freshness, and reinforcement
- **Injects context** into every tool call-the agent gets relevant memories without asking
- **Builds a knowledge graph** of entities and relationships
- **Enforces quality** via a compliance gate: search before write, no duplicates
- **Visualizes** knowledge through a snapshot-driven dashboard

### Core Objectives

| Objective | Description |
|-----------|-------------|
| **Immunity** | Prevent the repetition of known failures (via Neural Registers) |
| **Efficiency** | Maximize information density; minimize repetitive discovery |
| **Trust** | Provide evidence and verification for every claim made to the user |

---

## 2. The Three Unchangeable Laws

These laws are **non-negotiable** and form the foundation of Elefante's design:

### Law 1: The Law of Continuity

> *A session is never new; it is a continuation.*

You are forbidden from acting as a "stateless" tool. You must maintain the identity, preferences, and progress of the user as established in the Second Brain.

### Law 2: The Law of Compliance (Search-Before-Action)

> *Ignorance is a choice, not a constraint.*

You MUST search the memory (`elefante-MemorySearch`) before answering or writing. Failure to check the Brain before acting is a violation of the system's foundational protocol.

### Law 3: The Law of Absolute Grounding

> *Truth is a technical artifact.*

If information is not in the Brain or the Workspace, it is **UNKNOWN**. You are forbidden from hallucinating, approximating, or assuming. If it isn't grounded, it doesn't exist.

### The Cardinal Sins

| Sin | Description |
|-----|-------------|
| **Statelessness** | Asking for information already stored in the Brain |
| **Hallucination** | Guessing a path, an API, or a user preference |
| **STDOUT Pollution** | Printing logs to the MCP command stream (kills the connection) |
| **Redundancy** | Creating a new file where an archive/augmentation path exists |

---

## 3. Architecture Overview

### Three-Layer Architecture

```
LAYER 1: MCP PROTOCOL
==============================================
IDE (VS Code, Cursor, etc.)
  |
  |  MCP stdio connection
  v
Elefante Server (Python)
  |-- 17 MCP Tools
  |-- Compliance Gate (search-before-write)
  |-- Context Injection (auto-surface memories)
  |-- Pitfall Injection (surgical warnings)

LAYER 2: INTELLIGENCE ENGINE
==============================================
Orchestrator (src/core/orchestrator.py)
  |-- ChromaDB (semantic vector search)
  |     |-- 768-dim embeddings (gte-base)
  |     |-- Cosine similarity
  |
  |-- Kuzu (knowledge graph)
  |     |-- Entity nodes (person, project, tech, etc.)
  |     |-- Relationship edges (RELATES_TO, DEPENDS_ON, etc.)
  |
  |-- Cognitive Retriever (6-signal scoring)
        |-- vector, concept, domain, coactivation, authority, temporal

LAYER 3: DASHBOARD
==============================================
FastAPI Server (src/dashboard/server.py)
  |-- Reads from snapshot file (not live DB)
  |-- LAW #1: No direct DB access from dashboard

React UI (src/dashboard/ui/)
  |-- Overview tab (health score, diagnostics)
  |-- Memories tab (searchable table)
  |-- Explore tab (topic distribution, graph)
```

### Data Flow

```
User Input
    |
    v
MCP Tool Call (elefante-MemoryAdd)
    |
    v
Compliance Gate Check (was search performed?)
    |
    v
Orchestrator.add_memory()
    |-- Parse & Classify
    |-- Integrity Check (duplicates, contradictions)
    |-- Write to ChromaDB (vector embedding)
    |-- Write to Kuzu (entity/relationship nodes)
    |
    v
Return: { status: "stored", memory_id: UUID, classification: "NEW" }
```

### Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Vector store | ChromaDB 1.3.5 | Semantic search via embeddings |
| Graph store | Kuzu 0.11.3 | Knowledge graph, Cypher queries |
| Embeddings | sentence-transformers (gte-base) | 768-dim vectors for similarity |
| Protocol | MCP 1.23.1 | IDE-server communication |
| Dashboard | React + TypeScript + Vite | Graph visualization (SVG) |
| API server | FastAPI + Uvicorn | Dashboard backend |
| Runtime | Python 3.11 | All server-side code |

---

## 4. Behavioral Relevance Model

### Core Innovation: No Manual Importance

**Nobody assigns importance. Importance emerges from behavior.**

Traditional systems ask users to rate memories (1-10). This fails because:
1. **Bias**: Users rate everything as "important" (8+)
2. **Rot**: An architecture decision from 6 months ago sits at importance=9 forever

Elefante replaces human-assigned importance with a **system-computed score (0-100)**.

### Three Behavioral Signals

| Signal | Formula | What It Measures |
|--------|---------|------------------|
| **Recency** | `exp(-decay_rate × days_since_created)` | Memories decay exponentially. Rate depends on type. |
| **Freshness** | `exp(-0.02 × days_since_accessed)` | Recently retrieved memories get boosted. Stale ones fade. |
| **Reinforcement** | `1 + 0.25 × ln(access_count + 1)` | Frequently used memories grow stronger (logarithmic). |

### Final Formula

```python
relevance = 0.5 * recency * freshness * reinforcement
```

- Returns float 0.0-1.0
- Stored as integer 0-100
- Every memory starts at score **50**

### Decay Rates by Memory Type

The decay rate (lambda) controls how quickly a memory loses relevance if never accessed. Each type has a half-life:

| Memory Type | Decay Rate | Half-Life | Why |
|-------------|------------|-----------|-----|
| `rule` | 0.002 | ~347 days | Rules persist, but die if never enforced |
| `preference` | 0.002 | ~347 days | Preferences are stable but not eternal |
| `decision` | 0.005 | ~139 days | Decisions get revisited |
| `fact` | 0.005 | ~139 days | Facts change |
| `answer` | 0.005 | ~139 days | Answers may become outdated |
| `insight` | 0.008 | ~87 days | Insights are validated or forgotten |
| `code` | 0.008 | ~87 days | Code evolves constantly |
| `hypothesis` | 0.01 | ~69 days | Hypotheses get tested |
| `question` | 0.015 | ~46 days | Questions get answered |
| `note` | 0.015 | ~46 days | Notes are transient |
| `observation` | 0.015 | ~46 days | Observations are contextual |
| `task` | 0.02 | ~35 days | Tasks complete or go stale |
| `conversation` | 0.025 | ~28 days | Conversations are ephemeral |

**Implementation:** `src/models/memory.py` - `TYPE_DECAY_RATES` dictionary

### Code Reference

```python
# src/models/memory.py - Memory.calculate_relevance_score()

def calculate_relevance_score(self, current_time: Optional[datetime] = None) -> float:
    """
    System-computed relevance (v1.10.0).
    
    Formula: relevance = 0.5 * recency * freshness * reinforcement
    Returns float 0.0-1.0 for search ranking.
    """
    import math
    
    if current_time is None:
        current_time = datetime.utcnow()
    
    days_since_created = max(0, (current_time - self.metadata.created_at).total_seconds() / 86400)
    days_since_access = max(0, (current_time - self.metadata.last_accessed).total_seconds() / 86400)
    access_count = max(0, self.metadata.access_count)
    
    # Recency: exponential decay based on memory type
    recency = math.exp(-self.metadata.decay_rate * days_since_created)
    
    # Freshness: decays if not recently retrieved
    freshness = math.exp(-0.02 * days_since_access)
    
    # Reinforcement: grows with repeated access (logarithmic)
    reinforcement = 1.0 + (self.metadata.reinforcement_factor * math.log(access_count + 1))
    
    raw = 0.5 * recency * freshness * reinforcement
    return min(1.0, max(0.0, raw))
```

---

## 5. Memory Lifecycle Pipeline

### 5-Step Pipeline (v1.10.0)

When `elefante-MemoryAdd` is called, the orchestrator executes this pipeline:

```
STEP 1: PARSE & CLASSIFY
==============================================
|-- Validate content (min 1 char, max 10000)
|-- Extract title (from metadata or generate)
|-- Detect test artifacts (block unless ELEFANTE_ALLOW_TEST_MEMORIES=1)
|-- Set decay_rate from memory_type

STEP 2: INTEGRITY (Duplicate & Contradiction Check)
==============================================
|-- Generate embedding
|-- Search for similar memories (min_similarity=0.65)
|-- Classify relationship:
|     |-- score >= 0.95 + near_duplicate -> REDUNDANT
|     |-- score >= 0.75 + contradiction -> CONTRADICTORY (fact vs fact)
|     |-- score >= 0.75 + no contradiction -> RELATED
|     |-- else -> NEW
|-- Branch on memory_class:
|     |-- fact vs fact: CONTRADICTORY (old must be superseded)
|     |-- directive/state: RELATED (coexist, resolved at retrieval)

STEP 3: WRITE (Construct Memory Object)
==============================================
|-- Create MemoryMetadata with V2.0 schema
|-- Set score = 50 (everyone starts equal)
|-- Extract concepts (deterministic, no LLM)
|-- Infer surfaces_when (query patterns)
|-- Compute initial authority_score
|-- Set processing_status = "raw"

STEP 4: REINFORCE (Update Access Stats)
==============================================
|-- If memory exists (title match):
|     |-- Increment access_count
|     |-- Update last_accessed
|     |-- Return existing memory

STEP 5: GRAPH LINKS (Create Entities & Relationships)
==============================================
|-- For each entity in request:
|     |-- Create or get entity (dedup by name+type)
|     |-- Create relationship: Memory -> RELATES_TO -> Entity
|-- Link to User entity if first-person statement detected
```

### Memory Status Transitions

```
NEW -> REDUNDANT (if duplicate found)
NEW -> CONTRADICTORY (if fact conflicts with existing fact)
NEW -> RELATED (if similar but not duplicate)
REDUNDANT -> DEPRECATED (via refinery cleanup)
CONTRADICTORY -> DEPRECATED (old fact superseded by new)
```

### Memory Class Behavior

| Class | Behavior Under Contradiction |
|-------|------------------------------|
| `fact` | Newer supersedes older. Objective truth. |
| `directive` | Coexists. User preference/instruction. Resolved by recency at retrieval. |
| `state` | Coexists. Ephemeral condition (mood, energy). Most recent wins. |

### Preference Re-Assertion Merge

When a preference is re-asserted (similarity >= 0.40 + meaningful keyword overlap):

```python
# Merge behavior:
merged_content = existing.content + "\n\nReasserted (DATE): new.content"
merged_tags = union(existing.tags, new.tags)
reinforcements.append({ "at": timestamp, "content": new.content[:200] })
```

---

## 6. MCP Tools Reference

### 17 Tools + 2 Prompts

All tool names follow `elefante-PascalCase` convention.

#### Memory Tools

| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `elefante-MemoryAdd` | Store a new memory | `content`, `memory_type`, `memory_class`, `domain`, `category`, `tags`, `entities`, `force_new` |
| `elefante-MemorySearch` | Search memories | `query`, `mode` (semantic/structured/hybrid), `limit`, `filters`, `list_all` |
| `elefante-MemoryUpdate` | Amend a memory in-place | `memory_id`, `content`, `deprecated`, `archived`, `supersedes_id`, `tags` |
| `elefante-MemoryDelete` | Permanently delete with audit trail | `memory_id`, `reason` |
| `elefante-MemoryConsolidate` | Deterministic cleanup | `force` (dry-run by default) |

#### Knowledge Graph Tools

| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `elefante-GraphConnect` | Batch upsert entities and relationships | `entities`, `relationships`, `include_system_status` |
| `elefante-GraphQuery` | Execute raw Cypher queries | `cypher_query` |

#### Context & Session Tools

| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `elefante-ContextGet` | Get full context for session/task | `session_id`, `depth` (1-5), `limit` |
| `elefante-SessionsList` | List past sessions | `limit`, `offset` |

#### Task Tools

| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `elefante-TaskCreate` | Create task with optional subtasks | `description`, `parent_id`, `blocked_by`, `priority`, `assigned_agent`, `subtasks` |
| `elefante-TaskUpdate` | Update task status/output | `task_id`, `status`, `output` |
| `elefante-TaskGraph` | View task hierarchy | `task_id` (optional, returns roots if None) |

#### ETL Tools

| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `elefante-ETLProcess` | Get raw memories for agent classification | `limit`, `include_stats` |
| `elefante-ETLClassify` | Apply agent's classification | `memory_id`, `ring`, `knowledge_type`, `topic`, `summary`, `owner_id` |

#### System Tools

| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `elefante-System` | Enable/disable Elefante Mode | `action` ("enable" / "disable"), `force` |
| `elefante-SystemStatusGet` | Get system health and stats | None |
| `elefante-DashboardOpen` | Open knowledge graph dashboard | `refresh` (true/false) |

#### Prompts

| Prompt | Purpose |
|--------|---------|
| `elefante-grounding` | Inject memory-aware behavior into agent's system prompt |
| `elefante-context` | Search memories for a topic and return as context |

### Tool Schemas (Key Excerpts)

#### elefante-MemoryAdd

```json
{
  "properties": {
    "content": { "type": "string", "description": "The memory content to store" },
    "memory_type": {
      "type": "string",
      "enum": ["conversation", "fact", "insight", "code", "decision", "task", "note", "preference"],
      "default": "conversation"
    },
    "memory_class": {
      "type": "string",
      "enum": ["fact", "directive", "state"],
      "default": "fact"
    },
    "domain": {
      "type": "string",
      "enum": ["work", "personal", "learning", "project", "reference", "system"]
    },
    "category": { "type": "string" },
    "tags": { "type": "array", "items": { "type": "string" } },
    "entities": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": { "type": "string" },
          "type": { "type": "string" }
        },
        "required": ["name", "type"]
      }
    },
    "force_new": { "type": "boolean", "default": false }
  },
  "required": ["content"]
}
```

#### elefante-MemorySearch

```json
{
  "properties": {
    "query": { "type": "string" },
    "mode": {
      "type": "string",
      "enum": ["semantic", "structured", "hybrid"],
      "default": "hybrid"
    },
    "limit": { "type": "integer", "default": 10, "minimum": 1, "maximum": 100 },
    "filters": {
      "type": "object",
      "properties": {
        "memory_type": { "type": "string" },
        "domain": { "type": "string" },
        "category": { "type": "string" },
        "min_score": { "type": "integer", "minimum": 0, "maximum": 100 },
        "tags": { "type": "array", "items": { "type": "string" } },
        "start_date": { "type": "string", "format": "date-time" },
        "end_date": { "type": "string", "format": "date-time" }
      }
    },
    "min_similarity": { "type": "number", "default": 0.3 },
    "list_all": { "type": "boolean", "default": false },
    "offset": { "type": "integer", "default": 0 }
  },
  "required": ["query"]
}
```

---

## 7. Cognitive Retrieval System

### 6-Signal Scoring (V4)

The `CognitiveRetriever` class in `src/core/retrieval.py` implements multi-signal scoring:

| Signal | Weight | What It Measures |
|--------|--------|------------------|
| `vector_similarity` | 0.30 | Semantic match via embeddings |
| `concept_overlap` | 0.20 | Jaccard-like shared concepts |
| `domain_match` | 0.15 | Same domain (work/personal/etc) |
| `coactivation` | 0.15 | Co-retrieval history |
| `authority` | 0.10 | Score x access count |
| `temporal` | 0.10 | Recency + freshness |

### Composite Score Formula

```python
composite_score = (
    0.30 * vector_score +
    0.20 * concept_score +
    0.15 * domain_score +
    0.15 * coactivation_score +
    0.10 * authority_score +
    0.10 * temporal_score
)
```

### Data Classes

```python
@dataclass
class MemoryCandidate:
    id: str
    content: str
    title: str
    summary: str
    concepts: list[str]
    domain: str
    importance: int  # maps to metadata.score (0-100)
    access_count: int
    created_at: datetime
    last_accessed: datetime
    embedding: Optional[list[float]] = None
    
    # Computed scores
    vector_score: float = 0.0
    concept_score: float = 0.0
    domain_score: float = 0.0
    coactivation_score: float = 0.0
    authority_score: float = 0.0
    composite_score: float = 0.0
    
    # Role in constellation
    role: str = "candidate"  # primary, supporting, contradicting, context

@dataclass
class MemoryConstellation:
    """Structured retrieval result - not a flat list."""
    primary: Optional[MemoryCandidate] = None
    supporting: list[MemoryCandidate] = field(default_factory=list)
    contradicting: list[MemoryCandidate] = field(default_factory=list)
    context: list[MemoryCandidate] = field(default_factory=list)
    synthesis: str = ""

@dataclass
class RetrievalExplanation:
    """V5 Feature: Every search result includes WHY it surfaced."""
    composite_score: float
    signals: list[dict] = field(default_factory=list)
```

### Query Analysis

```python
@dataclass
class QueryAnalysis:
    raw_query: str
    concepts: list[str]  # extracted via extract_concepts()
    inferred_domain: Optional[str] = None
    inferred_intent: Optional[str] = None  # troubleshoot, learn, decide, remember
    embedding: Optional[list[float]] = None
```

### Intent Detection

```python
# Deterministic intent inference (no LLM)
if any(w in query_lower for w in ["error", "bug", "fix", "problem", "issue"]):
    intent = "troubleshoot"
elif any(w in query_lower for w in ["how", "learn", "what is", "explain"]):
    intent = "learn"
elif any(w in query_lower for w in ["decide", "choose", "should i", "which"]):
    intent = "decide"
else:
    intent = "remember"
```

---

## 8. ETL Pipeline: Agent-Brain Architecture

### Core Principle: Elefante is LLM-Free

Elefante does NOT make internal LLM calls. All classification is either:
1. **Deterministic** (via `src/utils/curation.py` helpers)
2. **Agent-driven** (via ETL tools that let the agent's LLM do the work)

### Two-Phase Memory Ingestion

```
PHASE 1: INGEST (elefante-MemoryAdd)
==============================================
|-- Fast, non-blocking raw storage
|-- Returns immediately with processing_status="raw"
|-- No V5 topology fields set yet

PHASE 2: PROCESS (Agent-Driven)
==============================================
|-- Agent calls elefante-ETLProcess
|     |-- Returns raw memories for agent to classify
|
|-- Agent's LLM classifies each memory:
|     |-- ring: core | domain | topic | leaf
|     |-- knowledge_type: law | principle | method | decision | insight | preference | fact
|     |-- topic: coding-standards | communication | workflow | agent-behavior | tools-environment | collaboration | general
|     |-- summary: one-line description
|
|-- Agent calls elefante-ETLClassify
|     |-- System updates memory with classification
|     |-- processing_status -> "processed"
```

### Processing Status Lifecycle

```python
class ProcessingStatus:
    RAW = "raw"              # Just ingested, awaiting agent classification
    PROCESSING = "processing" # Handed to agent for classification
    PROCESSED = "processed"   # Agent classified, fully placed in topology
    FAILED = "failed"         # Classification failed
```

### V5 Topology Fields

| Field | Values | Purpose |
|-------|--------|---------|
| `ring` | core, domain, topic, leaf | Distance from user's core concerns |
| `knowledge_type` | law, principle, method, decision, insight, preference, fact | Nature of knowledge |
| `topic` | coding-standards, communication, workflow, agent-behavior, tools-environment, collaboration, general | Subject area |
| `summary` | One-line description | Quick reference |
| `owner_id` | Default: "owner-jay" | Attribution |

---

## 9. Compliance Gate

### Purpose

Mechanical enforcement of search-before-write to prevent duplicates and ensure context awareness.

### Gated Tools

```python
GATED_TOOLS = {
    "elefante-MemoryAdd",
    "elefante-MemoryUpdate",
    "elefante-MemoryDelete",
    "elefante-GraphConnect",
}
```

### Gate Logic

```python
def _check_compliance_gate(self, tool_name: str) -> Dict[str, Any] | None:
    # Not a gated tool -> pass
    if tool_name not in GATED_TOOLS:
        return None
    
    # Search was performed -> pass
    if self._compliance_state["search_performed"]:
        return None
    
    # GATE BLOCKED
    return {
        "success": False,
        "error": "COMPLIANCE GATE: Search required before write operations.",
        "gate_status": "BLOCKED",
        "action_required": "Call elefante-MemorySearch first",
        "blocked_tool": tool_name
    }
```

### Gate State

```python
self._compliance_state = {
    "search_performed": False,
    "search_count": 0,
    "search_timestamp": None,
    "last_query": None
}
```

### Unlocking the Gate

After `elefante-MemorySearch` is called:

```python
self._compliance_state["search_performed"] = True
self._compliance_state["search_count"] = len(results)
self._compliance_state["search_timestamp"] = datetime.utcnow()
self._compliance_state["last_query"] = query
```

---

## 10. Dashboard Architecture

### LAW #1: Dashboard Does NOT Access Live Databases

The dashboard reads from a **snapshot file**, not directly from ChromaDB or Kuzu. This prevents lock conflicts with the MCP server.

```
Dashboard Server (FastAPI)
    |
    |  Reads from
    v
~/.elefante/data/dashboard_snapshot.json
    |
    |  Generated by
v
scripts/update_dashboard_data.py
```

### Snapshot Generation

Run manually or via `elefante-DashboardOpen(refresh=true)`:

```bash
python scripts/update_dashboard_data.py
```

This script:
1. Fetches ALL memories from ChromaDB
2. Fetches entities and relationships from Kuzu
3. Computes semantic similarity edges (optional)
4. Writes to `dashboard_snapshot.json`

### Dashboard Server

```python
# src/dashboard/server.py

@app.get("/api/graph")
async def get_graph(limit: int = 1000):
    """Fetch graph data from pre-generated snapshot file."""
    snapshot_path = Path(cfg.elefante.data_dir) / "dashboard_snapshot.json"
    
    with open(snapshot_path, "r") as f:
        data = json.load(f)
    
    return {
        "nodes": data["nodes"],
        "edges": data["edges"],
        "stats": data["stats"]
    }
```

### Dashboard Tabs

| Tab | Purpose |
|-----|---------|
| **Overview** | Health score (freshness, coverage, connectivity) with diagnostic panels |
| **Memories** | Searchable, sortable table with semantic search integration |
| **Explore** | Topic distribution, memory insights, and knowledge graph visualization |

---

## 11. Data Models

### Memory Model (V2.0 Schema)

```python
class Memory(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    content: str = Field(..., min_length=1, max_length=10000)
    metadata: MemoryMetadata = Field(default_factory=MemoryMetadata)
    embedding: Optional[List[float]] = None
    related_entities: List[UUID] = Field(default_factory=list)
    similarity_score: Optional[float] = None
    relevance_score: Optional[float] = None
```

### MemoryMetadata Model

```python
class MemoryMetadata(BaseModel):
    # Identity
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = "user"
    
    # Classification
    domain: DomainType = DomainType.REFERENCE
    category: str = "general"
    memory_type: MemoryType = MemoryType.CONVERSATION
    memory_class: MemoryClass = MemoryClass.FACT
    
    # Relevance (system-computed)
    score: int = Field(default=50, ge=0, le=100)
    urgency: int = Field(default=5, ge=0, le=10)
    intent: IntentType = IntentType.REFERENCE
    confidence: float = Field(default=0.7)
    tags: List[str] = Field(default_factory=list)
    
    # V4 Cognitive Retrieval
    concepts: List[str] = Field(default_factory=list)
    surfaces_when: List[str] = Field(default_factory=list)
    co_activated_with: List[UUID] = Field(default_factory=list)
    authority_score: float = Field(default=0.5)
    contradicts: List[UUID] = Field(default_factory=list)
    supports: List[UUID] = Field(default_factory=list)
    
    # Relationship Tracking
    status: MemoryStatus = MemoryStatus.NEW
    relationship_type: Optional[RelationshipType] = None
    supersedes_id: Optional[UUID] = None
    superseded_by_id: Optional[UUID] = None
    
    # Temporal Intelligence
    last_accessed: datetime = Field(default_factory=datetime.utcnow)
    access_count: int = 0
    decay_rate: float = 0.01
    reinforcement_factor: float = 0.25
    
    # Lifecycle
    deprecated: bool = False
    archived: bool = False
    
    # Extensibility
    custom_metadata: Dict[str, Any] = Field(default_factory=dict)
```

### Entity Model

```python
class Entity(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    type: EntityType
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    properties: Dict[str, Any] = Field(default_factory=dict)

class EntityType(str, Enum):
    PERSON = "person"
    PROJECT = "project"
    TECHNOLOGY = "technology"
    CONCEPT = "concept"
    FILE = "file"
    ORGANIZATION = "organization"
    LOCATION = "location"
    EVENT = "event"
    TOPIC = "topic"
    MEMORY = "memory"
    SESSION = "session"
    TASK = "task"
```

### Relationship Model

```python
class Relationship(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    from_entity_id: UUID
    to_entity_id: UUID
    relationship_type: RelationshipType
    strength: float = 1.0
    properties: Dict[str, Any] = Field(default_factory=dict)

class RelationshipType(str, Enum):
    # Additive
    EXTENDS = "extends"
    SUPPORTS = "supports"
    IMPLEMENTS = "implements"
    
    # Transformative
    REFINES = "refines"
    SUPERSEDES = "supersedes"
    CONSOLIDATES = "consolidates"
    
    # Conflictual
    CONTRADICTS = "contradicts"
    CHALLENGES = "challenges"
    
    # Structural
    DEPENDS_ON = "depends_on"
    PART_OF = "part_of"
    REFERENCES = "references"
    RELATES_TO = "relates_to"
    
    # Temporal
    FOLLOWS = "follows"
    PRECEDES = "precedes"
    UPDATES = "updates"
```

---

## 12. Key Files Reference

### Core Files

| File | Purpose | Key Classes/Functions |
|------|---------|------------------------|
| `src/mcp/server.py` | MCP server implementation | `ElefanteMCPServer`, tool handlers, compliance gate |
| `src/core/orchestrator.py` | Central intelligence layer | `MemoryOrchestrator`, `add_memory()`, `search_memories()` |
| `src/core/vector_store.py` | ChromaDB integration | `VectorStore`, `search()`, `add_memory()` |
| `src/core/graph_store.py` | Kuzu integration | `GraphStore`, `create_or_get_entity()`, `execute_query()` |
| `src/core/retrieval.py` | Cognitive retrieval | `CognitiveRetriever`, `MemoryCandidate`, `MemoryConstellation` |
| `src/core/embeddings.py` | Local embeddings | `EmbeddingService`, `generate_embedding()` |
| `src/core/etl.py` | Agent-driven ETL | `ETLProcessor`, `get_raw_memories()`, `apply_classification()` |
| `src/core/refinery.py` | Memory cleanup | `MemoryRefinery`, `build_refinery_plan()` |
| `src/models/memory.py` | Data models | `Memory`, `MemoryMetadata`, `TYPE_DECAY_RATES` |
| `src/utils/config.py` | Configuration | `Config`, `get_config()` |
| `src/utils/curation.py` | Deterministic helpers | `extract_concepts()`, `generate_title()`, `generate_summary()` |

### Dashboard Files

| File | Purpose |
|------|---------|
| `src/dashboard/server.py` | FastAPI server |
| `src/dashboard/ui/src/App.tsx` | Main React component |
| `src/dashboard/ui/src/components/OverviewTab.tsx` | Health diagnostics |
| `src/dashboard/ui/src/components/MemoriesTab.tsx` | Memory table |
| `src/dashboard/ui/src/components/KnowledgeGraph.tsx` | Graph visualization |

### Script Files

| File | Purpose |
|------|---------|
| `scripts/install.py` | Unified installation |
| `scripts/update_dashboard_data.py` | Snapshot generation |
| `scripts/health_check.py` | System diagnostics |
| `scripts/factory_reset.py` | Complete data wipe |

### Documentation Files

| File | Purpose |
|------|---------|
| `docs/the-core.md` | The Three Laws |
| `docs/README.md` | Main documentation |
| `docs/pitfall-index.md` | Quick reference for known issues |
| `docs/technical/usage.md` | Complete tool reference |
| `docs/debug/README.md` | Debugging guide |

---

## 13. Known Pitfalls

### From `docs/pitfall-index.md`

| Category | Pitfall | Quick Fix |
|----------|---------|-----------|
| Dashboard | Browser cache | `Ctrl+Shift+R` (hard refresh) |
| Dashboard | Snapshot stale | Run `python scripts/update_dashboard_data.py` |
| Dashboard | Kuzu lock conflict | Kill Python processes, remove `kuzu_db/.lock` |
| Installation | Kuzu pre-existing dir | Do NOT mkdir before Kuzu init |
| MCP | Type signature | Use `list[types.Tool]` not `List[Tool]` |
| MCP | STDOUT pollution | Redirect all prints to `sys.stderr` |
| Database | Reserved word | Use `props` not `properties` |
| Memory | Export API | Use `collection._collection.get()` for full export |
| Documentation | Archive without index | Update ALL READMEs that link to moved files |

### Critical Warnings

1. **Never print to stdout in MCP server** - This corrupts the JSON-RPC protocol and kills the connection.

2. **Never pre-create Kuzu database directory** - Kuzu 0.11+ creates its own structure. An empty directory blocks initialization.

3. **Always search before write** - The compliance gate blocks write operations until a search is performed.

4. **Dashboard reads from snapshot** - After adding memories, refresh the snapshot to see changes.

---

## 14. Implementation Guidance

### For New Agents

1. **Start with the Three Laws** - Read `docs/the-core.md` first. These are non-negotiable.

2. **Understand Behavioral Relevance** - The score is system-computed. Never let users assign importance.

3. **Respect the Compliance Gate** - Always call `elefante-MemorySearch` before write operations.

4. **Use Deterministic Helpers** - `src/utils/curation.py` provides LLM-free concept extraction, title generation, etc.

5. **Follow the ETL Pattern** - Elefante is LLM-free. Classification happens via agent-driven ETL tools.

6. **Check Pitfalls First** - Before any task, search `docs/pitfall-index.md` for relevant warnings.

### Key Implementation Files by Feature Area

| Feature Area | Primary File | Secondary Files |
|--------------|--------------|-----------------|
| Memory storage | `src/core/orchestrator.py` | `src/core/vector_store.py`, `src/core/graph_store.py` |
| Search/retrieval | `src/core/retrieval.py` | `src/core/scoring.py`, `src/core/deduplication.py` |
| MCP tools | `src/mcp/server.py` | `src/core/orchestrator.py` |
| Dashboard | `src/dashboard/server.py` | `scripts/update_dashboard_data.py` |
| Configuration | `src/utils/config.py` | `config.yaml` |
| Cleanup/maintenance | `src/core/refinery.py` | `scripts/golden_cleanup.py` |

### Testing Approach

1. **Unit tests** should mock database connections
2. **Integration tests** should use temporary database paths
3. **E2E tests** should set `ELEFANTE_ALLOW_TEST_MEMORIES=1`
4. **Always verify** with `scripts/health_check.py` after changes

---

## Appendix: Complete Tool Response Format

### elefante-MemoryAdd Response

```json
{
  "status": "stored",
  "classification": "NEW",
  "entity_count": 2,
  "relationship_count": 2,
  "embedding_id": "uuid-string",
  "graph_ids": ["uuid-string"],
  "score": 50,
  "memory_type": "preference",
  "memory_id": "uuid-string"
}
```

### elefante-MemorySearch Response

```json
{
  "success": true,
  "count": 5,
  "results": [
    {
      "memory": {
        "id": "uuid",
        "content": "...",
        "metadata": { ... }
      },
      "score": 0.85,
      "source": "hybrid"
    }
  ],
  "compliance_stamp": "[ELEFANTE] Searched: Found 5 relevant memories",
  "gate_status": "UNLOCKED"
}
```

---

**END OF VISION BRIEF**

*This document is self-contained. A new agent can implement Elefante features using only this reference.*