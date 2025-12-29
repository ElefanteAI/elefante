# Elefante Dashboard Usage Guide

See also:
- [Dashboard Overhaul SPEC](dashboard-overhaul-spec.md)
- [Dashboard Snapshot Contract](dashboard-snapshot-contract.md)

## Quick Start

### Starting the Dashboard

**Option 1: Via MCP Tool (Recommended)**
Use the `elefanteDashboardOpen` tool:
```
"Open the dashboard"
```
This will start the server and open your browser automatically.

**Option 2: Manual Start**
```bash
# From project root
python -m src.dashboard.server
```

Dashboard will be available at: **http://127.0.0.1:8000**

### Stopping the Dashboard

Press `Ctrl+C` in the terminal running the server.

---

## Dashboard Features

### 1. **Memory Visualization**

- **Interactive Graph**: Each green dot represents a memory
- **Node Labels**: Truncated descriptions (first 3 words) shown below each node
- **Hover Tooltips**: Curated-first (title + summary + explainable link counts)
- **Zoom Controls**: Use mouse wheel or zoom buttons (bottom right)
- **Pan**: Click and drag to move around the graph

### 2. **Statistics Panel** (Top Left)

- **Total Memories**: Current count in the system
- **Total Episodes**: Number of conversation sessions

## 4. **Visual Physics Engine (V30 Only)** 

- **Power Law Sizing**: Node size = `8 + (Importance² * 0.4)`.
  - Landmark Memories (Imp 10) are massive (48px) anchors.
  - Detail Memories (Imp 1) are small (8px) particles.
- **Oort Cloud Protocol**: Orphan nodes (no links) are physically locked into a deep-space orbital band (400-600px) to prevent cluttering the "Neural Web" center.
- **Electric Edges**: Relationships pulse with a gradient animation, flowing towards the target.

---

## Adding Memories

### Method 1: Via MCP Tools (Recommended)

When using Roo-Cline, memories are automatically added during conversations. You can also explicitly use:

```
Use the elefanteMemoryAdd MCP tool to store this information
```

### Method 2: Via Python Script

```python
import asyncio
from src.core.orchestrator import get_orchestrator

async def add_memory():
    orchestrator = get_orchestrator()

    result = await orchestrator.add_memory(
        content="Your memory content here",
        metadata={
            "layer": "world", # V3 Schema
            "sublayer": "fact",
            "importance": 5
        }
    )

    print(f"Memory added: {result.id}")

asyncio.run(add_memory())
```

### Method 3: Via Dashboard API

```bash
curl -X POST http://localhost:8000/api/memories \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Your memory content",
    "layer": "world",
    "sublayer": "fact",
    "importance": 5
  }'
```

---

## Snapshot Refresh

**IMPORTANT**: The dashboard is snapshot-driven. If new memories are added, you must regenerate the snapshot and then refresh the browser.

### How It Works:

1. **Add a memory** using MCP or scripts
2. **Regenerate the dashboard snapshot**: 
   - **Via Tool**: `elefanteDashboardOpen(refresh=True)`
   - **Via Script**: `python scripts/update_dashboard_data.py`
3. **Refresh your browser** (Cmd+R / F5)

### What Gets Updated:

-  Memory count in statistics panel
-  New nodes in the graph visualization
-  Relationships between memories
-  All filters and search results

### Notes

- Snapshot generation is the only step allowed to touch databases.
- Dashboard runtime reads `DATA_DIR/dashboard_snapshot.json` and must remain read-only.

---

## Memory Types (V3 Schema)

| Layer      | Sublayer                    | Color          | Meaning                    |
| :--------- | :-------------------------- | :------------- | :------------------------- |
| **SELF**   | `identity`, `preference`    |  Red/Orange  | User Persona & Constraints |
| **WORLD**  | `fact`, `failure`, `method` |  Blue/Purple | Objective Knowledge        |
| **INTENT** | `rule`, `goal`              |  White/Green | Directives & Plans         |

---

## Troubleshooting

### Dashboard Shows 0 Memories

1. **Hard refresh browser**: Cmd+Shift+R (clears cache)
2. **Check database**: Run `python -c "from src.core.orchestrator import get_orchestrator; import asyncio; print(asyncio.run(get_orchestrator().get_stats()))"`
3. **Check server logs**: Look for errors in the terminal

### Graph Not Loading (Blank Screen)

1. **Check Binding**: Server MUST bind to `0.0.0.0`, not `127.0.0.1`.
2. **Check API**: Visit http://localhost:8000/api/stats and ensure it returns a flat JSON object (no `{"success": true}` wrapper).
3. **Verify Static Files**: Ensure `ui/dist/index.html` exists.

### Memory Not Appearing After Adding

1. **Refresh browser**: Press F5
2. **Check if memory was added**: Visit http://localhost:8000/api/stats
3. **Verify no database lock**: Only one process can access Kuzu database at a time

---

## Database Locations

- **ChromaDB**: `~/.elefante/data/chroma` (or project specific)
- **Kuzu**: `~/.elefante/data/kuzu_db`
- **Logs**: `logs/`

---

## Advanced Usage

### Querying the Knowledge Graph

```python
from src.core.orchestrator import get_orchestrator
import asyncio

async def query_graph():
    orchestrator = get_orchestrator()

    # Cypher query example
    results = await orchestrator.graph_store.execute_query(
        "MATCH (n:Entity) RETURN n.name LIMIT 10"
    )

    for result in results:
        print(result)

asyncio.run(query_graph())
```

### Searching Memories

```python
results = await orchestrator.search_memories(
    query="Python decorators",
    mode="hybrid",  # semantic, structured, or hybrid
    limit=10
)
```

---

## Performance Notes

- **Memory Limit**: System can handle 10,000+ memories efficiently
- **Graph Rendering**: Limited to 500 nodes by default (configurable)
- **Search Speed**: Semantic search typically <100ms
- **Auto-Refresh**: Instant (just browser refresh needed)

---

## Support

For issues or questions:

1. Check logs in `~/.elefante/logs/` (or your configured logs directory)
2. Review [`docs/debug/dashboard-compendium.md`](../debug/dashboard-compendium.md) for common issues
3. Ensure only one process accesses the database at a time
