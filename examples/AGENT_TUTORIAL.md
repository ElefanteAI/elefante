# Elefante Agent Tutorial

> **Version:** 2.7.1  
> **Audience:** AI Agents using MCP tools  
> **Tool naming:** All tools use `elefante-PascalCase` convention

---

## STEP 0: Enable Elefante Mode

**ALWAYS do this first.** Acquires database locks.

```json
Tool: elefante-System
Arguments: { "action": "enable" }
```

Expected response:

```json
{ "status": "enabled", "message": "Elefante Mode activated" }
```

If already enabled: `{"status": "already_enabled"}`

Use `"force": true` to force-acquire locks from another session.

---

## STEP 1: Search Before Writing (Compliance Gate)

**You MUST search before you can write.** The compliance gate blocks `elefante-MemoryAdd`, `elefante-MemoryUpdate`, `elefante-MemoryDelete`, and `elefante-GraphConnect` until you call `elefante-MemorySearch` at least once per session.

```json
Tool: elefante-MemorySearch
Arguments: {
  "query": "user communication preferences style",
  "limit": 5
}
```

**CRITICAL:** Rewrite vague queries to be specific:

- Bad: `"How do I install it?"`
- Good: `"How to install Elefante memory system"`

**Required fields:**

- `query` — Natural language search (explicit, no pronouns)

**Optional fields:**

- `limit` — Max results, 1–100 (default: 10)
- `mode` — `semantic` | `structured` | `hybrid` (default: `hybrid`)
- `min_similarity` — 0.0–1.0 threshold (default: 0.3)
- `include_conversation` — Include conversation memories (default: `true`)
- `include_stored` — Include stored memories (default: `true`)
- `session_id` — Filter by session UUID
- `list_all` — If `true`, returns all memories (paginated). Replaces the old `MemoryListAll` tool.
- `offset` — Pagination offset for `list_all` (default: 0)
- `filters` — Object with:
  - `memory_type` — Filter by type
  - `domain` — Filter by domain
  - `category` — Filter by category
  - `min_score` — Minimum behavioral relevance score, 0–100
  - `tags` — Filter by tags
  - `start_date`, `end_date` — Date range

Expected response:

```json
{
  "results": [
    {
      "content": "The user prefers concise communication without fluff.",
      "score": 72,
      "memory_type": "preference",
      "tags": ["preference", "communication"]
    }
  ],
  "total": 1
}
```

---

## STEP 2: Add a Memory

Now that you've searched (compliance gate unlocked), you can store memories.

```json
Tool: elefante-MemoryAdd
Arguments: {
  "content": "The user prefers concise communication without fluff.",
  "memory_type": "preference",
  "domain": "personal",
  "category": "communication",
  "tags": ["preference", "communication"]
}
```

**Required fields:**

- `content` — What to remember (string)

**Recommended fields (YOU classify these):**

- `memory_type` — `fact` | `decision` | `preference` | `insight` | `note` | `conversation` (default: `fact`). Determines decay rate.
- `domain` — `work` | `personal` | `learning` | `project` | `reference` | `system`
- `category` — Topic grouping (e.g., "elefante", "python")
- `tags` — Array of keywords
- `entities` — Array of `{name, type}` objects to link in the knowledge graph
- `force_new` — `true` to bypass deduplication check

**What you do NOT set:**

- **Score** — Starts at 50 for every memory. Changes through behavior (access, time decay). Not a parameter.
- **Decay rate** — Derived automatically from `memory_type`.

---

## STEP 3: Get Session Context

Retrieve all relevant context for current work.

```json
Tool: elefante-ContextGet
Arguments: {
  "depth": 2,
  "limit": 50
}
```

**Optional fields:**

- `session_id` — Session UUID
- `depth` — Graph traversal depth, 1–5 (default: 2)
- `limit` — Max results, 1–200 (default: 50)

Returns: Recent memories, user profile, active entities, and graph connections.

---

## STEP 4: Knowledge Graph Operations

### Batch Create Entities and Relationships

The `elefante-GraphConnect` tool handles both entity creation and relationship creation in a single call.

```json
Tool: elefante-GraphConnect
Arguments: {
  "entities": [
    { "ref": "e1", "name": "FastAPI", "type": "technology", "properties": { "language": "python" } },
    { "ref": "e2", "name": "Python", "type": "technology" }
  ],
  "relationships": [
    { "relationship_type": "USES", "from_ref": "e1", "to_ref": "e2" }
  ]
}
```

- Use `ref` as a local identifier within the call to link entities to relationships.
- Entities are upserted (created or updated if they already exist).

### Query the Graph (Cypher)

```json
Tool: elefante-GraphQuery
Arguments: {
  "cypher_query": "MATCH (t:Entity {type: 'technology'}) RETURN t.name LIMIT 10"
}
```

Use `parameters` for parameterized queries:

```json
{
  "cypher_query": "MATCH (e:Entity) WHERE e.type = $type RETURN e.name",
  "parameters": { "type": "technology" }
}
```

---

## STEP 5: Tasks

### Create a Task (with optional subtasks)

