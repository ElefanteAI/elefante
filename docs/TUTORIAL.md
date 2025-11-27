# 🚀 ELEFANTE QUICK START - Real Examples

## Step-by-Step Installation & Testing Guide

---

## ✅ Step 1: Wait for Deploy to Finish

The `deploy.bat` script is currently running. Wait for it to show:

```
============================================================
DEPLOYMENT COMPLETE!
============================================================
[OK] Elefante is ready to use!
```

**Expected time:** 10-15 minutes (downloading models and packages)

---

## ✅ Step 2: Verify Installation

After deploy finishes, run:

```cmd
python scripts/health_check.py
```

**Expected output:**
```
✓ Configuration: HEALTHY
✓ Embedding Service: HEALTHY
✓ Vector Store: HEALTHY
✓ Graph Store: HEALTHY
✓ Orchestrator: HEALTHY
```

If you see all ✓ marks, you're ready!

---

## 🎯 Step 3: Test with Real Examples

### Example 1: Store Your First Memory

Create a file `test_memory.py`:

```python
import asyncio
from src.core.orchestrator import get_orchestrator

async def main():
    orchestrator = get_orchestrator()
    
    # Store a memory about yourself
    memory = await orchestrator.add_memory(
        content="Jaime works at IBM as a developer, building AI systems with Autogen",
        memory_type="fact",
        importance=9,
        tags=["personal", "work", "ibm"],
        entities=[
            {"name": "Jaime", "type": "person"},
            {"name": "IBM", "type": "organization"},
            {"name": "Autogen", "type": "technology"}
        ]
    )
    
    print(f"✓ Memory stored! ID: {memory.id}")
    print(f"  Content: {memory.content}")
    print(f"  Tags: {memory.metadata.tags}")

if __name__ == "__main__":
    asyncio.run(main())
```

**Run it:**
```cmd
python test_memory.py
```

**Expected output:**
```
✓ Memory stored! ID: 12345678-1234-1234-1234-123456789abc
  Content: Jaime works at IBM as a developer...
  Tags: ['personal', 'work', 'ibm']
```

---

### Example 2: Search Your Memories

Create `test_search.py`:

```python
import asyncio
from src.core.orchestrator import get_orchestrator
from src.models.query import QueryMode

async def main():
    orchestrator = get_orchestrator()
    
    # Search for memories about work
    print("Searching for: 'Where does Jaime work?'")
    results = await orchestrator.search_memories(
        query="Where does Jaime work?",
        mode=QueryMode.HYBRID,  # Uses both databases!
        limit=5
    )
    
    print(f"\n✓ Found {len(results)} results:\n")
    
    for i, result in enumerate(results, 1):
        print(f"Result {i}:")
        print(f"  Score: {result.score:.3f}")
        print(f"  Content: {result.memory.content[:100]}...")
        print(f"  Source: {result.source}")
        print()

if __name__ == "__main__":
    asyncio.run(main())
```

**Run it:**
```cmd
python test_search.py
```

**Expected output:**
```
Searching for: 'Where does Jaime work?'

✓ Found 1 results:

Result 1:
  Score: 0.892
  Content: Jaime works at IBM as a developer, building AI systems with Autogen...
  Source: hybrid
```

---

### Example 3: Build a Knowledge Graph

Create `test_knowledge.py`:

```python
import asyncio
from src.core.orchestrator import get_orchestrator

async def main():
    orchestrator = get_orchestrator()
    
    # Store a project memory
    print("1. Storing project information...")
    memory = await orchestrator.add_memory(
        content="Elefante is a dual-database AI memory system using ChromaDB and Kuzu",
        memory_type="fact",
        importance=10,
        tags=["elefante", "project", "architecture"],
        entities=[
            {"name": "Elefante", "type": "project"},
            {"name": "ChromaDB", "type": "technology"},
            {"name": "Kuzu", "type": "technology"}
        ]
    )
    print(f"✓ Stored memory: {memory.id}\n")
    
    # Create a relationship
    print("2. Creating entity relationship...")
    entity1 = await orchestrator.create_entity(
        name="Jaime",
        entity_type="person",
        properties={"role": "developer"}
    )
    
    entity2 = await orchestrator.create_entity(
        name="Elefante",
        entity_type="project",
        properties={"status": "active"}
    )
    
    relationship = await orchestrator.create_relationship(
        from_entity_id=entity1.id,
        to_entity_id=entity2.id,
        relationship_type="created_by",
        properties={"date": "2024-01"}
    )
    print(f"✓ Created relationship: Jaime -> created_by -> Elefante\n")
    
    # Get context
    print("3. Retrieving full context...")
    context = await orchestrator.get_context(depth=2, limit=10)
    
    print(f"✓ Context retrieved:")
    print(f"  Memories: {context['stats']['num_memories']}")
    print(f"  Entities: {context['stats']['num_entities']}")
    print(f"  Depth: {context['stats']['depth']}")

if __name__ == "__main__":
    asyncio.run(main())
```

**Run it:**
```cmd
python test_knowledge.py
```

**Expected output:**
```
1. Storing project information...
✓ Stored memory: 12345678-1234-1234-1234-123456789abc

2. Creating entity relationship...
✓ Created relationship: Jaime -> created_by -> Elefante

3. Retrieving full context...
✓ Context retrieved:
  Memories: 2
  Entities: 5
  Depth: 2
```

---

### Example 4: Real Conversation Simulation

Create `test_conversation.py`:

