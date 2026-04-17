# Usage Guide & API Reference (v2.9.3)

## 1. Natural Language Interaction

Once connected to your IDE, use natural language to interact with Elefante. The agent maps intent to the correct MCP tool or prompt.

**Examples**:

- **Store info**: "Remember that I prefer using async/await over callbacks."
- **Retrieve context**: "What do you know about my coding preferences?"
- **Graph query**: "Show me all technologies related to the Elefante project."
- **Browse sessions**: "Show me my recent work sessions."
- **Open dashboard**: "Open the knowledge graph dashboard."

---

## 2. Current MCP Surface

Elefante exposes **20 tools** and **2 prompts**.

- **Tools** read, write, or inspect the system.
- **Prompts** inject grounding or pre-fetched memory context into the model. They are not tools.
- **Source of truth**: `src/mcp/server.py`

**Critical workflow rule**:

- Call `elefante-MemorySearch` before `elefante-MemoryAdd`, `elefante-MemoryUpdate`, `elefante-MemoryDelete`, or `elefante-GraphConnect`.

**Tool response contract**:

- Every tool response injects `ENTRYPOINT_SEQUENCE_READ_THIS_FIRST`, `MANDATORY_PROTOCOLS_READ_THIS_FIRST`, `DIRECTIVES`, and `TOKEN_STATS`.
- Some responses also inject `RELEVANT_CONTEXT` when Elefante can surface related memories automatically.
- `ENTRYPOINT_SEQUENCE_READ_THIS_FIRST` is the exact developer/debug routing path for repository work: Known Issues -> verification command -> compendium -> maintained test surface.
- `RELEVANT_CONTEXT` is conditional, not universal. It is skipped for tools that already return memory-heavy data, and when present it contains a short `note` plus a `memories` list of summarized snippets rather than full raw memory payloads.
- `TOKEN_STATS` is injected into every tool response. It tells the agent what each tool call costs in tokens. Fields:
  - `output_tokens` (int): Total tokens in the response, including protocol overhead and the TOKEN_STATS block itself.
  - `overhead_tokens` (int): Tokens consumed by protocol injection (MANDATORY_PROTOCOLS, DIRECTIVES, ENTRYPOINT_SEQUENCE) plus TOKEN_STATS itself. Not content the agent requested.
  - `signal_ratio` (float, 0.0-1.0): Fraction of output that is actual payload. `1.0` = zero overhead, `0.0` = all overhead. Higher is better.

**Token intelligence on `elefante-MemoryAdd`**:

- `elefante-MemoryAdd` responses include `content_tokens` (estimated token count of the stored content) and `token_density` (ratio of actual tokens to the type's budget). When density exceeds 2.0x, a `density_warning` string is included advising the caller to trim or split the memory.
- Token budgets are proportional to memory type lifespan: `specification` (800), `insight` (500), `decision` (400), `preference` (300), `fact` (250), `directive` (200), `note` (150), `conversation` (100).

### Core Memory Operations

#### `elefante-MemoryAdd`

**Purpose**: Store a new memory.

**Why this exists**: Elefante's session context is not durable. If a user makes a real decision, preference, or rule, it must be stored explicitly or it disappears on restart.

**Why `memory_type` matters**: This is not cosmetic metadata. It changes decay, ranking, and lifespan.

- `specification` and `directive` never decay.
- `note` and `conversation` decay quickly.
- Wrong type = wrong behavior later.

**Parameters**:

- `content` (required, string): The memory content to store.
- `memory_type` (optional, string, default `fact`): `fact`, `decision`, `preference`, `insight`, `note`, `conversation`, `specification`, or `directive`.
- `domain` (optional, string): `work`, `personal`, `learning`, `project`, `reference`, or `system`.
- `category` (optional, string): Topic grouping such as `elefante`, `python`, or `user-preferences`.
- `tags` (optional, string[]): Tags for filtering and retrieval.
- `entities` (optional, object[]): Graph links as `{name, type}` objects.
- `metadata` (optional, object): Additional structured metadata.
- `force_new` (optional, boolean, default `false`): Always create a new record and bypass deduplication.

**Important**:

- `force_new=true` should be rare. It skips title deduplication, preference merge, and high-similarity redundancy checks.
- Use `specification` for durable architecture or contract truths.
- Use `directive` for rules that must not fade.
- Use `note` only for short-lived context.

**Example**:

```json
{
  "content": "I prefer using async/await over callbacks",
  "memory_type": "preference",
  "domain": "work",
  "category": "python",
  "tags": ["coding-style", "async"],
  "entities": [
    { "name": "Python", "type": "technology" },
    { "name": "async/await", "type": "concept" }
  ]
}
```

#### `elefante-MemorySearch`

**Purpose**: Retrieve memories using semantic, structured, or hybrid search.

**Why this exists**: Elefante cannot infer vague references. Search quality depends on explicit entities, not pronouns.

**Query rule**:

- Rewrite vague queries before search.
- Replace pronouns like `it`, `that`, `this`, `he`, `she`, and `they` with real names, systems, files, or concepts.

**Parameters**:

- `query` (required, string): Explicit, standalone search query.
- `mode` (optional, string, default `hybrid`): `semantic`, `structured`, or `hybrid`.
- `limit` (optional, integer, default `10`, min `1`, max `100`): Maximum results to return.
- `filters` (optional, object): Filter by `memory_type`, `domain`, `category`, `min_score`, `tags`, `start_date`, or `end_date`.
- `min_similarity` (optional, number, default `0.3`, min `0.0`, max `1.0`): Minimum semantic similarity threshold.
- `include_conversation` (optional, boolean, default `true`): Include recent conversation context.
- `include_stored` (optional, boolean, default `true`): Include stored memories from ChromaDB and Kuzu.
- `session_id` (optional, string): Session UUID. Required when `include_conversation=true` and the caller needs session-scoped context.
- `list_all` (optional, boolean, default `false`): Bypass semantic ranking and enumerate stored memories for inspection or export.
- `offset` (optional, integer, default `0`, min `0`): Pagination offset used with `list_all=true`.

**Important**:

- Use normal search for questions, context retrieval, and compliance-gate workflows.
- Use `list_all=true` for browsing or exports such as "show me all memories about X".
- `list_all=true` is browse mode, not relevance search. It does not replace a targeted search when you need write-safe context.

**Example**:

```json
{
  "query": "preferences for Python development",
  "mode": "hybrid",
  "limit": 5,
  "filters": {
    "memory_type": "preference"
  }
}
```

#### `elefante-MemoryUpdate`

**Purpose**: Amend an existing memory in place.

**Why this exists**: If a stored fact is wrong or outdated, the system should correct the record, not bury the error under another memory.

**Parameters**:

- `memory_id` (required, string): UUID of the memory to update.
- `content` (optional, string): Replacement content. Triggers re-embedding.
- `deprecated` (optional, boolean): Exclude the memory from normal search.
- `archived` (optional, boolean): Archive the memory.
- `supersedes_id` (optional, string): UUID of the older memory this one replaces.
- `tags` (optional, string[]): Replacement tags.

**Important**:

- Requires prior `elefante-MemorySearch`.
- Prefer `MemoryUpdate` over `MemoryAdd` when a decision changes.

#### `elefante-MemoryDelete`

**Purpose**: Permanently delete a memory.

**Why this exists**: Some information must be removed, not just deprioritized. Examples: harmful facts, bad test data, or false records.

**Parameters**:

- `memory_id` (required, string): UUID of the memory to delete.
- `reason` (required, string): Audit-trail reason for deletion.

**Important**:

- Requires prior `elefante-MemorySearch`.
- Use this for true deletion, not normal versioning. If the old fact should remain historically visible, prefer `MemoryUpdate` with `deprecated` or `supersedes_id`.

#### `elefante-MemoryConsolidate`

**Purpose**: Deduplicate and canonicalize stored memories.

**Why this exists**: Over time, memories can drift into redundant or test-only states. Consolidation keeps exports and retrieval clean.

**Parameters**:

- `force` (optional, boolean, default `false`): Apply changes. Default behavior is dry-run only.

**Important**:

- Start with `force=false`.
- Use this for maintenance, not for routine single-memory edits.

---

### Knowledge Graph Operations

#### `elefante-GraphConnect`

**Purpose**: Batch upsert entities and relationships in one call.

**Why this exists**: Graph writes are safer and cheaper when the entire mini-topology is sent together. This reduces duplicate nodes and broken edges.

**Parameters**:

- `entities` (optional, object[]): Entities to upsert.
  - `ref` (required): Local reference key such as `user`, `project`, or `repo`.
  - `id` (optional): Existing entity UUID.
  - `name` (optional): Entity name. Required if `id` is not provided.
  - `type` (optional): Entity type. Required if `id` is not provided.
  - `properties` (optional): Additional entity properties.
- `relationships` (optional, object[]): Relationships to create.
  - `from_ref` / `to_ref` (optional): Connect by local refs.
  - `from_entity_id` / `to_entity_id` (optional): Connect by existing UUIDs.
  - `relationship_type` (required): Relationship type.
  - `properties` (optional): Additional relationship properties.
- `include_system_status` (optional, boolean, default `false`): Include `elefante-SystemStatusGet` output in the response.

**Important**:

- Requires prior `elefante-MemorySearch`.
- Use stable names and refs so repeated calls stay idempotent.
- Use `id` when updating an existing entity rather than creating a near-duplicate.
- Prefer enum-aligned values from `src/models/entity.py` such as `PERSON`, `PROJECT`, `FILE`, `CONCEPT`, `TECHNOLOGY`, `TASK`, `SPECIFICATION`, and `DIRECTIVE`. Common relationship values include `RELATES_TO`, `DEPENDS_ON`, `PART_OF`, `CREATED_BY`, `USES`, `BLOCKS`, `REFERENCES`, `WORKS_ON`, `GOVERNS`, `ENFORCES`, `SUPERSEDES`, and `CONTRADICTS`.

**Example**:

```json
{
  "entities": [
    { "name": "Jay", "type": "PERSON", "ref": "user" },
    { "name": "Elefante", "type": "PROJECT", "ref": "proj" }
  ],
  "relationships": [
    { "from_ref": "user", "to_ref": "proj", "relationship_type": "CREATED_BY" }
  ]
}
```

#### `elefante-GraphQuery`

**Purpose**: Execute raw Cypher queries on the Kuzu knowledge graph.

**Why this exists**: Some graph questions are too specific for fixed tools, such as path discovery, relationship analysis, or topology inspection.

**Parameters**:

- `cypher_query` (required, string): Cypher query text.
- `parameters` (optional, object): Parameter values for the query.

**Important**:

- Prefer parameterized queries over string interpolation.
- Use this when you need graph structure, not semantic memory search.

---

### Context and Sessions

#### `elefante-ContextGet`

**Purpose**: Retrieve a larger context bundle of memories plus graph connections.

**Why this exists**: Sometimes top-N search is not enough. You need surrounding relationships and a wider context window before deciding or answering.

**Parameters**:

- `session_id` (optional, string): Session UUID when the caller wants context tied to a specific session.
- `depth` (optional, integer, default `2`, min `1`, max `5`): Graph traversal depth.
- `limit` (optional, integer, default `50`, min `1`, max `200`): Maximum memories to retrieve.

**Important**:

- Use `ContextGet` for broad grounding.
- Use `MemorySearch` for targeted lookup.

#### `elefante-SessionsList`

**Purpose**: List recent work sessions.

**Why this exists**: Sessions provide a time-based view of what happened, separate from semantic memory retrieval.

**Parameters**:

- `limit` (optional, integer, default `10`): Number of sessions to return.
- `offset` (optional, integer, default `0`): Pagination offset.

**Important**:

- Use pagination when reconstructing older work.

---

### Tasks

#### `elefante-TaskCreate`

**Purpose**: Create a task in the orchestration graph.

**Why this exists**: Complex work should live in persistent task state, not only in an agent's short-lived scratchpad.

**Parameters**:

- `description` (required, string): What needs to be done.
- `parent_id` (optional, string): Parent task UUID for subtask relationships.
- `priority` (optional, integer, default `1`, min `1`, max `10`): Higher number means higher priority.
- `assigned_agent` (optional, string): Agent or role responsible for the task.
- `blocked_by` (optional, string[]): Task IDs that must complete first.
- `subtasks` (optional, object[]): Inline child tasks.
  - `description` (required): Subtask description.
  - `priority` (optional, integer, default `1`): Subtask priority.
  - `assigned_agent` (optional, string): Subtask assignee.

**Important**:

- Use `parent_id` for hierarchy.
- Use `blocked_by` for dependency chains.
- Use `subtasks` when you already know the full breakdown.

#### `elefante-TaskUpdate`

**Purpose**: Update task status or attach output.

**Why this exists**: Work state must survive context loss. Tasks are only useful if status changes are written back.

**Parameters**:

- `task_id` (required, string): Task UUID.
- `status` (optional, string): `pending`, `in_progress`, `completed`, `failed`, or `blocked`.
- `output` (optional, string): Result summary or failure message.

#### `elefante-TaskGraph`

**Purpose**: Inspect task hierarchy.

**Why this exists**: Persistent tasks are only useful if agents can re-open the graph and see dependencies or subtasks.

**Parameters**:

- `task_id` (optional, string): Specific task UUID. Omit to list root tasks.

---

### ETL (Batch Enrichment)

#### `elefante-ETLProcess`

**Purpose**: Fetch raw memories that still need agent enrichment.

**Why this exists**: Elefante stores memory first, then lets an agent enrich retrieval quality later with summary and trigger patterns.

**Parameters**:

- `limit` (optional, integer, default `5`, min `1`, max `50`): Number of raw memories to process.
- `include_stats` (optional, boolean, default `false`): Include processing counts.

**Workflow**:

1. Call `elefante-ETLProcess`.
2. Read each raw memory.
3. Call `elefante-ETLClassify` for each one.

#### `elefante-ETLClassify`

**Purpose**: Submit agent-written enrichment for a memory returned by `ETLProcess`.

**Why this exists**: Retrieval improves only if the agent supplies usable summaries, concepts, and trigger phrases.

**Parameters**:

- `memory_id` (required, string): Memory UUID from `ETLProcess`.
- `summary` (required, string): One-line summary, max 200 characters.
- `concepts` (optional, string[]): Key terms for graph edges and retrieval.
- `surfaces_when` (optional, string[]): Query patterns that should trigger this memory later.

**Important**:

- The live schema fields are `concepts` and `surfaces_when`.
- `topic` and `knowledge_type` are not part of the live schema.

---

### System Operations

#### `elefante-System`

**Purpose**: Enable or disable Elefante Mode.

**Why this exists**: The system coordinates database locks. The caller needs an explicit way to activate or release access.

**Parameters**:

- `action` (optional, string, default `enable`): `enable` or `disable`.
- `force` (optional, boolean, default `false`): Force-enable despite a lock conflict.

**Important**:

- Use `disable` for multi-IDE safety when you are done.
- Use `force` carefully. It is an override path, not normal flow.

#### `elefante-SystemStatusGet`

**Purpose**: Return current system health and lock state.

**Why this exists**: Before opening dashboards or diagnosing failures, the caller needs a fast read on mode state, locks, and database health.

**Parameters**: None.

#### `elefante-DashboardOpen`

**Purpose**: Open the dashboard in the browser.

**Why this exists**: The dashboard is the visual layer of the memory and graph system.

**Parameters**:

- `refresh` (optional, boolean, default `false`): Rebuild dashboard snapshot before opening.

**Important**:

- `refresh=true` reads from live databases and requires Elefante Mode to be enabled.
- Use `refresh=false` when you only need the latest existing snapshot.

---

### Directives

Directives are always-on behavioral constraints. They are not memories. They are injected into every tool response and cannot be outcompeted by similarity scores.

#### `elefante-DirectiveAdd`

**Purpose**: Add a persistent directive.

**Why this exists**: Some rules should never depend on search relevance. They must always be present at decision time.

**Parameters**:

- `content` (required, string): Clear, actionable directive text.

**Example**:

```json
{
  "content": "Always verify the MCP server is alive before opening the dashboard"
}
```

#### `elefante-DirectiveList`

**Purpose**: List active directives.

**Why this exists**: Directives need inspection and audit because they affect every future tool response.

**Parameters**: None.

#### `elefante-DirectiveRemove`

**Purpose**: Remove a directive by ID.

**Why this exists**: Always-on rules must be removable when they become outdated or harmful.

**Parameters**:

- `directive_id` (required, string): Directive ID from `elefante-DirectiveList`.

**Storage**: `~/.elefante/data/directives.json`

---

### Prompts

Prompts are not tools. They inject memory-aware instructions or pre-fetched context into the model.

#### `elefante-grounding`

**Purpose**: Inject search-first memory behavior into the model at the start of a conversation.

**Why this exists**: It teaches the model to search Elefante before answering questions about preferences, project conventions, or past decisions.

**Arguments**: None.

**Important**:

- This is a prompt retrieved through MCP prompt APIs, not a tool call.
- The content is instructional grounding. It does not itself fetch memories.

#### `elefante-context`

**Purpose**: Inject a small retrieved memory bundle for a specific topic.

**Why this exists**: It gives the model targeted context before answering a memory-related question.

**Arguments**:

- `topic` (required, string): What topic to retrieve context for.

**Important**:

- This prompt performs a live hybrid memory search before returning content.
- It is a focused prefetch path for one topic, not a replacement for explicit tool calls when the caller needs structured results or mutations.

---

## 3. Best Practices

1. **Search before write**: Run `elefante-MemorySearch` before `MemoryAdd`, `MemoryUpdate`, `MemoryDelete`, or `GraphConnect`.
2. **Choose memory type by lifespan**: Use `specification` and `directive` for permanent truths. Use `note` and `conversation` only for short-lived context.
3. **Use `list_all` deliberately**: It is browse/export mode, not a replacement for a targeted relevance search.
4. **Batch graph work**: Prefer one `GraphConnect` call with refs or IDs over many small graph mutations.
5. **Parameterize Cypher**: Use `GraphQuery.parameters` instead of building queries with string interpolation.
6. **Persist plans**: Use `TaskCreate`, `parent_id`, and `blocked_by` so work survives context loss.
7. **Treat ETL as a pair**: `ETLProcess` fetches raw memories; `ETLClassify` is what actually improves future retrieval.
8. **Refresh the dashboard only when mode is active**: `DashboardOpen(refresh=true)` touches live data.

## 4. Why This Document Is Strict

Elefante is not a generic note store. Each feature exists because the system is trying to solve a failure mode:

- `memory_type` exists because memory lifespan changes behavior.
- compliance-gated writes exist because duplicate or context-free writes degrade the brain.
- graph refs and IDs exist because graph duplication destroys topology quality.
- ETL enrichment exists because raw storage alone is not enough for strong retrieval.
- directives exist because some rules must always be present, not merely likely to surface.

If this document drifts from `src/mcp/server.py`, the UX breaks first for agents and then for users. Keep it source-derived.
