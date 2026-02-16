# Elefante Dashboard Usage Guide

**Version**: v1.10.0  
**Last Updated**: 2026-02-16

See also:
- [Dashboard Startup Guide](dashboard-startup.md) — Starting, verifying, and troubleshooting
- [Dashboard Snapshot Contract](dashboard-snapshot-contract.md)

---

## Quick Start

### Starting the Dashboard

**Option 1: Via MCP Tool (Recommended)**
```
"Open the dashboard"
```
This calls `elefante-DashboardOpen`, starts the server, and opens your browser.

**Option 2: Manual Start**
```bash
# Refresh snapshot first
python scripts/update_dashboard_data.py

# Start dashboard server
python -m src.dashboard.server
```

Dashboard will be available at: **http://127.0.0.1:8000**

### Stopping the Dashboard

Press `Ctrl+C` in the terminal running the server.

---

## Dashboard Features

### 1. Memory Visualization

- **Neural Web Graph**: Memories rendered as an organic, physics-driven network
- **Node Labels**: Truncated descriptions shown below each node
- **Hover Tooltips**: Title, summary, and connection counts
- **Zoom Controls**: Mouse wheel or zoom buttons (bottom right)
- **Pan**: Click and drag to move around the graph

### 2. Statistics Panel (Top Left)

- **Total Memories**: Current count in the system
- **Total Episodes**: Number of conversation sessions

### 3. Visual Physics Engine

- **Linear Node Sizing**: Balanced sizes (max 25px) based on behavioral relevance score
- **Neural Physics**: Nodes float organically, no rigid ring locks
- **Recency Pulse**: White ring for very recent memories
- **Status Borders**: Green = processed, amber = pending ETL classification
- **Signal Hubs**: Topic, ring, and knowledge_type hub nodes connect related memories

---

## Adding Memories

### Via MCP Tools (Recommended)

Use the `elefante-MemoryAdd` tool from your IDE:

```
Store this in Elefante: "Always use absolute paths in configuration files"
```

The agent provides `content`, `memory_type`, and `domain`. The system computes behavioral relevance automatically.

### Via Python Script

```python
import asyncio
from src.core.orchestrator import get_orchestrator

async def add_memory():
    orchestrator = get_orchestrator()

    result = await orchestrator.add_memory(
        content="Your memory content here",
        metadata={
            "memory_type": "fact",
            "domain": "work"
        }
    )

    print(f"Memory added: {result.id}")

asyncio.run(add_memory())
```

---

## Snapshot Refresh

The dashboard is **snapshot-driven**. It reads from a static JSON file, not directly from the databases. This prevents lock conflicts with the MCP server.

### Workflow:

1. **Add memories** using MCP tools or scripts
2. **Regenerate the snapshot**: 
   - **Via Tool**: `elefante-DashboardOpen(refresh=True)`
   - **Via Script**: `python scripts/update_dashboard_data.py`
3. **Refresh your browser** (Cmd+R / F5)

### What Gets Updated:

- Memory count in statistics panel
- New nodes in the graph visualization
- Relationships and signal hub connections
- ETL classification status indicators

### Architecture:

```
MCP Server (write) -> databases -> Export Script -> snapshot.json -> Dashboard (read-only)
```

Snapshot generation is the **only** step that touches databases. The dashboard runtime reads `dashboard_snapshot.json` and remains read-only.

---

## Troubleshooting

### Dashboard Shows 0 Memories

1. **Hard refresh browser**: Cmd+Shift+R (clears cache)
2. **Regenerate snapshot**: `python scripts/update_dashboard_data.py`
3. **Check database**: `python scripts/health_check.py`

### Graph Not Loading (Blank Screen)

1. **Check Binding**: Server MUST bind to `0.0.0.0`, not `127.0.0.1`
2. **Check API**: Visit http://localhost:8000/api/stats
3. **Verify Static Files**: Ensure `src/dashboard/ui/dist/index.html` exists

### Memory Not Appearing After Adding

1. **Regenerate snapshot**: `python scripts/update_dashboard_data.py`
2. **Refresh browser**: Press F5
3. **Verify no database lock**: Only one process can access Kuzu at a time

---

## Database Locations

| Store | Default Path |
|-------|-------------|
| ChromaDB | `data/chroma_db/` |
| Kuzu | `data/kuzu_db` |
| Snapshot | `data/dashboard_snapshot.json` |
| Logs | `logs/` |

Paths are configured in `config.yaml`.

---

## Performance Notes

- **Memory Limit**: System handles 10,000+ memories efficiently
- **Graph Rendering**: Limited to 500 nodes by default (configurable)
- **Search Speed**: Semantic search typically <100ms

---

## Support

For common issues, see [`docs/debug/dashboard-compendium.md`](../debug/dashboard-compendium.md)
