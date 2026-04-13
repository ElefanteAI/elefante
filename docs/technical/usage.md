# Usage Guide & API Reference (v2.2.1)

## 1. Natural Language Interaction

Once connected to your IDE, use natural language to interact with Elefante. The agent will map your intent to the correct MCP tools.
**Examples**:

- **Store Info**: "Remember that I prefer using async/await over callbacks."
- **Retrieve Context**: "What do you know about my coding preferences?"
- **Graph Query**: "Show me all technologies related to the Elefante project."
- **Browse Sessions**: "Show me my recent work sessions"
- **Open Dashboard**: "Open the knowledge graph dashboard"

---

## 2. MCP Tools (20 Total)

The MCP server exposes 20 tools to your AI agent. All tool names follow the `elefante-PascalCase` convention.

### Core Memory Operations

#### `elefante-MemoryAdd`

**Purpose**: Store new information.

**Classification**: You must classify every memory by `memory_type` and `domain`.
**Scoring**: Do NOT assign importance. The system computes a score (0-100) based on behavior (recency, access count).

**Parameters**:

| Parameter     | Purpose                                   | Values                                                              |
| ------------- | ----------------------------------------- | ------------------------------------------------------------------- |
| `content`     | The actual text to remember               | Free text                                                           |
| `memory_type` | Kind of knowledge (determines decay rate) | `preference`, `fact`, `decision`, `insight`, `note`, `conversation` |
| `domain`      | High-level context                        | `work`, `personal`, `project`, `learning`, `reference`, `system`    |
| `category`    | Topic grouping                            | e.g. `elefante`, `python`                                           |
| `tags`        | Keywords for filtering                    | Array of strings                                                    |
| `entities`    | Graph links                               | Array of `{name, type}`                                             |
| `metadata`    | Extra key-value data                      | `{}`                                                                |
| `force_new`   | Bypass deduplication                      | `false`                                                             |

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

**Purpose**: Retrieve memories using hybrid search (semantic + structured + context).
**CRITICAL**: Query Rewriting Required

- Replace ALL pronouns (it, that, this, he, she, they)
- Make queries standalone and specific

**Response Format (v2.1.2+)**:

- **Null Stripping**: The payload is mathematically compressed. All null variables and empty arrays/dictionaries in the `metadata` block are dropped prior to serialization to save token context.
- **Actionable Header**: Every search payload includes a deterministic `suggested_action` system directive forcing the LLM to obey the constraints found.

**Parameters**:

- `query` (required): Search query
- `mode` (optional): `semantic` (vectors), `structured` (graph), or `hybrid` (both). Default: `hybrid`
- `limit` (optional): Max results (default: 10)
- `filters` (optional): Filter by `memory_type`, `min_score` (score 0-100), `tags`
- `list_all` (optional): If true, returns ALL memories (paginated) without semantic search. Use for dumps/exports.

**Example**:

```
elefante-MemorySearch(query="preferences for Python development")
```

#### `elefante-MemoryUpdate`

**Purpose**: Amend an existing memory.

**Use Cases**:

- Correct accurate facts
- Mark as deprecated or archived
- Set supersession chains (when a decision is overruled)

**Parameters**:

- `memory_id` (required): UUID
- `content` (optional): New text (triggers re-embedding)
- `tags` (optional): New tags
- `deprecated` (optional): Mark as obsolete (excluded from normal search)
- `archived` (optional): Mark as archived
- `supersedes_id` (optional): UUID of older memory this one replaces

#### `elefante-MemoryDelete`

**Purpose**: Permanently delete a memory (Compliance Gated - requires prior search).

**Parameters**:

- `memory_id` (required): UUID
- `reason` (required): Audit trail string

#### `elefante-MemoryConsolidate`

**Purpose**: Deduplicate and canonicalize memories.

**Parameters**:

- `force` (optional): If true, apply changes. Default `false` (dry-run).

---

### Knowledge Graph Operations

#### `elefante-GraphConnect`

**Purpose**: Batch upsert entities and relationships in one call.

**Parameters**:

- `entities`: Array of `{name, type, ref}`. Use `ref` to link relationships.
- `relationships`: Array of `{from_ref, to_ref, relationship_type}`.

**Example**:

```json
{
  "entities": [
    { "name": "Jay", "type": "person", "ref": "user" },
    { "name": "Elefante", "type": "project", "ref": "proj" }
  ],
  "relationships": [
    { "from_ref": "user", "to_ref": "proj", "relationship_type": "created_by" }
  ]
}
```

#### `elefante-GraphQuery`

**Purpose**: Execute raw Cypher queries on Kuzu.

**Parameters**:

- `cypher_query` (required): query string

---

### Context & Sessions

#### `elefante-ContextGet`

**Purpose**: Retrieve full context (memories + graph) for the current task.

**Parameters**:

- `depth`: Graph traversal depth (1-5)
- `limit`: Max memories

#### `elefante-SessionsList`

**Purpose**: List recent work sessions.

---

### Tasks

#### `elefante-TaskCreate`

**Purpose**: Create a task.

**Parameters**:

- `description` (required)
- `priority` (1-10)
- `assigned_agent`
- `subtasks`: Array of optional `{description, priority}` objects for inline subtask creation.

#### `elefante-TaskUpdate`

**Purpose**: Update status/output.
**Parameters**: `task_id`, `status` (pending/in_progress/completed/failed/blocked), `output`.

#### `elefante-TaskGraph`

**Purpose**: View task hierarchy.

---

### ETL (Batch Processing)

#### `elefante-ETLProcess`

**Purpose**: Fetch unclassified memories for agent review.
**Parameters**: `limit`, `include_stats` (bool).

#### `elefante-ETLClassify`

**Purpose**: Submit classification.
**Parameters**: `memory_id`, `summary`, `topic`, `knowledge_type`.

---

### System Operations

#### `elefante-System`

**Purpose**: Enable or disable Elefante Mode.
**Parameters**: `action` ("enable" or "disable").

#### `elefante-SystemStatusGet`

**Purpose**: Get health, lock status, stats.

#### `elefante-DashboardOpen`

**Purpose**: Open dashboard in browser.
**Parameters**: `refresh` (bool) to update snapshot first.

---

### Directives (Always-Active Behavioral Constraints)

Directives are unconditional behavioral rules injected into **every** MCP tool response under the `DIRECTIVES` key. They are stored separately from memories (not in ChromaDB, not in Kuzu) and cannot be outcompeted by similarity scores. Use directives for rules that must be followed regardless of context — things that should never depend on whether a search happens to surface them.

Elefante ships with a built-in system baseline in core code:

- 13 system directives are always present on every install
- at least 6 of them are SDD enforcement directives
- user-added directives are stored alongside them in `~/.elefante/data/directives.json`

#### `elefante-DirectiveAdd`

**Purpose**: Add a persistent behavioral constraint.

**Parameters**:

- `content` (required): The directive text — a clear, actionable rule (e.g., "Never claim success without user confirmation")

**Example**:

```json
{
  "content": "Always verify the MCP server is alive before opening the dashboard"
}
```

#### `elefante-DirectiveList`

**Purpose**: List all active directives (with their IDs for removal).

**Response Notes**:

- Includes both built-in `system` directives and user-stored directives
- Built-in system directives are immutable and always injected

#### `elefante-DirectiveRemove`

**Purpose**: Remove a directive so it stops being injected.

**Parameters**:

- `directive_id` (required): The ID from `elefante-DirectiveList`

**Removal Rule**: Only user directives are removable. Built-in system directives return an explicit error if removal is attempted.

**Storage**: `~/.elefante/data/directives.json` — user directives only. System directives are embedded in core source code.

### Runtime Specification Bootstrap

On first orchestrator use, Elefante automatically seeds the required `specification` memories for:

- SDD Gate 2 leakage surface scan
- SDD Gate 3 scoring formulas
- Elefante Developer Etiquette closure

This is idempotent and requires no manual install step.

---

## 3. Prompts

- **`elefante-grounding`**: System prompt injection for memory awareness.
- **`elefante-context`**: Context retrieval template.