```json
Tool: elefante-TaskCreate
Arguments: {
  "description": "Refactor authentication module",
  "priority": 7,
  "assigned_agent": "copilot",
  "subtasks": [
    { "description": "Extract JWT logic into helper", "priority": 5 },
    { "description": "Add refresh token support", "priority": 8 }
  ]
}
```

### Update Task Status

```json
Tool: elefante-TaskUpdate
Arguments: {
  "task_id": "task-uuid",
  "status": "completed",
  "output": "Refactored into src/auth/jwt_helper.py"
}
```

Status values: `pending` | `in_progress` | `completed` | `failed` | `blocked`

### View Task Hierarchy

```json
Tool: elefante-TaskGraph
Arguments: { "task_id": "task-uuid" }
```

Omit `task_id` to see all root tasks.

---

## STEP 6: Maintenance

### Consolidate Memories (Cleanup)

```json
Tool: elefante-MemoryConsolidate
Arguments: { "force": false }
```

- `force: false` — Dry run (preview changes)
- `force: true` — Apply deduplication and cleanup

### List All Memories

```json
Tool: elefante-MemorySearch
Arguments: { "query": "", "list_all": true, "limit": 100 }
```

### Open Dashboard

```json
Tool: elefante-DashboardOpen
Arguments: { "refresh": true }
```

### Check System Status

```json
Tool: elefante-SystemStatusGet
Arguments: {}
```

---

## STEP 7: Disable When Done

**Release locks for other IDEs.**

```json
Tool: elefante-System
Arguments: { "action": "disable" }
```

---

## Behavioral Relevance (Scoring)

Elefante does **not** use human-assigned importance. Every memory starts at score **50** and changes over time based on three behavioral signals:

| Signal            | What it measures         | Effect                                                       |
| ----------------- | ------------------------ | ------------------------------------------------------------ |
| **Recency**       | Days since creation      | Memories decay exponentially. Rate depends on `memory_type`. |
| **Freshness**     | Days since last access   | Recently retrieved memories get a boost. Stale ones fade.    |
| **Reinforcement** | Number of times accessed | Frequently used memories grow stronger (logarithmic).        |

A preference you set 6 months ago and still use? Score stays high. An architecture decision from a year ago that you never reference? It fades naturally.

### Decay by Memory Type

| Type           | Half-Life | Why                     |
| -------------- | --------- | ----------------------- |
| `preference`   | ~347 days | Stable personal choices |
| `decision`     | ~139 days | Get revisited over time |
| `fact`         | ~139 days | Objective truths evolve |
| `insight`      | ~87 days  | Validated or forgotten  |
| `note`         | ~46 days  | Contextual, transient   |
| `conversation` | ~28 days  | Ephemeral               |

---

## Memory Type Guide

| Type           | Use For                                     |
| -------------- | ------------------------------------------- |
| `fact`         | Objective truths, configurations            |
| `decision`     | Architecture choices, rationale             |
| `preference`   | User preferences, style choices, rules      |
| `insight`      | Patterns, learned behaviors                 |
| `note`         | General notes, documentation, code snippets |
| `conversation` | Chat history, discussions                   |

---

## Domain Guide

| Domain      | Use For                    |
| ----------- | -------------------------- |
| `work`      | Professional context       |
| `personal`  | User identity, preferences |
| `learning`  | Educational content        |
| `project`   | Specific project context   |
| `reference` | Documentation, guides      |
| `system`    | Elefante/system settings   |

---

## Common Patterns

### Store User Preference

```json
{
  "content": "User prefers dark mode in all IDEs.",
  "memory_type": "preference",
  "domain": "personal",
  "category": "ui",
  "tags": ["preference", "ui", "ide"]
}
```

### Store Critical Constraint

```json
{
  "content": "NEVER commit directly to main branch.",
  "memory_type": "preference",
  "domain": "work",
  "category": "git",
  "tags": ["rule", "git", "workflow"]
}
```

### Store Project Decision

```json
{
  "content": "Using PostgreSQL for persistence, Redis for caching.",
  "memory_type": "decision",
  "domain": "project",
  "category": "architecture",
  "tags": ["architecture", "database"]
}
```

### Store Current State

```json
{
  "content": "Current sprint: migrating auth to OAuth2.",
  "memory_type": "fact",
  "domain": "project",
  "category": "sprint",
  "tags": ["sprint", "auth"]
}
```

### Search for Context

```json
{
  "query": "PostgreSQL database architecture decisions for this project",
  "mode": "hybrid",
  "limit": 5,
  "filters": { "min_score": 30 }
}
```

---

## Error Handling

| Error                         | Cause                           | Fix                                               |
| ----------------------------- | ------------------------------- | ------------------------------------------------- |
| `"Elefante Mode not enabled"` | Forgot Step 0                   | Call `elefante-System` with `action: "enable"`    |
| `"Database locked"`           | Another IDE has lock            | Use `"force": true` or disable in other IDE first |
| `"Compliance gate"`           | Tried to write before searching | Call `elefante-MemorySearch` first                |

---

## Checklist

- [ ] Called `elefante-System` with `action: "enable"` first
- [ ] Called `elefante-MemorySearch` before any write operations
- [ ] Used correct `memory_type` (determines decay rate)
- [ ] Used meaningful `tags` for filtering
- [ ] Called `elefante-System` with `action: "disable"` when switching IDEs

---
