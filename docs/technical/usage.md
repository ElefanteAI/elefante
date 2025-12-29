# Usage Guide & API Reference

## 1. Natural Language Interaction

Once connected to your IDE, use natural language to interact with Elefante.

**Examples**:
- **Store Info**: "Remember that I prefer using async/await over callbacks."
- **Retrieve Context**: "What do you know about my coding preferences?"
- **Graph Query**: "Show me all technologies related to the Elefante project."
- **Browse Sessions**: "Show me my recent work sessions"
- **Open Dashboard**: "Open the knowledge graph dashboard"

---

## 2. MCP Tools (18 Total)

The MCP server exposes 18 tools to your AI agent:

### Core Memory Operations

#### `elefanteMemoryAdd`
**Purpose**: Store new information with intelligent ingestion.

**YOU ARE ELEFANTE'S BRAIN**: You must classify every memory as you store it. All fields below are expected by default.

---

**Parameters** (all expected by default):

| Parameter | Purpose | Values |
|-----------|---------|--------|
| `content` | The actual text to remember | Free text |
| `layer` | High-level classification: who/what/do | `self`, `world`, `intent` |
| `sublayer` | Fine-grained classification within layer | See table below |
| `memory_type` | Kind of knowledge | `preference`, `fact`, `decision`, `task`, `insight`, `code`, `note`, `conversation` |
| `domain` | Context where this applies | `work`, `personal`, `project`, `learning`, `reference`, `system` |
| `importance` | Priority 1–10 | Use 8+ for critical items |
| `category` | Topic grouping | e.g. `elefante`, `python`, `user-preferences` |
| `tags` | Keywords for filtering | Array of strings |
| `entities` | Graph links | Array of `{name, type}` |

**Layer/sublayer reference**:

| Layer | Sublayers | When to use |
|-------|-----------|-------------|
| `self` | `identity`, `preference`, `constraint` | About the user: who they are, what they like, limits |
| `world` | `fact`, `failure`, `method` | Objective knowledge: truths, errors encountered, how-tos |
| `intent` | `rule`, `goal`, `anti-pattern` | Directives: what to do, what to avoid |

**Advanced parameters** (for special cases only):

| Parameter | Purpose | Default |
|-----------|---------|--------|
| `metadata` | Extra key-value data | `{}` |
| `force_new` | Bypass deduplication (create even if duplicate) | `false` |

---

**Example** (complete, production-ready):
```json
{
  "content": "I prefer using async/await over callbacks",
  "layer": "self",
  "sublayer": "preference",
  "memory_type": "preference",
  "domain": "work",
  "importance": 8,
  "category": "python",
  "tags": ["python", "async", "coding-style"],
  "entities": [
    {"name": "Python", "type": "technology"},
    {"name": "async/await", "type": "concept"}
  ]
}
```

#### `elefanteMemorySearch`
**Purpose**: Retrieve memories using hybrid search (semantic + structured + context)

**CRITICAL**: Query Rewriting Required
- Replace ALL pronouns (it, that, this, he, she, they)
- Make queries standalone and specific
- Include actual entity names from context

**Bad Queries** (will fail):
- "How do I install it?" -> Missing: what is "it"?
- "Fix that error" -> Missing: which error?

**Good Queries** (will succeed):
- "How to install Elefante memory system on Windows"
- "ChromaDB ImportError solution in Python"

**Parameters**:
- `query` (required): Search query (must be explicit, no pronouns)
- `mode` (optional): Search mode - semantic, structured, or hybrid (default: hybrid)
- `limit` (optional): Maximum results to return (default: 10, max: 100)
- `filters` (optional): Filter by memory_type, min_importance, tags, date range
- `min_similarity` (optional): Minimum similarity threshold 0-1 (default: 0.3)
- `include_conversation` (optional): Include recent conversation context (default: true)
- `include_stored` (optional): Include stored memories from databases (default: true)
- `session_id` (optional): Session UUID for conversation context

**Automatic Usage Rules**:
1. ALWAYS call when user asks open-ended questions about the project
2. ALWAYS call when user refers to past decisions or preferences
3. NEVER assume you know the answer if it might be in memory
4. If results are contradictory, most recent memory takes precedence
5. If results are irrelevant, try broader query or switch to semantic mode

