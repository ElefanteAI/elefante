# MCP Tools and Prompts (published v2.15.1 baseline; current source)

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

The published customer profile exposes **18 tools** and **2 prompts**, including
the verified `elefante-Recover` surface documented below. Memory operations use one
`elefante-Memory` tool with an action discriminator.

- **Tools** read, write, or inspect the system.
- **Prompts** inject grounding or pre-fetched memory context into the model. They are not tools.
- **Source of truth**: `src/mcp/server.py`

**Critical workflow rule**:

- When `elefante-Recall` is listed by the connected surface, call it at most once
  per user question when stored preferences, decisions, or project context could
  materially change the answer. Skip it for a self-contained question. Treat
  `no_match`, `blocked`, and `unavailable` as terminal for that answer; do not
  retry or broaden retrieval.
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
  writing, call `elefante-Recall` with one likely future question. A stored
  receipt is not proof that the memory is deliverable.
- Home's verified Remember flow asks that likely future question before writing.
  It persists the bounded question as a strict project-scoped Recall cue and
  proves the cue through Recall. If proof fails, the attempted memory is removed
  and Home reports that nothing was saved.

**Tool response contract**:

- `elefante-Recall` is intentionally minimal: it returns only `success`,
  `status`, `context`, `supplied_count`, `abstained`, `delivery_blocked`, and
  `read_only`. Internal protocol, directive, entrypoint, and `TOKEN_STATS`
  wrappers are not sent to the answering model; Elefante still records its
  token accounting locally. Recall does not echo the current question in its
  response. Its governed context remains capped at 450 heuristic tokens, and
  the complete pretty Unicode response is capped at 1,000 heuristic tokens; an
  encoded response that cannot fit fails closed without a memory body.
- Other tool responses include `TOKEN_STATS`. Normal memory, graph, context,
  session, ETL, and task operations also receive the entrypoint, pitfall, and
  active-directive blocks. System, dashboard, and directive-management tools
  return through a minimal management path and do not receive those recursive
  policy blocks.
- `ENTRYPOINT_SEQUENCE_READ_THIS_FIRST` is environment-specific. Developer
  runtimes receive repository-debug routing; customer runtimes receive a short
  memory-use and secret-handling sequence.
- The customer profile does not enable automatic tool-response context. Recall
  and the context prompt are the explicit bounded answer-delivery paths.
- `RELEVANT_CONTEXT` is conditional, not universal. It remains disabled in the
  customer profile and is not a substitute for Recall or the context prompt.
- `TOKEN_STATS` is injected into every non-Recall tool response. It reports
  Elefante's local heuristic estimate of each call's token size; it is not a
  provider pricing API, invoice estimate, or dollar-cost calculation. Fields:
  - `output_tokens` (int): Total tokens in the response, including protocol overhead and the TOKEN_STATS block itself.
  - `overhead_tokens` (int): Tokens consumed by protocol injection (MANDATORY_PROTOCOLS, DIRECTIVES, ENTRYPOINT_SEQUENCE) plus TOKEN_STATS itself. Not content the agent requested.
  - `signal_ratio` (float, 0.0-1.0): Fraction of output that is actual payload. `1.0` = zero overhead, `0.0` = all overhead. Higher is better.

**Token intelligence on `elefante-Memory(action="add")`**:

