# Usage Guide & API

## 1. Natural Language Interaction

Once connected to your IDE, use natural language to interact with Elefante.

- **Store Info:** "Remember that I prefer using async/await over callbacks."
- **Retrieve Context:** "What do you know about my coding preferences?"
- **Graph Query:** "Show me all technologies related to the Elefante project."

## 2. Available Tools

The MCP server exposes the following tools to the agent:

| Tool             | Description                               |
| :--------------- | :---------------------------------------- |
| `addMemory`      | Stores semantic and structured data.      |
| `searchMemories` | Performs hybrid search (Vector + Graph).  |
| `queryGraph`     | Executes raw Cypher queries against Kuzu. |
| `createEntity`   | Manually creates nodes in the graph.      |

## 3. Python API (For Scripting)

You can import the core logic into your own Python scripts:

```python
import asyncio
from src.core.orchestrator import get_orchestrator

async def main():
    orch = get_orchestrator()
    # Hybrid Search
    results = await orch.search_memories("How is Elefante designed?")
    for r in results:
        print(f"- {r.memory.content} (Score: {r.score})")

if __name__ == "__main__":
    asyncio.run(main())
```

## 4. Testing

- **End-to-End Test:** Run `python scripts/test_end_to_end.py` to verify memory persistence, search, and graph linking.
- **Health Check:** Run `python scripts/health_check.py` to verify DB connectivity.