**Example**:
```
"What are Jaime's preferences for Python development?"
```

#### `elefanteGraphQuery`
**Purpose**: Execute Cypher queries directly on Kuzu knowledge graph

**Use Cases**:
- Complex relationship traversals
- Pattern matching
- Graph analytics
- Find all entities connected to X
- Show path between A and B
- List all relationships of type Y

**Parameters**:
- `cypher_query` (required): Cypher query to execute
- `parameters` (optional): Query parameters object

**Example**:
```cypher
MATCH (p:Entity {type: 'project'})-[:RELATES_TO]->(t:Entity {name: 'AI'}) 
RETURN p
```

#### `elefanteContextGet`
**Purpose**: Retrieve comprehensive context for current session/task

**Returns**:
- Related memories from ChromaDB
- Connected entities and relationships from Kuzu
- Configurable traversal depth

**Parameters**:
- `session_id` (optional): Session UUID
- `depth` (optional): Relationship traversal depth 1-5 (default: 2)
- `limit` (optional): Maximum memories to retrieve 1-200 (default: 50)

**Example**:
```
(Auto-called by agent at start of task)
```

---

### Graph Building Operations

#### `elefanteGraphEntityCreate`
**Purpose**: Create new entity node in Kuzu knowledge graph

**Entity Types**:
- person, project, file, concept, technology, task
- organization, location, event, custom

**Parameters**:
- `name` (required): Entity name
- `type` (required): Entity type (see list above)
- `properties` (optional): Additional properties object

**Example**:
```
"Create an entity for 'Bob' as a person"
```

#### `elefanteGraphRelationshipCreate`
**Purpose**: Create directed relationship edge between entities

**Relationship Types**:
- relates_to, depends_on, part_of, created_by
- references, blocks, implements, uses, custom

**Parameters**:
- `from_entity_id` (required): Source entity UUID
- `to_entity_id` (required): Target entity UUID
- `relationship_type` (required): Relationship type (see list above)
- `properties` (optional): Additional properties object

**Example**:
```
"Link Bob to Elefante as Maintainer"
```

#### `elefanteGraphConnect`
**Purpose**: Upsert entities and create relationships in one idempotent call.

**Use Cases**:
- Create a small, consistent graph workflow (entities + edges) in one call
- Reduce tool-chaining when building graphs

**Parameters**:
- `entities` (optional): Entities to upsert (use stable `ref` keys)
- `relationships` (optional): Relationships to create
- `include_system_status` (optional): If true, include `elefanteSystemStatusGet` output

---

### Session & History Operations

#### `elefanteSessionsList`
**Purpose**: Retrieve list of recent sessions (episodes) with summaries

**Use Cases**:
- Browse past interactions
- Understand timeline of work
- Review session history

**Parameters**:
- `limit` (optional): Number of episodes to return (default: 10)
- `offset` (optional): Pagination offset (default: 0)

**Example**:
```
"Show me my last 5 work sessions"
```

---

### System Operations

#### `elefanteSystemStatusGet`
**Purpose**: Get combined system status and statistics

**Returns**:
- Elefante Mode state (enabled/disabled)
- Lock status / holder information
- When enabled: system health & usage statistics

**Parameters**: None

**Example**:
```
"Show me Elefante system status"
```

#### `elefanteMemoryConsolidate`
**Purpose**: Deterministic, LLM-free memory cleanup (canonicalize + de-duplicate)

**Use Cases**:
- User getting inconsistent information
- Memory search returns too many near-identical results
- Periodic maintenance

**What it does (V4-compatible)**:
- Assigns stable `canonical_key` (prefers existing SAQ `custom_metadata.title`)
- Quarantines test/E2E memories into a `test` namespace (stored in `custom_metadata.namespace`)
- Marks duplicates as `redundant`/`archived` and links them to the canonical winner

**Safety**:
- Default is **dry-run** (`force=false`) so you can inspect stats before changing data
- Set `force=true` to apply cleanup updates

**Parameters**:
- `force` (optional): Force consolidation even if threshold not met (default: false)

**Example**:
```
"Consolidate my memories to remove duplicates"
```