- `add` responses include `content_tokens` (estimated token count of the stored content) and `token_density` (ratio of actual tokens to the type's budget). When density exceeds 2.0x, a `density_warning` string is included advising the caller to trim or split the memory.
- Token budgets are proportional to memory type lifespan: `specification` (800), `insight` (500), `decision` (400), `preference` (300), `fact` (250), `directive` (200), `note` (150), `conversation` (100).

### Core Memory Operations

#### `elefante-Recall`

**Status**: Released and default-on in v2.15.1.

**Purpose**: Give an answering agent the smallest governed durable context for
one question without exposing the broad search or mutation interface.

**Parameter**:

- `question` (required, string, 1–1,000 characters): The complete standalone
  customer question. Include specific project, file, person, or decision names
  when known.
- `workspace` (optional, absolute path): Current workspace used by the local
  Project Registry. A host-provided working directory is used when
  omitted.
- `project_id` (optional, UUID): Exact registered project ID used only to
  cross-check the workspace resolution; it never replaces workspace context.

**Result**:

- `status="supplied"`: One to three memories were supplied within a 450-token
  context budget.
- `status="no_match"`: No memory passed the relevance and governance gates.
- `status="blocked"`: Governed context could not be delivered safely within a
  mandatory-governance or complete-response budget.
- `status="unavailable"`: Local retrieval failed; the agent must continue from
  the current request and verified current evidence without inventing history.

Recall is read-only. It does not create a compliance receipt, increment access
counts, record declared use, mutate ranking, expose memory UUIDs, or require any
opt-in evaluation flags. The context prompt and Recall share the
same retrieval, current-source validation, governed selection, and budget path.
The answering host already owns the question, so Recall does not echo it in the
returned context. Call Recall at most once for that user question; a terminal
status is evidence to continue from current sources, not a retry instruction.
Missing, empty, overlong, and wrong-type questions return the same seven-field
`status="blocked"` product response rather than an SDK validation wrapper.
Operator-disabled and retrieval-failure paths use the same seven fields with
`status="unavailable"`.
When local strict project mode is active, Elefante resolves one registered
project before opening the memory stores. Missing, invalid, unregistered, or
ambiguous workspace context returns `status="blocked"` and explicitly states
that no memory was read or supplied. Supplied context is then forced to the
resolved project ID and root; semantic similarity cannot widen that boundary.
Its MCP annotations declare `readOnlyHint=true`, `destructiveHint=false`,
`idempotentHint=true`, and `openWorldHint=false`, so compatible hosts do not ask
for mutation approval.

The customer installer also adds a marked Recall-routing block to Codex's active
global guidance file (`AGENTS.override.md` when it is non-empty, otherwise
`AGENTS.md`). Existing user text is preserved. The install manifest owns only
that exact block; uninstall removes it only while unchanged and preserves a
user-edited block for review. Configuration rolls back a newly added or prior
installer-owned Codex registration when managed guidance fails, and reports
`partial` if that rollback cannot finish. Customer readiness additionally
requires that the active guidance path, Codex registration, live Recall tool,
read-only annotations, and one bounded read-only probe all verify.

**Rollback**: Set `ELEFANTE_RECALL_ENABLED=0` in the local daemon environment
and restart Elefante. The tool disappears from discovery and direct calls fail
closed; the existing broad memory search and prompts remain unchanged.

#### `elefante-Memory`

**Purpose**: Single discriminated entry point for persistent memory operations.
The normal customer actions are `add`, `search`, `update`, `resolve`, `delete`,
and `consolidate`. The source schema reserves `record_use` for the default-off
developer evaluation profile; it is not a normal customer operation.

**Why one tool, not five**: Five separate memory tools forced agents to pre-classify intent before naming a tool. Consolidation moves that branch into a parameter, reduces five memory entries to one, and lets one schema document the later additive actions too. Atomic-swapped at v2.10.0 / 2026-05-02 — no overlap window, no aliases.

**Why `memory_type` matters** (`action=add`): Not cosmetic metadata. It changes decay, ranking, and lifespan.

- `specification` and `directive` have zero type-specific creation decay, but the current freshness term still lowers their behavioral vitality when they are not accessed.
- `note` and `conversation` decay quickly.
- Wrong type = wrong behavior later.

**Common parameter**:

- `action` (required, string): One of `add`, `search`, `update`, `resolve`,
  `delete`, or `consolidate` for normal customer operation.
- `workspace` (optional, absolute path): Current workspace used by the local
  Project Registry. The host-provided working directory is used when
  omitted.
- `project_id` (optional, UUID): Exact registered ID used only as a strict-mode
  cross-check. A supplied ID that disagrees with workspace mapping is rejected.

##### `action="add"` — store a new memory

**Why this exists**: Elefante's session context is not durable. If a user makes a real decision, preference, or rule, it must be stored explicitly or it disappears on restart.

**Parameters**:

- `content` (required, string): The memory content to store.
- `memory_type` (optional, string, default `fact`): `fact`, `decision`, `preference`, `insight`, `note`, `conversation`, `specification`, or `directive`.
- `domain` (optional, string): `work`, `personal`, `learning`, `project`, `reference`, or `system`.
- `category` (optional, string): Topic grouping such as `elefante`, `python`, or `user-preferences`.
- `tags` (optional, string[]): Tags for filtering and retrieval.
- `entities` (optional, object[]): Graph links as `{name, type}` objects.
- `attachments` (optional, object[], maximum 8): Local image, audio, or video
  files copied into Elefante's private content-addressed media store. Each item
  requires `path` and a bounded text `description`; optional fields are
  `mime_type`, `width`, `height`, and `duration_ms`. Files are limited to 25 MiB
  each and never trigger OCR, transcription, captioning, or network upload.
- `metadata` (optional, object): Additional structured metadata.
- `retention_policy` (optional): `managed`, `permanent`, or `ephemeral`.
  Automatic ephemeral expiry is not implemented.
- `injection_policy` (optional): `ranked`, `triggered`, or `always`. `always`
  requires `user_locked=true`.
- `scope` (optional): Exact project, workspace, or task identifier.
- `trigger` (optional): Up to 20 literal phrases for triggered delivery.
- `user_locked` (optional): Explicit user authority; automated refinery cleanup
  does not archive or weaken a protected memory.
- `force_new` (optional, boolean, default `false`): Always create a new record and bypass deduplication.

**Important**:

- Requires prior `action="search"` (Compliance Gate).
- `force_new=true` should be rare. It skips title deduplication, preference merge, and high-similarity redundancy checks.
- Use `specification` for durable architecture or contract truths. Use
  `directive` for behavioral rules. Use `note` only for short-lived context.
  Governance fields are part of the v2.15.1 customer contract.
- In local strict project mode, Elefante resolves the workspace
  before opening the stores and overwrites project/workspace/scope metadata with
  that registered identity. Missing or ambiguous context, an unavailable root,
  or a mismatched supplied project ID changes nothing.

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
- `surface_context` (optional, string, max 1,000 characters): File, terminal-error,
  or conversation context for the opt-in literal-trigger path. Only memories
  explicitly configured with `injection_policy="triggered"` can surface from
  this field; when omitted, the query is used as the context.
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
- When governed candidates carry a stored conflict relationship or contradictory
  status, `answer_context` reports a bounded `conflict_count` and
  `conflict_warnings` while withholding those candidates from answer delivery.
  The warning omits internal IDs; neither side is selected as authoritative.
- When a `surface_context` is supplied, or when the query itself contains a
  configured literal trigger, matching `triggered` memories are added as
  `source="triggered"` results with `surface_matches` and an explicit-trigger
  explanation (or annotate an existing semantic hit). This path is capped at
  three memories and remains subject to lifecycle, scope, source-trust,
  conflict, and privacy gates. When a workspace filter is supplied, the shared
  current-source digest gate also blocks stale source-bound memories. It does
  not increment access counts or create graph relationships.
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

##### `action="correct"` — inspect or apply verified customer repair

**Why this exists**: A customer must be able to fix wrong, stale, duplicate, or
inactive knowledge without opening SQLite, Kuzu, or internal lifecycle fields.

**Parameters**:

- `memory_id` (required UUID): Exact target memory.
- `correction` (required): `edit`, `replace`, `resolve`, `archive`, `restore`,
  or `permanent_delete`.
- `apply` (optional boolean, default `false`): Inspect without writing when
  false. Apply only the exact inspected plan when true.
- `content` (required for `edit` and `replace`): Corrected knowledge. Edit keeps
  the same ID; Replace creates a new current assertion and preserves the older
  one as history.
- `related_memory_id` and `winner_memory_id` (Resolve only): Exact peer and, when
  required, the user-selected authoritative record.
- `reason`, `verification_question`, and `invocation_mode="user_directed"`
  (required for apply): Bounded audit reason and one likely future Recall
  question. Edit, Replace, and Restore persist the canonicalized question as a
  cue on the resulting current memory. Archive and permanent delete use it only
  to prove exclusion. The question is never stored in the privacy-safe receipt.
- `confirm_protected` (required when the affected record is protected): Explicit
  user authorization.
- `confirm_permanent` (apply only for `permanent_delete`): A separate final
  boolean confirmation after inspecting the exact destructive plan.
- `expected_record_sha256`, `expected_graph_sha256`, and
  `expected_content_sha256` (apply): Copy the exact hashes returned by the
  inspected plan. A stale or altered plan performs no write.

**Behavior**:

- Edit, Replace, Archive, and Restore require one exact registered project
  scope and verify both vector and graph authority.
- Archive removes the record from normal Recall but preserves an exact manual
  restore point. Restore accepts only that unambiguous service-created archive;
  it does not silently revive a superseded or legacy record.
- Replace preserves the old assertion, creates explicit lineage, and verifies
  that scoped Recall selects the new assertion and excludes the old one.
- Edit and Replace re-mine deterministic concept links from the corrected
  content. Only generated `HAS_CONCEPT` links are replaced; explicit and
  structural relationships are preserved. A failed re-mine or later
  postcondition restores the previous content and concept projection.
- Home is atomically refreshed only after authoritative readback. Any failed
  postcondition restores the exact memory, graph, snapshot, and correction-
  created provenance preimage when possible.
- Terminal statuses are `VERIFIED_COMPLETE`, `FAILED_NO_CHANGE`,
  `FAILED_ROLLED_BACK`, `NEEDS_HUMAN`, or `UNSAFE`.
- Receipts contain bounded identifiers, hashes, checks, and error codes, not
  memory content, customer-entered reason/question, project path, or capability
  token.
- `permanent_delete` is an advanced destructive flow. Under one write boundary,
  Correct revalidates the inspected hashes, creates and revalidates a fresh
  workflow-managed Recover backup, removes the exact memory, generated concept
  links, graph entity, orphaned source when safe, and unshared attachments, then
  proves Home and scoped Recall no longer expose it. Failure restores the
  verified backup. Success destroys the temporary backup and reports
  `recoverable=false`; the deleted memory cannot then be restored by Elefante.

**Important**:

- Inspection is read-only. Apply requires the normal search-before-write
  Compliance Gate and the exact inspected hashes.
- This is the primary customer repair path. Use it instead of low-level content
  or lifecycle mutation aliases.

##### `action="update"` — amend governance metadata only

**Why this exists**: Compatibility callers may need to adjust retrieval and
retention policy without redefining the stored assertion.

**Parameters**:

- `memory_id` (required, string): UUID of the memory to amend.
- `tags` (optional, string[]): Replacement tags.
- `retention_policy`, `injection_policy`, `scope`, `trigger`, `user_locked`
  (optional): Governance fields with the same meanings as `action="add"`.

**Important**:

- Requires prior `action="search"` (Compliance Gate).
- Strict mode requires the active project to match the target memory before a
  store is opened.
- `content`, `deprecated`, `archived`, and `supersedes_id` are rejected with
  `USE_VERIFIED_CORRECT`. Use `action="correct"` for knowledge or lifecycle
  changes.

##### `action="resolve"` — inspect or apply Smart Merge/conflict repair

**Why this exists**: Equivalent records should consolidate without losing
history, while contradictory records need an explicit authority decision
instead of an arbitrary timestamp or type winner.

This direct verb remains as a compatibility path. New customer repair flows
should use `action="correct", correction="resolve"` so all correction intent is
expressed through one product action.

**Parameters**:

- `memory_id` and `related_memory_id` (required UUIDs): The two current records.
- `winner_memory_id` (optional UUID): Required for an ambiguous true conflict;
  must identify one of the pair.
- `apply` (optional boolean, default `false`): Dry-run when false.
- `reason` (required for apply): Bounded audit reason.
- `verification_question` (required for apply): A bounded, disposable question
  used only to prove the scoped Recall result. It is not stored in the receipt.
- `invocation_mode` (required for apply): Must be `user_directed`.
- `confirm_protected` (required when the losing record is protected): Explicit
  authorization to supersede it.

**Behavior**:

- Equivalent assertions consolidate automatically into one recoverable current
  record.
- A true conflict auto-selects only when exactly one side carries protected user
  authority; otherwise the user chooses the winner.
- Different scopes never collapse.
- The losing record is archived/deprecated/superseded, not silently deleted.
- Both records and their conflict IDs are updated together; a second-write
  failure restores the first record.
- Both records must already carry one exact matching declared
  project/workspace/scope identity. Apply also requires the normal
  search-before-write compliance receipt.
- Completion is not inferred from the write return. Elefante reads both records
  back, atomically refreshes the private Home snapshot, and runs scoped Recall;
  the winner must be supplied and the loser excluded.
- A failed postcondition restores the exact two-record preimage and verifies the
  restore. An incomplete restore is `UNSAFE` and requires human recovery.
- Apply returns one bounded terminal status: `VERIFIED_COMPLETE`,
  `FAILED_NO_CHANGE`, `FAILED_ROLLED_BACK`, `NEEDS_HUMAN`, or `UNSAFE`, plus a
  privacy-safe receipt containing IDs, hashes, checks, and error codes but no
  memory content, project name, path, reason, or verification question.
- Elefante Home uses the same operation through a short-lived origin-bound
  capability and one-use plan ticket. It does not expose a generic MCP, database,
  path, query, or shell proxy.

##### `action="delete"` — guarded legacy compatibility path

**Why this exists**: Older callers may still send the historical delete verb;
it must fail safely rather than bypass the verified product lifecycle.

**Parameters**:

- `memory_id` (required, string): UUID of the memory to delete.
- `reason` (required, string): Audit-trail reason.
- `delete_mode` (optional, `archive | permanent`, default `archive`).
- `invocation_mode` (optional, `workflow_managed | user_directed`, default
  `workflow_managed`): Declares who authorized the mutation.
- `confirm_permanent` (required for permanent deletion): Must be `true`.
- `confirm_protected` (required for protected memory): Must be `true` together
  with `invocation_mode="user_directed"`.

**Important**:

- `delete_mode="archive"` performs no write and returns
  `USE_VERIFIED_CORRECT`; use `action="correct", correction="archive"`.
- Confirmed legacy permanent deletion performs no write and returns
  `USE_VERIFIED_CORRECT`; use
  `action="correct", correction="permanent_delete"` so the exact plan, fresh
  temporary backup, verification, and receipt remain one operation.
- Workflow-managed calls cannot authorize protected or permanent deletion.

##### `action="consolidate"` — deduplicate and canonicalize

**Why this exists**: Over time, memories can drift into redundant or test-only states. Consolidation keeps exports and retrieval clean.

**Parameters**:

- `force` (optional, boolean, default `false`): Apply changes. Default behavior is dry-run only.

**Important**:

- Start with `force=false`.
- Use this for maintenance, not for routine single-memory edits.

### Knowledge Graph Operations

#### `elefante-GraphConnect`

**Purpose**: Find or create entities and create or reuse relationships in one call.

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
- The complete nested request is privacy-scrubbed before any graph write;
  responses expose only redaction counts and detector types.
- One transaction-scoped write lock covers every entity and relationship
  mutation. Optional system status is added after that graph ownership ends.
- Stable entity names/types and identical relationship endpoints/type/properties
  reuse existing IDs. Different relationship properties remain distinct links.
- `id` references an existing entity; this path does not overwrite its fields.
  Properties on a newly created entity are persisted.
- Invalid refs, types and missing existing endpoints are rejected before the
  first mutation. This is not a promise of rollback after every storage failure.
- All 18 `RelationshipType` values retain their actual labels and properties.
  Legacy schemas upgrade additively; old timestamps are not invented.
- Entity types are lowercase enum values from `src/models/entity.py`, such as
  `person`, `project`, `file`, `concept`, `technology`, `task`, `specification`,
  and `directive`. Relationship values include `RELATES_TO`, `DEPENDS_ON`,
  `PART_OF`, `CREATED_BY`, `USES`, `BLOCKS`, `REFERENCES`, `WORKS_ON`, `GOVERNS`,
  `ENFORCES`, `SUPERSEDES`, and `CONTRADICTS`.

**Example**:

```json
{
  "entities": [
    { "name": "Jay", "type": "person", "ref": "user" },
    { "name": "Elefante", "type": "project", "ref": "proj" }
  ],
  "relationships": [
    { "from_ref": "proj", "to_ref": "user", "relationship_type": "CREATED_BY" }
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

The complete agent-facing result is privacy-scrubbed, including legacy raw
content, before it leaves the server. Fetching raw rows marks them as processing,
so that queue transition and optional stats read share one transaction-scoped
write lock.

**Parameters**:

- `limit` (optional, integer, default `5`, min `1`, max `50`): Number of raw memories to process.
- `include_stats` (optional, boolean, default `false`): Include processing counts.

**Workflow**:

1. Call `elefante-ETLProcess`.
2. Read each raw memory.
3. Call `elefante-ETLClassify` for each one.

#### `elefante-ETLClassify`

**Purpose**: Submit agent-written enrichment for a memory returned by `ETLProcess`.

**Why this exists**: Agent enrichment adds usable summaries and retrieval concepts while preserving trigger metadata for bounded proactive surfacing.

**Parameters**:

- `memory_id` (required, string): Memory UUID from `ETLProcess`.
- `summary` (required, string): One-line summary, max 200 characters.
- `concepts` (optional, string[]): Key terms for graph edges and retrieval.
- `surfaces_when` (optional, string[]): Stored trigger phrases for the explicit,
  bounded proactive-surfacing path; this is not a current ranking signal for
  general semantic retrieval.

**Important**:

- The live schema fields are `concepts` and `surfaces_when`.
- `topic` and `knowledge_type` are not part of the live schema.
- Summary, concepts, and trigger metadata are privacy-scrubbed before
  persistence; responses expose only redaction counts and detector types.

---

### System Operations

#### `elefante-Recover`

**Purpose**: Inspect and perform named, verified lifecycle operations without
exposing arbitrary paths, shell access, or database primitives.

**Why this exists**: A customer needs one recovery contract that says what will
happen, requires confirmation, verifies the result, and reports whether anything
changed or was rolled back.

**Actions**:

- `health`: read-only product state from runtime, agent, Recall, and verified
  backup evidence. It accepts no apply fields.
- `backup`: inspect the managed data layout, then create and independently
  restage one checksummed local backup.
- `restore`: list configured backup basenames or inspect one archive; apply
  creates a safety backup, stages and verifies the target, switches once, tests
  Home and Recall, and restores exact previous data when a postcondition fails.
- `support_report`: preview an allowlisted diagnostic manifest, then create one
  private verified ZIP containing only `support-report.json`. Elefante does not
  transmit the ZIP.

**Plan and apply**:

- Omit `apply` or set it to `false` for inspection.
- Apply requires `confirm=true`, a valid `invocation_mode`, and the exact plan
  hash: `expected_layout_sha256` for backup/restore,
  `expected_archive_sha256` for restore, or `expected_report_sha256` for the
  support report.
- Restore also requires one disposable `verification_question`. The question
  is used for the post-restore Recall check and is not written to the receipt.
- A changed layout, archive, or support preview is stale and must be inspected
  again.

**Support-report privacy boundary**:

- Included: product/build identity, OS and Python version, agent and Recall
  readiness, diagnostic codes, backup validity counts, and allowlisted
  content-free lifecycle receipts.
- Excluded: memory content, project names and paths, prompts, questions,
  answers, transcripts, credentials, environment values, host configuration
  contents, and application logs.
- Elefante Home shows these categories before confirmation and downloads the
  verified managed ZIP through the short-lived local control session.

Repair, update, code rollback, and data-preserving uninstall remain
official-package operations rather than MCP Recover actions.

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
- Snapshot browsing and Reload remain read-only and cannot trigger a live
  database refresh. Local Elefante Home can additionally request only
  named Verified Correct, Verified Resolve, and Project Registry operations
  through `/control`, using a short-lived origin-bound capability carried in
  the URL fragment and removed from browser history after load. Correct supports
  Edit, Replace, Archive, Restore, and advanced permanent deletion through
  content-free one-use plan tickets. Permanent deletion additionally requires
  typing `DELETE` and a separate final confirmation; its temporary verified
  backup is restored on failure and destroyed on verified success. Home exposes
  no generic MCP, database, path, query, or shell proxy.

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
