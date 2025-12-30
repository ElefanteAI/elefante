# Elefante Agent Tutorial

> **Version:** 1.6.2  
> **Audience:** AI Agents using MCP tools

---

## STEP 0: Enable Elefante Mode

**ALWAYS do this first.** Acquires database locks.

```json
Tool: elefanteSystemEnable
Arguments: {}
```

Expected response:
```json
{"status": "enabled", "message": "Elefante Mode activated"}
```

If already enabled: `{"status": "already_enabled"}`

---

## STEP 1: Add Your First Memory

Store a simple fact.

```json
Tool: elefanteMemoryAdd
Arguments: {
  "content": "The user prefers concise communication without fluff.",
  "importance": 8,
  "layer": "self",
  "sublayer": "preference",
  "memory_type": "preference",
  "domain": "personal",
  "category": "communication",
  "tags": ["preference", "communication"]
}
```

**Required fields:**
- `content` - What to remember (string)

**Recommended fields (YOU classify these):**
- `importance` - 1-10 scale (8+ for preferences, decisions)
- `layer` - `self` | `world` | `intent`
- `sublayer` - See Layer Guide below
- `memory_type` - `conversation` | `fact` | `insight` | `code` | `decision` | `task` | `note` | `preference`
- `domain` - `work` | `personal` | `learning` | `project` | `reference` | `system`
- `category` - Topic grouping (e.g., "elefante", "python")
- `tags` - Array of keywords

Expected response:
```json
{
  "status": "stored",
  "memory_id": "abc123...",
  "title": "Self-Pref-Communication-Concise"
}
```

---

## STEP 2: Search Memories

Retrieve what you stored.

```json
Tool: elefanteMemorySearch
Arguments: {
  "query": "user communication preferences style",
  "limit": 5
}
```

**CRITICAL:** Rewrite vague queries to be specific:
-  Bad: `"How do I install it?"` 
-  Good: `"How to install Elefante memory system"`

**Required fields:**
- `query` - Natural language search (explicit, no pronouns)

**Optional fields:**
- `limit` - Max results (default: 10)
- `mode` - `semantic` | `structured` | `hybrid` (default: hybrid)
- `min_similarity` - 0.0-1.0 threshold (default: 0.3)
- `filters` - Object with `memory_type`, `domain`, `min_importance`, etc.

Expected response:
```json
{
  "results": [
    {
      "content": "The user prefers concise communication without fluff.",
      "score": 0.92,
      "memory_type": "preference",
      "importance": 8,
      "tags": ["preference", "communication"]
    }
  ],
  "total": 1
}
```

---

## STEP 3: Get Session Context

Retrieve all relevant context for current work.

```json
Tool: elefanteContextGet
Arguments: {
  "session_id": "optional-session-id"
}
```

Returns: Recent memories, user profile, active entities.

---

## STEP 4: Advanced - Graph Operations

### Create an Entity

```json
Tool: elefanteGraphEntityCreate
Arguments: {
  "name": "FastAPI",
  "entity_type": "technology",
  "properties": {
    "category": "web-framework",
    "language": "python"
  }
}
```

### Create a Relationship

```json
Tool: elefanteGraphRelationshipCreate
Arguments: {
  "source_name": "FastAPI",
  "target_name": "Python",
  "relationship_type": "USES"
}
```

### Query the Graph (Cypher)

```json
Tool: elefanteGraphQuery
Arguments: {
  "query": "MATCH (t:Entity {type: 'technology'}) RETURN t.name LIMIT 10"
}
```

---

## STEP 5: Maintenance

### Consolidate Memories (Cleanup)

```json
Tool: elefanteMemoryConsolidate
Arguments: {
  "force": false
}
```

- `force: false` = Dry run (preview changes)
- `force: true` = Apply changes

### List All Memories

```json
Tool: elefanteMemoryListAll
Arguments: {
  "limit": 100
}
```

### Open Dashboard

```json
Tool: elefanteDashboardOpen
Arguments: {
  "refresh": true
}
```

---

## STEP 6: Disable When Done

**Release locks for other IDEs.**

```json
Tool: elefanteSystemDisable
Arguments: {}
```

---

## Memory Importance Guide

| Score | Meaning | Examples |
|-------|---------|----------|
| 1-3 | Ephemeral | Casual chat, temp notes |
| 4-6 | Useful | General context, observations |
| 7 | Important | Project facts, methods |
| 8-9 | Critical | Preferences, decisions, key insights |
| 10 | Sacred | Laws, constraints, never forget |

---

## Memory Type Guide

| Type | Use For |
|------|---------|
| `conversation` | Chat history, discussions |
| `fact` | Objective truths, configurations |
| `insight` | Patterns, learned behaviors |
| `code` | Code snippets, implementations |
| `decision` | Architecture choices, rationale |
| `task` | TODOs, action items |
| `note` | General notes, documentation |
| `preference` | User preferences, style choices |

---

## Domain Guide

| Domain | Use For |
|--------|---------|
| `work` | Professional context |
| `personal` | User identity, preferences |
| `learning` | Educational content |
| `project` | Specific project context |
| `reference` | Documentation, guides |
| `system` | Elefante/system settings |

---

## Layer/Sublayer Guide

| Layer | Sublayer | Use For |
|-------|----------|---------|
| `self` | `identity` | Who the user is |
| `self` | `preference` | User preferences |
| `self` | `constraint` | User rules/laws |
| `world` | `fact` | General knowledge |
| `world` | `failure` | Errors, bugs, lessons |
| `world` | `method` | How-to, procedures |
| `intent` | `rule` | Behavioral rules |
| `intent` | `goal` | Objectives, targets |
| `intent` | `anti-pattern` | What to avoid |

---

## Common Patterns

### Store User Preference
```json
{
  "content": "User prefers dark mode in all IDEs.",
  "importance": 7,
  "layer": "self",
  "sublayer": "preference",
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
  "importance": 10,
  "layer": "self",
  "sublayer": "constraint",
  "memory_type": "decision",
  "domain": "work",
  "category": "git",
  "tags": ["rule", "git", "workflow"]
}
```

### Store Project Decision
```json
{
  "content": "Using PostgreSQL for persistence, Redis for caching.",
  "importance": 8,
  "layer": "world",
  "sublayer": "fact",
  "memory_type": "decision",
  "domain": "project",
  "category": "architecture",
  "tags": ["architecture", "database"]
}
```

### Store a Method/How-To
```json
{
  "content": "To deploy: run ./scripts/deploy.sh with ENV=production",
  "importance": 7,
  "layer": "world",
  "sublayer": "method",
  "memory_type": "note",
  "domain": "project",
  "category": "deployment",
  "tags": ["deployment", "script"]
}
```

### Search for Context
```json
{
  "query": "PostgreSQL database architecture decisions for this project",
  "mode": "hybrid",
  "limit": 5,
  "filters": {
    "min_importance": 7
  }
}
```

---

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| `"Elefante Mode not enabled"` | Forgot Step 0 | Call `elefanteSystemEnable` |
| `"Database locked"` | Another IDE has lock | Disable in other IDE first |
| `"Memory blocked"` | Test tag without override | Remove `test` tag or set env var |

---

## Checklist

- [ ] Called `elefanteSystemEnable` first
- [ ] Set appropriate `importance` (not everything is 10)
- [ ] Used meaningful `tags` for filtering
- [ ] Chose correct `layer`/`sublayer`
- [ ] Called `elefanteSystemDisable` when switching IDEs

---

