# Elefante + Agent Zero Integration

> Status: ACTIVE TARGET · Goal: Elefante runs as Agent Zero's persistent memory layer with zero friction.
>
> Sections below predate v2.3.0 and describe Agent Zero internals as observed at study time. Treat the Agent Zero side as reference, not as a current Elefante contract. Anything describing Elefante must be re-validated against today's code before implementation.

## Executive Summary

The current state reveals a critical insight: ELEFANTE IS ALREADY PARTIALLY INTEGRATED with Agent Zero via FAISS project memory. The NO EMOJIS memory was present in the EXTRAS section but was IGNORED by the AI - this is a BEHAVIORAL failure, not a technical integration failure.

---

## Part 1: Agent Zero Memory Architecture

### 1.1 Core Components

| Component | Location | Purpose |
|-----------|----------|----------|
| Memory Class | python/helpers/memory.py | FAISS wrapper with CRUD operations |
| FAISS Index | .a0proj/memory/index.faiss | Vector storage |
| Pickle Store | .a0proj/memory/index.pkl | Document metadata |
| Knowledge Import | .a0proj/memory/knowledge_import.json | Preloaded knowledge tracking |

### 1.2 Memory Areas

```
class Area(Enum):
    MAIN = "main"        # Primary memory storage
    FRAGMENTS = "fragments"  # Reusable code/text snippets
    SOLUTIONS = "solutions"  # Past problem solutions
```

### 1.3 Memory Operations

| Method | Purpose |
|--------|----------|
| insert_text() | Store new memory |
| search_similarity_threshold() | Retrieve by similarity |
| delete_documents_by_ids() | Remove memories |
| update_documents() | Modify memories |

---

## Part 2: ELEFANTE Architecture

### 2.1 Core Components

| Component | Location | Purpose |
|-----------|----------|----------|
| Orchestrator | src/core/orchestrator.py | Central coordination |
| Vector Store | src/core/vector_store.py | ChromaDB wrapper |
| Graph Store | src/core/graph_store.py | Kuzu knowledge graph |
| Scoring | src/core/scoring.py | Behavioral relevance (0-100) |
| MCP Server | src/mcp/server.py | 22 MCP tools via stdio |

### 2.2 MCP Tools (22 Available)

| Tool | Purpose |
|------|----------|
| elefante-MemoryAdd | Store new memory |
| elefante-MemorySearch | Semantic/structured search |
| elefante-MemoryUpdate | Update existing memory |
| elefante-MemoryDelete | Remove memory |
| elefante-ContextGet | Get session context |
| elefante-GraphQuery | Cypher queries on knowledge graph |
| elefante-GraphConnect | Batch upsert entities/relationships |
| elefante-DirectiveAdd | Add behavioral constraint |
| elefante-DirectiveList | List directives |
| elefante-DirectiveRemove | Remove directive |
| elefante-SystemStatusGet | System status |
| elefante-DashboardOpen | Open web dashboard |
| ... | (11 more tools) |

### 2.3 Response Injection

Every MCP tool response contains:

```
MANDATORY_PROTOCOLS_READ_THIS_FIRST: Critical pitfalls
DIRECTIVES: User-managed behavioral constraints
RELEVANT_CONTEXT: Auto-surfaced top 3 memories
```

---

## Part 3: Current Integration Status

### 3.1 What EXISTS

| Component | Status | Evidence |
|-----------|--------|----------|
| ELEFANTE Memory Store | WORKING | 25 memories in ChromaDB+Kuzu |
| FAISS Project Memory | WORKING | .a0proj/memory/ exists |
| Knowledge Preloading | WORKING | knowledge_import.json configured |
| Memory Injection to EXTRAS | WORKING | NO EMOJIS memory was in EXTRAS |
| MCP Client Code | EXISTS | mcp_handler.py (1139 lines) |
| MCP Configuration | CONFIGURED | initialize.py passes mcp_servers |

### 3.2 What DOES NOT WORK

| Component | Status | Evidence |
|-----------|--------|----------|
| AI Behavioral Compliance | FAILING | NO EMOJIS memory ignored |
| MCP Server Active Connection | UNKNOWN | Not verified |
| FastA2A Bridge a2a_chat | BROKEN | 404 errors from tool |

---

## Part 4: Integration Options

### Option A: MCP Integration (RECOMMENDED)

Agent Zero already HAS MCP client capability. The proper path is:

```yaml
# In Agent Zero settings:
mcp_servers:
  - name: "elefante"
    type: "stdio"
    command: "python3"
    args: ["-m", "src.mcp"]
    cwd: "/Volumes/Hard/2026/AI Projects/A0/usr/projects/elefante_2_2"
```

This exposes all 22 ELEFANTE tools directly to Agent Zero.

### Option B: FastA2A Bridge (REDUNDANT)

The FastA2A bridge I built at src/a2a/ is REDUNDANT because:
1. Agent Zero already has MCP client
2. ELEFANTE already has MCP server
3. MCP is the native protocol for both systems

### Option C: FAISS Sync (CURRENT PARTIAL)

ELEFANTE memories could sync to Agent Zero FAISS project memory.
This is ALREADY happening partially via knowledge_import.json.

---

## Part 5: Recommended Architecture

```
+-------------------+     MCP Protocol      +-------------------+
|   AGENT ZERO      | <-------------------> |    ELEFANTE       |
|                   |                        |                   |
|  MCP Client       |     stdio://           |  MCP Server       |
|  (mcp_handler.py) |                        |  (22 tools)       |
|                   |                        |                   |
|  FAISS Memory     |   (Optional Sync)      |  ChromaDB + Kuzu  |
|  (Local Cache)    | <------------------->  |  (Persistent)     |
+-------------------+                        +-------------------+
```

### Primary Path: MCP
- Agent Zero calls ELEFANTE tools via MCP
- Full access to all 22 tools
- Response injection ensures compliance

### Secondary Path: FAISS Sync
- High-priority memories cached locally
- Offline access capability
- Knowledge preloading via .a0proj/knowledge/

---

## Part 6: Required Actions

### 6.1 Configure MCP Integration

1. Create/update Agent Zero settings with ELEFANTE MCP config
2. Verify MCP server startup
3. Test tool discovery

### 6.2 Clean Up Redundant Code

- Remove or archive src/a2a/ (FastA2A bridge)
- Document why MCP is preferred

### 6.3 Update Documentation

- Update copilot-instructions.md for Agent Zero
- Create integration guide
- Document behavioral compliance requirements

---

## Part 7: Behavioral Compliance (CRITICAL)

### The Core Problem

The AI received the NO EMOJIS memory but IGNORED it.
This is a BEHAVIORAL failure, not a technical one.

### Required Protocol

1. READ EXTRAS section at conversation start
2. APPLY all retrieved preferences/constraints
3. INCLUDE compliance stamp: [ELEFANTE] Searched: Found N memories
4. STORE important discoveries in ELEFANTE

### Developer Etiquette (User Preference)

Based on the conversation, the user expects:

1. NO EMOJIS in any output
2. NO claiming success without verification
3. NO asking permission - deliver autonomously
4. NO fabricating results - be honest
5. FULL study before building
6. CLEAN workspace
7. UPDATED documentation

---

## Conclusion

The integration architecture is SIMPLER than initially built:

1. MCP integration is the NATIVE path (both systems support it)
2. FastA2A bridge is REDUNDANT
3. The real issue is BEHAVIORAL compliance, not technical integration
4. AI must READ and FOLLOW injected memories from EXTRAS