```python
import asyncio
from src.core.orchestrator import get_orchestrator
from src.models.query import QueryMode

async def simulate_conversation():
    orchestrator = get_orchestrator()
    
    print("=== SIMULATING AI CONVERSATION WITH MEMORY ===\n")
    
    # Session 1: Initial conversation
    print("📅 SESSION 1 - Monday")
    print("You: I'm working on a Python project called Elefante")
    
    await orchestrator.add_memory(
        content="User is working on a Python project called Elefante",
        memory_type="conversation",
        importance=7,
        tags=["project", "python"]
    )
    print("AI: Got it! I'll remember that.\n")
    
    # Session 2: Next day
    print("📅 SESSION 2 - Tuesday")
    print("You: What was I working on yesterday?")
    
    results = await orchestrator.search_memories(
        query="What project is the user working on?",
        mode=QueryMode.HYBRID,
        limit=3
    )
    
    if results:
        print(f"AI: You were working on {results[0].memory.content}")
    print()
    
    # Session 3: Add more details
    print("📅 SESSION 3 - Wednesday")
    print("You: Elefante uses ChromaDB and Kuzu databases")
    
    await orchestrator.add_memory(
        content="Elefante uses ChromaDB for vector search and Kuzu for graph queries",
        memory_type="fact",
        importance=8,
        tags=["elefante", "architecture", "databases"],
        entities=[
            {"name": "Elefante", "type": "project"},
            {"name": "ChromaDB", "type": "technology"},
            {"name": "Kuzu", "type": "technology"}
        ]
    )
    print("AI: Noted! I've linked those technologies to your project.\n")
    
    # Session 4: Complex query
    print("📅 SESSION 4 - Thursday")
    print("You: What technologies does my project use?")
    
    results = await orchestrator.search_memories(
        query="What technologies does Elefante use?",
        mode=QueryMode.HYBRID,
        limit=5
    )
    
    print("AI: Based on what you've told me:")
    for result in results:
        if "ChromaDB" in result.memory.content or "Kuzu" in result.memory.content:
            print(f"  - {result.memory.content}")
    
    print("\n=== CONVERSATION COMPLETE ===")
    print("✓ AI remembered everything across 4 sessions!")

if __name__ == "__main__":
    asyncio.run(simulate_conversation())
```

**Run it:**
```cmd
python test_conversation.py
```

**Expected output:**
```
=== SIMULATING AI CONVERSATION WITH MEMORY ===

📅 SESSION 1 - Monday
You: I'm working on a Python project called Elefante
AI: Got it! I'll remember that.

📅 SESSION 2 - Tuesday
You: What was I working on yesterday?
AI: You were working on User is working on a Python project called Elefante

📅 SESSION 3 - Wednesday
You: Elefante uses ChromaDB and Kuzu databases
AI: Noted! I've linked those technologies to your project.

📅 SESSION 4 - Thursday
You: What technologies does my project use?
AI: Based on what you've told me:
  - Elefante uses ChromaDB for vector search and Kuzu for graph queries

=== CONVERSATION COMPLETE ===
✓ AI remembered everything across 4 sessions!
```

---

## 🎯 Step 4: Start MCP Server (For IDE Integration)

Once tests work, start the server:

```cmd
python -m src.mcp.server
```

**Leave this running!** It will show:
```
INFO: Elefante MCP Server initialized
INFO: Starting Elefante MCP Server...
INFO: MCP Server running on stdio
```

---

## 🎯 Step 5: Configure Your IDE

### For Cline (VSCode)

1. Open VSCode Settings (Ctrl+,)
2. Search for "MCP"
3. Add this configuration:

```json
{
  "mcpServers": {
    "elefante": {
      "command": "python",
      "args": ["-m", "src.mcp.server"],
      "cwd": "C:/Users/JaimeSubiabreCistern/Documents/Agentic/Elefante"
    }
  }
}
```

4. Restart Cline
5. You should see "Elefante" in available MCP servers

---

## 🎯 Step 6: Use It in Your IDE!

Now when you chat with Cline:

**You:** "Remember that I prefer async Python code"
**Cline:** *Uses `addMemory` tool* "I'll remember that!"

**Later...**
**You:** "What do you know about my coding preferences?"
**Cline:** *Uses `searchMemories` tool* "You prefer async Python code"

---

## 📊 Verify Everything Works

Run the complete test suite:

```cmd
python scripts/test_end_to_end.py
```

**Expected:**
```
============================================================
TEST SUMMARY
============================================================
add_memory          : ✓ PASS
semantic_search     : ✓ PASS
hybrid_search       : ✓ PASS
entity_creation     : ✓ PASS
get_context         : ✓ PASS
system_stats        : ✓ PASS

Results: 6 passed, 0 failed
============================================================

🎉 ALL TESTS PASSED!
```

---

## 🎉 You're Done!

Elefante is now:
- ✅ Installed
- ✅ Tested
- ✅ Ready to use

Your AI now has **permanent memory**! 🐘

---

## 🆘 Troubleshooting

### If deploy.bat fails:
```cmd
# Install dependencies manually
pip install -r requirements.txt

# Initialize databases
python scripts/init_databases.py

# Run tests
python scripts/test_end_to_end.py
```

### If tests fail:
```cmd
# Check health
python scripts/health_check.py

# Check logs
type logs\elefante.log
```

### If MCP server won't start:
```cmd
# Verify Python can find modules
python -c "import src.core.orchestrator"

# Check for errors
python -m src.mcp.server
```

---

**Made with ❤️ by IBM Bob & Jaime** 🐘