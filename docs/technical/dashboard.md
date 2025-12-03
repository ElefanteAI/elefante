# Elefante Dashboard Usage Guide

## Quick Start

### Starting the Dashboard
```bash
cd Elefante
.venv\Scripts\python.exe -m src.dashboard.server
```

Dashboard will be available at: **http://127.0.0.1:8000**

### Stopping the Dashboard
Press `Ctrl+C` in the terminal running the server.

---

## Dashboard Features

### 1. **Memory Visualization**
- **Interactive Graph**: Each green dot represents a memory
- **Node Labels**: Truncated descriptions (first 3 words) shown below each node
- **Hover Tooltips**: Full description and timestamp appear on hover
- **Zoom Controls**: Use mouse wheel or zoom buttons (bottom right)
- **Pan**: Click and drag to move around the graph

### 2. **Statistics Panel** (Top Left)
- **Total Memories**: Current count in the system
- **Total Episodes**: Number of conversation sessions

### 3. **Spaces Filter** (Left Sidebar)
- Filter memories by category/space
- "All Spaces" shows everything

---

## Adding Memories

### Method 1: Via MCP Tools (Recommended)
When using Roo-Cline, memories are automatically added during conversations. You can also explicitly use:

```
Use the addMemory MCP tool to store this information
```

### Method 2: Via Python Script
```python
import asyncio
from src.core.orchestrator import MemoryOrchestrator

async def add_memory():
    orchestrator = MemoryOrchestrator()
    
    result = await orchestrator.add_memory(
        content="Your memory content here",
        memory_type="note",  # or: conversation, fact, insight, code, decision, task
        importance=5,        # 1-10 scale
        tags=["tag1", "tag2"]
    )
    
    print(f"Memory added: {result.id}")

asyncio.run(add_memory())
```

### Method 3: Via Dashboard API
```bash
curl -X POST http://127.0.0.1:8000/api/memories \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Your memory content",
    "memory_type": "note",
    "importance": 5,
    "tags": ["test"]
  }'
```

---

## Auto-Refresh Feature ✅

**IMPORTANT**: The dashboard automatically reflects new memories without requiring server restart!

### How It Works:
1. **Add a memory** using any method above
2. **Refresh your browser** (press F5 or Ctrl+R)
3. **New memory appears** immediately in the graph

### What Gets Updated:
- ✅ Memory count in statistics panel
- ✅ New nodes in the graph visualization
- ✅ Relationships between memories
- ✅ All filters and search results

### No Need To:
- ❌ Restart the dashboard server
- ❌ Rebuild the frontend
- ❌ Reinitialize the database
- ❌ Clear browser cache (unless you updated the code)

---

## Memory Types

| Type | Purpose | Example |
|------|---------|---------|
| `conversation` | Chat history | "User asked about Python decorators" |
| `fact` | Factual information | "Project uses FastAPI 0.104.1" |
| `insight` | Learned patterns | "User prefers detailed error messages" |
| `code` | Code snippets | "Function to parse JSON config" |
| `decision` | Design choices | "Chose PostgreSQL over MongoDB" |
| `task` | Action items | "TODO: Add unit tests for auth" |
| `note` | General notes | "Meeting scheduled for Friday" |

---

## Troubleshooting

### Dashboard Shows 0 Memories
1. **Hard refresh browser**: Ctrl+Shift+R (clears cache)
2. **Check database**: Run `python -c "from src.core.orchestrator import MemoryOrchestrator; import asyncio; print(asyncio.run(MemoryOrchestrator().get_stats()))"`
3. **Check server logs**: Look for errors in the terminal

### Graph Not Loading
1. **Check browser console**: Press F12, look for JavaScript errors
2. **Verify API**: Visit http://127.0.0.1:8000/api/stats in browser
3. **Restart server**: Ctrl+C, then restart

### Memory Not Appearing After Adding
1. **Refresh browser**: Press F5
2. **Check if memory was added**: Visit http://127.0.0.1:8000/api/stats
3. **Verify no database lock**: Only one process can access Kuzu database at a time

---

## Database Locations

- **ChromaDB (Vector Store)**: `C:\Users\JaimeSubiabreCistern\.elefante\data\chroma`
- **Kuzu (Knowledge Graph)**: `C:\Users\JaimeSubiabreCistern\.elefante\data\kuzu_db`
- **Logs**: `C:\Users\JaimeSubiabreCistern\.elefante\logs\`

---

## Advanced Usage

### Querying the Knowledge Graph
```python
from src.core.orchestrator import MemoryOrchestrator
import asyncio

async def query_graph():
    orchestrator = MemoryOrchestrator()
    
    # Cypher query example
    results = await orchestrator.graph_store.query(
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
1. Check logs in `C:\Users\JaimeSubiabreCistern\.elefante\logs\`
2. Review `DEBUG/DASHBOARD_DEBUGGING_POSTMORTEM.md` for common issues
3. Ensure only one process accesses the database at a time