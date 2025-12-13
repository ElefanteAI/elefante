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

## 2. MCP Tools (15 Total)

The MCP server exposes 15 tools to your AI agent:

### Core Memory Operations

#### `elefanteMemoryAdd`
**Purpose**: Store new information with intelligent ingestion

**Features**:
- Automatically analyzes against existing knowledge
- Flags as NEW/REDUNDANT/RELATED/CONTRADICTORY
- Links to existing concepts in graph
- No manual duplicate checking needed

**Parameters**:
- `content` (required): The memory content to store
- `memory_type` (optional): Type of memory (conversation, fact, insight, code, decision, task, note)
- `importance` (optional): Importance level 1-10 (default: 5)
- `tags` (optional): Array of tags for categorization
- `entities` (optional): Array of entities to link in knowledge graph
- `metadata` (optional): Additional metadata object

**Example**:
```
"Remember that I'm working on Project Omega using Python and FastAPI"
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
**Purpose**: Retrieve ALL memories without semantic filtering

**Use Cases**:
- Database inspection
- Debugging
- Exporting all memories
- Browsing complete memory collection
- Comprehensive view needed

**Note**: For relevance-based search, use `elefanteMemorySearch` instead

**Parameters**:
- `limit` (optional): Maximum memories to return 1-500 (default: 100)
- `offset` (optional): Number to skip for pagination (default: 0)
- `filters` (optional): Filter by memory_type, min_importance, tags

**Example**:
```
"List all my memories for backup"
```

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

#### `elefanteGraphConnect`
**Purpose**: Upsert entities and create relationships in a single workflow call

**Use Cases**:
- Create two (or more) entities and link them without tool-chaining
- Create relationship edges using stable entity refs

**Parameters**:
- `entities` (optional): Array of entities with `ref` and either `id` or (`name` + `type`)
- `relationships` (optional): Array of relationships using `from_ref`/`to_ref` or explicit UUIDs
- `include_system_status` (optional, default: false): Include `elefanteSystemStatusGet` output

**Example**:
```
"Create entities for 'Elefante' (project) and 'Kuzu' (technology) and link them"
```

---

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

#### `elefanteSystemEnable`
**Purpose**: Acquire exclusive locks and enable memory operations

**CRITICAL**: Server starts in OFF mode by default. User must call this tool before any memory operations work.

**Behavior**:
- Acquires exclusive locks on ChromaDB and Kuzu databases
- Stores lock holder info (PID, timestamp)
- Enables all memory tools

**Parameters**: None

**Returns**:
- Success: Lock acquired, mode enabled
- Failure: Another IDE holds locks (shows holder info)

**Example**:
```
"Enable Elefante" or "Start memory system"
```

#### `elefanteSystemDisable`
**Purpose**: Release exclusive locks and return to OFF state

**Use Case**: Before switching to another IDE (VS Code -> Cursor -> Claude Desktop)

**Behavior**:
- Releases all database locks
- Cleans up lock files
- Returns server to OFF state

**Parameters**: None

**Example**:
```
"Disable Elefante" or "Release memory locks"
```

**Status Check**: Use `elefanteSystemStatusGet` to check mode/locks and (when enabled) system statistics.

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
