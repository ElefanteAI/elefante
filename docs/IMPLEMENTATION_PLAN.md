# Implementation Plan - IDE Agnostic Configuration

The goal is to adapt the Elefante installation and documentation to be IDE-agnostic, specifically adding support for Antigravity and ensuring "Bob" (IBM's VS Code fork) is covered.

# Implementation Plan - Metadata Standardization & Fast Memory

## Goal

Standardize memory metadata and implement a local, efficient storage mechanism ("Fast Memory") to handle it.

## User Review Required

> [!IMPORTANT] > **Architecture Decision**: We will introduce **SQLite** as the "Fast Metadata Store".
>
> - **Why?**: SQLite is the industry standard for local, high-performance structured data. It allows for sub-millisecond retrieval of metadata by ID, session, or tag, without the overhead of vector search or graph traversal.
> - **Role**: It will serve as the "Hot Layer" for quick lookups and filtering, complementing Chroma (Semantic) and Kuzu (Relational).

## Proposed Changes

### 1. Standardized Schema (`src/models/metadata.py`)

We will extract and enhance the metadata model into a dedicated file.

#### [NEW] `src/models/metadata.py`

- Define `CoreMetadata` (timestamp, source, type).
- Define `ContextMetadata` (session_id, project, file_path).
- Define `SystemMetadata` (processing_time, version, hash).
- Combine into `StandardizedMetadata`.

### 2. Fast Metadata Store (`src/core/metadata_store.py`)

Implement a SQLite-based store.

#### [NEW] `src/core/metadata_store.py`

- **Technology**: `sqlite3` (Standard Library) + `aiosqlite` (Async).
- **Schema**:
  ```sql
  CREATE TABLE metadata (
      memory_id TEXT PRIMARY KEY,
      session_id TEXT,
      timestamp TEXT,
      type TEXT,
      json_data TEXT  -- Full metadata blob
  );
  CREATE INDEX idx_session ON metadata(session_id);
  CREATE INDEX idx_timestamp ON metadata(timestamp);
  ```
- **Methods**: `add_metadata`, `get_metadata`, `filter_metadata`.

### 3. Orchestrator Integration (`src/core/orchestrator.py`)

Update `MemoryOrchestrator` to write to the new store.

#### [MODIFY] `src/core/orchestrator.py`

- Initialize `MetadataStore`.
- In `add_memory`: Write to SQLite in parallel with Chroma/Kuzu.
- In `get_context`: Use SQLite for fast retrieval of recent session items.

## Verification Plan

### Automated Tests

- `tests/test_metadata_store.py`: Verify CRUD operations and query performance.
- `tests/test_standardization.py`: Verify Pydantic schema validation.

### Manual Verification

- [x] Run `scripts/verify_metadata_persistence.py` (created and run successfully) to verify metadata is persisted in SQLite, Vector, and Graph stores.

## User Review Required

> [!IMPORTANT]
> The automatic configuration script currently targets VS Code/Bob specifically. I will add a manual configuration section for Antigravity and other IDEs, but I will not attempt to auto-configure Antigravity as its config location is user-specific.

# Implementation Plan - Visual Control Plane ("The Chart")

## Goal

Build **Elefante Dashboard**: A local, visual control plane to explore, understand, and curate your memory graph. This answers the need for "The Chart" — a way to see your own brain.

## User Review Required

> [!IMPORTANT] > **Tech Stack Selection**: We will use **Streamlit** + **PyVis** (or `streamlit-agraph`).
>
> - **Why?**: Streamlit is the fastest way to build data apps in Python. PyVis provides interactive, physics-based graph rendering that looks "premium" and "organic", matching the "Supermemory" aesthetic better than static charts.
> - **Local Only**: The dashboard runs on `localhost:8501` and reads directly from your local Kuzu DB. No cloud.

## Proposed Changes

### 1. Dependencies

Add `streamlit` and `pyvis` (or `streamlit-agraph`) to `requirements.txt`.

### 2. The Dashboard App (`src/dashboard/app.py`)

A new module for the visual interface.

#### [NEW] `src/dashboard/app.py`

- **Layout**:
  - **Sidebar**: "Angle Selector" (Filter by Entity Type: Person, Tech, Project).
  - **Main Area**: Interactive Graph Visualization.
  - **Data Panel**: Click a node to see its full metadata/properties.
- **Logic**:
  - Connects to `KuzuGraphStore`.
  - Executes Cypher queries based on filters.
  - Converts Kuzu results -> NetworkX -> PyVis HTML.
  - Renders HTML in Streamlit.

### 3. Graph Service (`src/dashboard/graph_service.py`)

Helper class to fetch and format graph data for visualization.

- `get_graph_data(limit=100, types=[...])`: Returns nodes/edges.

## Verification Plan

### Manual Verification

- [x] **Launch**: Run `streamlit run src/dashboard/app.py`.
- [x] **Visual Check**:
  - Verify nodes appear (e.g., "User", "Python", "Elefante").
  - Verify edges link correctly (e.g., "User" -[RELATES_TO]-> "Python").
  - Test "Angle Selector" filters.

# Implementation Plan - UI Overhaul & Relationship Primitives

## Goal

1.  **UI Tremendous Improvement**: Transform the dashboard from a simple viewer to a "Reflective Control Plane" with Search, Timeline, and Deep Inspection.
2.  **Relationship Primitives**: Implement `UPDATE`, `EXTEND`, and `DERIVE` logic to make memory ingestion smarter.

## User Review Required

> [!IMPORTANT] > **UI Interaction Limit**: Streamlit + PyVis has limited bidirectional communication. Clicking a node in the graph _cannot_ easily trigger a Python callback to update the UI without full page reloads or complex hacks.
> **Workaround**: I will add a "Node Inspector" selectbox in the sidebar that is synced with the graph data. Selecting a node there will show its full details.

## Proposed Changes

### 1. Dashboard Overhaul (`src/dashboard/app.py`)

- **Search**: Add text input to filter nodes by name/content.
- **Timeline**: Add `st.slider` for `created_at` range.
- **Inspector**: Add `st.expander` or side panel to show full JSON/Metadata of selected node.
- **Visuals**: Use a distinct color palette for different entity types (e.g., User=Gold, Memory=Blue, Concept=Purple).

### 2. Memory Intelligence Pipeline (`src/core/orchestrator.py`)

> [!IMPORTANT] > **Audit Findings**: Current memories have UUID names (`memory_8c15...`) and lack tags. This makes the graph "nonsense".
> **Solution**: Ingest memories through an LLM extraction layer.

- **Step 1: Analysis (LLM)**
  - Input: Raw memory content.
  - Output: `Title` (Short summary), `Tags` (Categorization), `Facts` (Atomic statements), `Action` (ADD/UPDATE/IGNORE).
- **Step 2: Primitives (Logic)**
  - **UPDATE**: If `Action=UPDATE` or high similarity to existing node -> Merge content & tags.
  - **EXTEND**: If `Action=ADD` but related -> Create node + `RELATES_TO` edge.
  - **DERIVE**: If new facts contradict/enhance -> Create `Insight` node.
- **Step 3: Storage**
  - Store `Title` as `name` (not UUID).
  - Store `Tags` in metadata.

### 3. Cognitive Graph Ingestion (The "Soul" Upgrade)

> [!IMPORTANT] > **Strategic Shift**: We are moving from simple "Tags/Facts" to a **Cognitive Memory Model**.
> See `docs/COGNITIVE_MEMORY_MODEL.md` for the full vision.

- **Step 1: Deep Analysis (LLM)**

  - **Input**: Raw memory content.
  - **Output Schema**:
    - `Entities`: List of nodes to create/merge.
    - `Relationships`: List of edges `(Source)-[Type]->(Target)`.
    - `Emotional Context`: Valence, Arousal, Mood.
    - `Cognitive Intent`: Teaching, Venting, Planning, etc.
    - `Strategic Insight`: Actionable takeaway.

- **Step 2: Graph Execution**

## Cognitive UX Overhaul (The "Mirror")

**Goal**: Transform raw data into "Self-Understanding".
**Key Insights for Jaime**:

1.  **Alignment**: Does this memory support the "High Valuation Exit"?
2.  **State**: What was the cognitive/emotional state (Intent/Mood)?
3.  **Impact**: How does this connect to the Venture Portfolio?

### Dashboard Upgrade

- **Cognitive Card**: Replace raw JSON inspector with a rich UI component.
  - **Header**: Title + Type Icon.
  - **Badges**: Intent, Mood, Importance.
  - **Insight**: Highlighted "Strategic Insight" box.
  - **Context**: Clickable links to related entities.
- **Views**: Filter graph by "Venture" (KnownStorm vs Elefante) or "Mode" (Builder vs Father).

### Optimization & Scalability

- **Data Structure**: Ensure `CognitiveAnalysis` fields are indexed or easily accessible.
- **Performance**: Implement lazy loading for graph nodes if count > 1000.

  - **Entity Merging**: Use `MERGE` logic to avoid duplicates.
  - **Relationship Creation**: Create semantic edges (e.g., `LOVES`, `BLOCKS`, `DEPENDS_ON`) instead of generic links.
  - **Metadata Storage**: Store emotional/cognitive context in the Memory node's properties JSON.

- **Step 3: Retrieval Upgrade**
  - Update `get_context` to retrieve these rich relationships and insights, enabling the "Brain" to understand the user's worldview.

## Verification Plan

- **UI**: Visual check of Search, Timeline, and Inspector.
- **Cognitive Intelligence**:
  - Ingest a complex memory: "I'm frustrated with Python's GIL; we should switch to Rust for the core engine."
  - **Verify Graph**:
    - Nodes: `User`, `Python`, `Rust`, `GIL`, `Core Engine`.
    - Edges: `(User)-[FRUSTRATED_BY]->(GIL)`, `(User)-[PREFERS]->(Rust)`.
    - Insight: "User wants to migrate core engine to Rust for performance."
  - **Verify Metadata**: Mood="Frustrated", Intent="PLANNING".
- **Primitives**: Unit test with duplicate/related memories to verify correct primitive execution.
