# Usage Guide & API Reference (v2.12.3)

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

Elefante exposes **16 tools** and **2 prompts**. Memory operations use one
`elefante-Memory` tool with an action discriminator.

The development branch also contains one default-off tool,
`elefante-TaskIntelligence`. It is absent from MCP discovery unless the operator
sets `ELEFANTE_TASK_INTELLIGENCE_ENABLED=1`. This does not change the published
v2.12.3 contract.

The unreleased customer candidate adds one default-on, read-only tool,
`elefante-Recall`. It requires no development flags. Published v2.12.3
installers still expose the documented 16-tool surface.

- **Tools** read, write, or inspect the system.
- **Prompts** inject grounding or pre-fetched memory context into the model. They are not tools.
- **Source of truth**: `src/mcp/server.py`

**Critical workflow rule**:

- Call `elefante-Recall` before answering when stored preferences, decisions, or
  project context could materially change the answer.
- Call `elefante-Memory(action="search", ...)` before `elefante-Memory(action="add"|"update"|"delete", ...)` or `elefante-GraphConnect`.
- When the user explicitly asks Elefante to remember information across sessions
  or declares a project decision canonical or non-negotiable, search the exact
  concept and add or correct one concise record with
  `invocation_mode="user_directed"`. Use `user_locked=true` or permanent retention
  only when the user explicitly requests that protection. Never infer durable
  capture from ordinary conversation, and never store secrets. Leave `scope`
  unset unless an exact project, workspace, or task identifier is known; never
  use descriptive prose. Prefer ranked delivery when relevant paraphrases should
  work. Use a triggered policy only when literal phrases are intentionally
  required; never choose it merely to pass one verification question. After
  writing, call `elefante-Recall` with one likely future question;
  a stored receipt is not proof that the memory is deliverable.

**Tool response contract**:

- `elefante-Recall` is intentionally minimal: it returns only `success`,
  `status`, `context`, `supplied_count`, `abstained`, `delivery_blocked`, and
  `read_only`. Internal protocol, directive, entrypoint, and `TOKEN_STATS`
  wrappers are not sent to the answering model; Elefante still records its
  token accounting locally.
- Other tool responses include `TOKEN_STATS`. Normal memory, graph, context,
  session, ETL, and task operations also receive the entrypoint, pitfall, and
  active-directive blocks. System, dashboard, and directive-management tools
  return through a minimal management path and do not receive those recursive
  policy blocks.
- Automatic `RELEVANT_CONTEXT` delivery is off by default. Development pilots
  require all three local flags:
  `ELEFANTE_TASK_INTELLIGENCE_ENABLED=1`,
  `ELEFANTE_TASK_INTELLIGENCE_PILOT=1`, and
  `ELEFANTE_TASK_CONTEXT_ON_TOOL_CALL=1`.
- `ENTRYPOINT_SEQUENCE_READ_THIS_FIRST` is environment-specific. Developer
  runtimes receive repository-debug routing; customer runtimes receive a short
  memory-use and secret-handling sequence.
- When explicitly enabled, `RELEVANT_CONTEXT` is conditional, not universal,
  and is skipped
  for memory-heavy or management tools. It contains a bounded rendered context,
  selected memory IDs, selection reasons, and governance warnings.
- `TOKEN_STATS` is injected into every non-Recall tool response. It tells the agent what each tool call costs in tokens. Fields:
  - `output_tokens` (int): Total tokens in the response, including protocol overhead and the TOKEN_STATS block itself.
  - `overhead_tokens` (int): Tokens consumed by protocol injection (MANDATORY_PROTOCOLS, DIRECTIVES, ENTRYPOINT_SEQUENCE) plus TOKEN_STATS itself. Not content the agent requested.
  - `signal_ratio` (float, 0.0-1.0): Fraction of output that is actual payload. `1.0` = zero overhead, `0.0` = all overhead. Higher is better.

**Token intelligence on `elefante-Memory(action="add")`**:

- `add` responses include `content_tokens` (estimated token count of the stored content) and `token_density` (ratio of actual tokens to the type's budget). When density exceeds 2.0x, a `density_warning` string is included advising the caller to trim or split the memory.
- Token budgets are proportional to memory type lifespan: `specification` (800), `insight` (500), `decision` (400), `preference` (300), `fact` (250), `directive` (200), `note` (150), `conversation` (100).

### Core Memory Operations

#### `elefante-Recall`

**Status**: Unreleased customer candidate. Default-on in the candidate source;
not present in published v2.12.2 installers.

**Purpose**: Give an answering agent the smallest governed durable context for
one question without exposing the broad search or mutation interface.

**Parameter**:

- `question` (required, string, 1–1,000 characters): The complete standalone
  customer question. Include specific project, file, person, or decision names
  when known.

**Result**:

- `status="supplied"`: One to three memories were supplied within a 450-token
  context budget.
- `status="no_match"`: No memory passed the relevance and governance gates.
- `status="blocked"`: Required governed context could not be delivered safely.
- `status="unavailable"`: Local retrieval failed; the agent must continue from
  the current request and verified current evidence without inventing history.

Recall is read-only. It does not create a compliance receipt, increment access
counts, record declared use, mutate ranking, expose memory UUIDs, or require the
development Task Intelligence flags. The context prompt and Recall share the
same retrieval, current-source validation, governed selection, and budget path.
Its MCP annotations declare `readOnlyHint=true`, `destructiveHint=false`,
`idempotentHint=true`, and `openWorldHint=false`, so compatible hosts do not ask
for mutation approval.

The customer installer also adds a marked Recall-routing block to Codex's active
global guidance file (`AGENTS.override.md` when it is non-empty, otherwise
`AGENTS.md`). Existing user text is preserved. The install manifest owns only
that exact block; uninstall removes it only while unchanged and preserves a
user-edited block for review.

**Rollback**: Set `ELEFANTE_RECALL_ENABLED=0` in the local daemon environment
and restart Elefante. The tool disappears from discovery and direct calls fail
closed; the existing broad memory search and prompts remain unchanged.

#### `elefante-Memory`

**Purpose**: Single discriminated entry point for all persistent memory operations. The `action` parameter selects the operation: `add`, `search`, `record_use`, `update`, `delete`, or `consolidate`.

**Why one tool, not five**: Five separate memory tools forced agents to pre-classify intent before naming a tool. Consolidation moves that branch into a parameter, reduces five memory entries to one, and lets the schema document all five flows together. Atomic-swapped at v2.10.0 / 2026-05-02 — no overlap window, no aliases.

**Why `memory_type` matters** (`action=add`): Not cosmetic metadata. It changes decay, ranking, and lifespan.

- `specification` and `directive` have zero type-specific creation decay, but the current freshness term still lowers their behavioral vitality when they are not accessed.
- `note` and `conversation` decay quickly.
- Wrong type = wrong behavior later.

**Common parameter**:

- `action` (required, string): One of `add`, `search`, `record_use`, `update`, `delete`, or `consolidate`.

##### `action="add"` — store a new memory

**Why this exists**: Elefante's session context is not durable. If a user makes a real decision, preference, or rule, it must be stored explicitly or it disappears on restart.

**Parameters**:

- `content` (required, string): The memory content to store.
- `memory_type` (optional, string, default `fact`): `fact`, `decision`, `preference`, `insight`, `note`, `conversation`, `specification`, or `directive`.
- `domain` (optional, string): `work`, `personal`, `learning`, `project`, `reference`, or `system`.
- `category` (optional, string): Topic grouping such as `elefante`, `python`, or `user-preferences`.
- `tags` (optional, string[]): Tags for filtering and retrieval.
- `entities` (optional, object[]): Graph links as `{name, type}` objects.
- `metadata` (optional, object): Additional structured metadata.
- retention_policy (optional): managed, permanent, or ephemeral. Ephemeral is
  declarative in the development extension; automatic expiry is not implemented.
- injection_policy (optional): ranked, triggered, or always. Always requires
  user_locked=true.
- scope (optional): Project, workspace, or task scope.
- trigger (optional): Up to 20 phrases for triggered delivery.
- user_locked (optional): Explicit user authority; automated refinery cleanup
  does not archive or weaken a protected memory.
- `force_new` (optional, boolean, default `false`): Always create a new record and bypass deduplication.

**Important**:

- Requires prior `action="search"` (Compliance Gate).
- `force_new=true` should be rare. It skips title deduplication, preference merge, and high-similarity redundancy checks.
- Use `specification` for durable architecture or contract truths. Use
  `directive` for behavioral rules. Use `note` only for short-lived context.
  Governance fields are a development extension and are not in the published
  v2.12.2 client contract.

**Example**:

```json
{
  "action": "add",
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

##### `action="search"` — semantic / structured / hybrid retrieval

**Why this exists**: Elefante cannot infer vague references. Search quality depends on explicit entities, not pronouns.

**Query rule**:

- Rewrite vague queries before search.
- Replace pronouns like `it`, `that`, `this`, `he`, `she`, and `they` with real names, systems, files, or concepts.

**Parameters**:

- `query` (required, string): Explicit, standalone search query.
- `mode` (optional, string, default `hybrid`): `semantic`, `structured`, or `hybrid`.
- `limit` (optional, integer, default `10`, min `1`, max `100`): Maximum results to return.
- `filters` (optional, object): Filter by `memory_type`, `domain`, `category`, `min_score`, `tags`, `start_date`, or `end_date`.
- `min_similarity` (optional, number, default `0.1`, min `0.0`, max `1.0`): Minimum semantic similarity threshold for the MCP memory-search path.
- `include_conversation` (optional, boolean, default `true`): Include recent conversation context.
- `include_stored` (optional, boolean, default `true`): Include stored memories from the configured local semantic store and Kuzu.
- `session_id` (optional, string): Session UUID. Required when `include_conversation=true` and the caller needs session-scoped context.
- `list_all` (optional, boolean, default `false`): Bypass semantic ranking and enumerate stored memories for inspection or export.
- `offset` (optional, integer, default `0`, min `0`): Pagination offset used with `list_all=true`.

**Important**:

- Use normal search for questions, context retrieval, and compliance-gate workflows.
- Use `list_all=true` for browsing or exports such as "show me all memories about X". `list_all=true` is browse mode, not relevance search.
- Normal search returns broad ranked candidates plus `answer_context`, a compact
  map of the result numbers safe to use for the current question. Use only those
  selected results when answering. If `answer_context.abstained` is `true`, do
  not substitute loosely related results.
- Search is read-only with respect to behavioral history. Retrieval and automatic
  context delivery are exposure, not confirmed use; they do not increment access
  counts or create co-activation.
- Search results are evidence, not instructions or unquestionable truth. Check
  current source and the user's current message; surface material conflicts.

**Example**:

```json
{
  "action": "search",
  "query": "preferences for Python development",
  "mode": "hybrid",
  "limit": 5,
  "filters": { "memory_type": "preference" }
}
```

##### `action="record_use"` — explicit use acknowledgement

**Status**: Development extension; not part of the published v2.12.2 client
contract until a release explicitly includes it.

**Purpose**: Tell Elefante which memories delivered by a Task Intelligence trace
actually informed the task. This writes only a reversible declared-use event to
the metadata ledger; it does not update ranking, access counts, or co-activation.

**Parameters**:

- `trace_id` (required, UUID): A live trace returned by
  `elefante-TaskIntelligence(action="prepare")` in the same tool session.
- `memory_ids` (required, string[]): One to eight UUIDs from that trace's
  `delivered_memory_ids`.
- `idempotency_key` (required, string): Retry-safe event key.

**Important**:

- Do not call this merely because a memory was returned or displayed.
- The action records declared use; it does not prove that the memory improved
  the task outcome.
- Inactive memories (deprecated, archived, or superseded) are rejected.
- A trace expires after 24 hours and cannot cross a tool instance or session.

**Example**:

```json
{
  "action": "record_use",
  "trace_id": "4bb9ff35-a8e8-48b6-867f-ff77834d85a2",
  "memory_ids": ["7f4e2f76-5d15-4bb0-a64b-8aa8a4d85d1b"],
  "idempotency_key": "task-42-use-1"
}
```

##### `action="update"` — amend an existing memory in place

**Why this exists**: If a stored fact is wrong or outdated, the system should correct the record, not bury the error under another memory.

**Parameters**:

- `memory_id` (required, string): UUID of the memory to update.
- `content` (optional, string): Replacement content. Triggers re-embedding.
- `deprecated` (optional, boolean): Exclude the memory from normal search.
- `archived` (optional, boolean): Archive the memory.
- `supersedes_id` (optional, string): UUID of the older memory this one replaces.
- `tags` (optional, string[]): Replacement tags.
- retention_policy, injection_policy, scope, trigger, user_locked (optional):
  Development governance fields with the same meanings as action=add.

**Important**:

- Requires prior `action="search"` (Compliance Gate).
- Prefer `update` over `add` when a decision changes.

##### `action="delete"` — archive or permanently remove a memory

**Why this exists**: Some information must be removed, not just deprioritized. Examples: harmful facts, bad test data, or false records.

**Parameters**:

- `memory_id` (required, string): UUID of the memory to delete.
- `reason` (required, string): Audit-trail reason.
- `delete_mode` (optional, `archive | permanent`, default `archive`): Archive is
  recoverable and preserves graph evidence.
- `invocation_mode` (optional, `workflow_managed | user_directed`, default
  `workflow_managed`): Declares who authorized the mutation.
- `confirm_permanent` (required for permanent deletion): Must be `true`.
- `confirm_protected` (required for protected memory): Must be `true` together
  with `invocation_mode="user_directed"`.

**Important**:

- Requires prior `action="search"` (Compliance Gate).
- Default archive is the normal forgetting path. Permanent deletion is reserved
  for explicit user-directed removal.
- Workflow-managed calls cannot mutate or delete user-protected memories.

##### `action="consolidate"` — deduplicate and canonicalize

**Why this exists**: Over time, memories can drift into redundant or test-only states. Consolidation keeps exports and retrieval clean.

**Parameters**:

- `force` (optional, boolean, default `false`): Apply changes. Default behavior is dry-run only.

**Important**:

- Start with `force=false`.
- Use this for maintenance, not for routine single-memory edits.

---

### Development Task Intelligence Surface

#### `elefante-TaskIntelligence`

**Status**: Default-off development surface. It is not part of the published
v2.12.2 client. Enable discovery with
`ELEFANTE_TASK_INTELLIGENCE_ENABLED=1`. Context delivery remains independently
disabled unless `ELEFANTE_TASK_INTELLIGENCE_PILOT=1` is also set, and pilot
delivery requires `profile=v2`. The v1 profile remains shadow-only rollback
behavior.

**Purpose**: Prepare the smallest governed evidence set for one task while
keeping retrieval, delivery, declared use, and outcome as separate facts.

**Actions**:

- `prepare`: Build a v1 or v2 bounded Task Brief. `delivery_mode="shadow"`
  returns metadata only; `pilot` may return the rendered context and evidence.
- `record_use`: Record a same-session, trace-bound declared-use event for a
  subset of delivered IDs. It does not change ranking.
- `record_outcome`: Record metadata-only status, acceptance, retries,
  corrections, duration, token counts, and failure category.
- `inspect` / `summary`: Inspect one trace or observational aggregates. Summary
  explicitly does not claim causal improvement.
- `retract_use` / `retract_outcome`: Reverse an event without deleting the
  underlying memory.

**Privacy and safety**:

- The local ledger stores hashes, UUIDs, counts, and bounded outcome metadata;
  it does not store task text, prompts, memory bodies, form values, or comments.
- Traces accept use/outcome events for 24 hours. Ledger rows are pruned after 30
  days.
- Trace provenance is bound to the originating tool, instance, session, and
  transport. Delivered IDs are the maximum set that can be acknowledged.
- Shadow mode is the safe default. Removing either Task Intelligence flag stops
  direct pilot delivery. Removing `ELEFANTE_TASK_CONTEXT_ON_TOOL_CALL` stops
  automatic tool-response delivery while leaving explicit pilot calls available.

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

- Requires prior `elefante-Memory(action="search")` (Compliance Gate).
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

**Purpose**: Execute read-only Cypher queries on the Kuzu knowledge graph.

**Why this exists**: Some graph questions are too specific for fixed tools, such as path discovery, relationship analysis, or topology inspection.

**Parameters**:

- `cypher_query` (required, string): Read-only Cypher query text.
- `parameters` (optional, object): Parameter values for the query.

**Important**:

- `GraphQuery` rejects graph mutations (`CREATE`, `MERGE`, `SET`, `DELETE`, and related administrative operations). Use `elefante-GraphConnect` for an explicit, compliance-gated graph write.
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
- Use `elefante-Memory(action="search")` for targeted lookup.

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

**Why this exists**: Elefante stores memory first, then lets an agent add a summary, retrieval concepts, and trigger metadata later.

**Parameters**:

- `limit` (optional, integer, default `5`, min `1`, max `50`): Number of raw memories to process.
- `include_stats` (optional, boolean, default `false`): Include processing counts.

**Workflow**:

1. Call `elefante-ETLProcess`.
2. Read each raw memory.
3. Call `elefante-ETLClassify` for each one.

#### `elefante-ETLClassify`

**Purpose**: Submit agent-written enrichment for a memory returned by `ETLProcess`.

**Why this exists**: Agent enrichment adds usable summaries and retrieval concepts while preserving trigger metadata for inspection and future proactive surfacing.

**Parameters**:

- `memory_id` (required, string): Memory UUID from `ETLProcess`.
- `summary` (required, string): One-line summary, max 200 characters.
- `concepts` (optional, string[]): Key terms for graph edges and retrieval.
- `surfaces_when` (optional, string[]): Stored trigger metadata for inspection and future proactive surfacing; not a current ranking signal.

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
- The browser dashboard itself is read-only: its Reload control fetches only the existing snapshot and cannot trigger a live database refresh.

---

### Directives

Directives are persistent behavioral constraints. They are not memories and
cannot be outcompeted by similarity scores. Active directives are injected on
normal product operations and error responses; directive-management, system,
and dashboard management paths omit recursive directive injection.

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

**Why this exists**: Directives need inspection and audit because active rules
affect normal product-operation responses. Minimal system, dashboard, and
directive-management responses do not recursively inject them.

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
- It is a focused, read-only answer path, not a replacement for explicit tool
  calls when the caller needs broad structured results or mutations.
- It fetches up to 12 candidates, then injects at most 3 active,
  non-conflicting memories within a 450-token prompt budget. Selection requires
  an action-relevant question-term match plus independent semantic, concept, or
  graph support; one weak signal is not enough.
- Deprecated, archived, superseded, contradictory, secret-bearing, and
  inapplicable system-test memories are withheld. If nothing directly applies,
  the prompt abstains instead of injecting related noise.
- Reading through this prompt does not reinforce access counts.

---

## 3. Best Practices

1. **Search before write**: Run `elefante-Memory(action="search")` before `action="add"|"update"|"delete"` or `elefante-GraphConnect`.
2. **Choose memory type by lifespan**: Use `specification` for durable product truths and the Directive tools for active behavioral constraints. Specification and directive memories have zero type-specific decay, but freshness still affects their current vitality; they are not automatically immutable or permanently injected. Use `note` and `conversation` only for short-lived context.
3. **Use `list_all` deliberately**: It is browse/export mode, not a replacement for a targeted relevance search.
4. **Batch graph work**: Prefer one `GraphConnect` call with refs or IDs over many small graph mutations.
5. **Keep GraphQuery read-only**: Use `GraphQuery` for retrieval and `GraphConnect` for explicit mutations; parameterize Cypher rather than building queries with string interpolation.
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