#### `elefanteMemoryListAll`
**Purpose**: Retrieve ALL memories without semantic filtering (direct inspection/export).

**Use Cases**:
- Export the full memory store
- Debug what is actually stored (bypass ranking)
- Verify migrations/cleanup results

**Parameters**:
- `limit` (optional): Maximum number of memories to return (default: 100)
- `offset` (optional): Pagination offset (default: 0)
- `filters` (optional): Filter by `memory_type`, `min_importance`, `tags`

---

### ETL & Classification Tools (Agent-Brain)

#### `elefanteETLProcess`
**Purpose**: Get unclassified memories for YOU (the agent) to classify.

**V5 Topology Schema**:
- **ring**: core | domain | topic | leaf
- **knowledge_type**: law | principle | method | decision | insight | preference | fact
- **topic**: coding-standards | communication | workflow | agent-behavior | tools-environment | collaboration | general

**Parameters**:
- `limit` (optional): Number of raw memories to process (default: 5)

#### `elefanteETLClassify`
**Purpose**: Submit YOUR classification for a memory retrieved via `elefanteETLProcess`.

**Parameters**:
- `memory_id` (required): Memory UUID
- `ring` (required): Topology ring
- `knowledge_type` (required): Type of knowledge
- `topic` (required): Topic cluster
- `summary` (required): One-line summary (max 200 chars)

#### `elefanteETLStatus`
**Purpose**: Get ETL processing statistics (raw, processed, failed counts).

---

#### `elefanteDashboardOpen`
**Purpose**: Launch and open Knowledge Garden Dashboard in browser

**Features**:
- Visual interface for exploring memory graph
- View connections between concepts
- Filter by 'Spaces'
- Interactive graph visualization

**Parameters**:
- `refresh` (optional, default: false): If true, regenerate dashboard snapshot before opening (requires Elefante Mode enabled)

**Example**:
```
"Open the dashboard" or "Show me my knowledge graph"
```

#### `elefanteMemoryMigrateToV3`
**Purpose**: Administrative migration tool that re-classifies existing memories into V3 schema (`layer`/`sublayer`) and writes updates back.

**When to use**:
- After changing classification logic
- After importing legacy memories that lack V3 fields

**Parameters**:
- `limit` (optional): Batch size per iteration (default: 500)

**Example**:
```
"Migrate memories to V3"
```

---

### ELEFANTE_MODE Operations (Multi-IDE Safety)

> **v1.1.0 Update**: Transaction-scoped locking now handles multi-IDE safety automatically. The `enable`/`disable` calls below are retained for backward compatibility but are now **no-ops** - the system is always enabled and uses per-operation locks instead.

#### `elefanteSystemEnable`
**Purpose**: Backward-compatible no-op (v1.1.0+)

**v1.1.0 Behavior**: Always returns success. Elefante now uses transaction-scoped locking where each write operation acquires and releases locks automatically (milliseconds per operation). No manual enable/disable ceremony needed.

**Legacy Behavior (v1.0.1)**: Acquired exclusive locks and enabled memory operations.

**Parameters**: None

**Returns**: Success message (always succeeds in v1.1.0)

**Example**:
```
"Enable Elefante" or "Start memory system"
```

#### `elefanteSystemDisable`
**Purpose**: Release resources and clear locks

**v1.1.0 Behavior**: Clears any stale locks and releases resources. Safe to call but not required - locks auto-release after each operation.

**Parameters**: None

**Example**:
```
"Disable Elefante" or "Release memory locks"
```

**Status Check**: Use `elefanteSystemStatusGet` to check system status and statistics.

---

## 2.1 MCP Prompts (2 Total)

These are MCP **prompts** (not tools). Some IDEs can inject them into the model context to enforce memory-aware behavior.

### `elefante-grounding`
**Purpose**: Default grounding prompt that reminds the agent to use Elefante before answering.

### `elefante-context`
**Purpose**: A prompt template that fetches context for a given topic before answering.

---

## 3. Python API (For Scripting)

You can import the core logic into your own Python scripts:

```python
import asyncio
from src.core.orchestrator import get_orchestrator

async def main():
    orch = get_orchestrator()
    
    # Add Memory
    await orch.add_memory(
        content="I prefer FastAPI over Flask",
        memory_type="preference",
        importance=8,
        tags=["python", "web-framework"]
    )
    
    # Hybrid Search
    results = await orch.search_memories(
        query="What are my Python preferences?",
        mode="hybrid",
        limit=10
    )
    for r in results:
        print(f"- {r.memory.content} (Score: {r.score})")
    
    # Graph Query
    graph_results = await orch.query_graph(
        cypher_query="MATCH (n:Entity {type: 'technology'}) RETURN n LIMIT 10"
    )
    print(f"Found {len(graph_results)} technologies")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 4. Testing

### End-to-End Test
Run complete system verification:
```bash
python scripts/test_end_to_end.py
```

Verifies:
- Memory persistence
- Search functionality
- Graph linking
- MCP tool integration

### Health Check
Verify database connectivity:
```bash
python scripts/health_check.py
```

Checks:
- ChromaDB connection
- Kuzu connection
- Embedding model
- MCP server status

---

## 5. Best Practices

### Memory Storage
- **Be Specific**: "I prefer async/await" vs "I like that"
- **Add Context**: Include relevant entities and relationships
- **Use Tags**: Categorize for easier retrieval
- **Set Importance**: Help prioritize critical information

### Memory Retrieval
- **Rewrite Queries**: Replace pronouns with actual entities
- **Use Hybrid Mode**: Combines semantic + structured + context
- **Adjust Similarity**: Lower threshold for broader results
- **Check Timestamps**: Recent memories may override older ones

### Graph Building
- **Create Entities First**: Before creating relationships
- **Use Standard Types**: Stick to predefined entity/relationship types
- **Add Properties**: Enrich nodes with metadata
- **Verify Connections**: Use `elefanteGraphQuery` to check relationships

### System Maintenance
- **Monitor Stats**: Regular `elefanteSystemStatusGet` checks
- **Consolidate Periodically**: Run `elefanteMemoryConsolidate` monthly
- **Review Episodes**: Use `elefanteSessionsList` to track progress
- **Backup Memories**: Use `elefanteMemoryListAll` for exports

---

## 6. Troubleshooting

### Common Issues

**"No memories found"**
- Check if memories were actually stored (`elefanteSystemStatusGet`)
- Try broader query or lower similarity threshold
- Use `elefanteMemoryListAll` to verify database content

**"Duplicate memories"**
- Run `elefanteMemoryConsolidate` to merge
- Check intelligent ingestion flags (NEW/REDUNDANT)
- Review memory timestamps

**"Slow search"**
- Reduce `limit` parameter
- Use `mode="semantic"` for faster results
- Check `elefanteSystemStatusGet` for performance issues

**"Graph query fails"**
- Verify Cypher syntax
- Check entity/relationship types exist
- Use `elefanteSystemStatusGet` to see available node types

---

## 7. Advanced Usage

### Custom Workflows

**Daily Standup Memory**:
```python
await orch.add_memory(
    content="Today I completed the authentication module and started on the API endpoints",
    memory_type="task",
    importance=7,
    tags=["daily-standup", "progress"],
    entities=[
        {"name": "Authentication Module", "type": "project"},
        {"name": "API Endpoints", "type": "project"}
    ]
)
```

**Knowledge Graph Exploration**:
```cypher
// Find all projects I'm working on
MATCH (me:Entity {name: 'Jaime'})-[:WORKS_ON]->(p:Entity {type: 'project'})
RETURN p.name, p.properties

// Find technology dependencies
MATCH (p:Entity {type: 'project'})-[:USES]->(t:Entity {type: 'technology'})
RETURN p.name, collect(t.name) as technologies
```

**Session Review**:
```python
# Get recent episodes
episodes = await orch.get_episodes(limit=5)
for ep in episodes:
    print(f"Session {ep.id}: {ep.summary}")
    print(f"  Memories: {ep.memory_count}")
    print(f"  Duration: {ep.duration}")
```

---

**For complete system architecture, see [`architecture.md`](architecture.md)**  
**For installation help, see [`installation.md`](installation.md)**  
**For dashboard usage, see [`dashboard.md`](dashboard.md)**
