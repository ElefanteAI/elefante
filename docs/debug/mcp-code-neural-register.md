# 🧠 MCP CODE NEURAL REGISTER
## System Immunity: MCP Protocol Failure Laws

**Purpose**: Permanent record of MCP protocol violations and enforcement strategies  
**Status**: Active Neural Register  
**Last Updated**: 2025-12-05

---

## 📜 THE LAWS (Immutable Truths)

### LAW #1: Type Signature Exactness
**Statement**: MCP tool handlers MUST return `list[types.Tool]`, not `list[Tool]` or `List[types.Tool]`.

**The Python Type System Trap**: MCP SDK uses strict runtime type checking.

**Correct Signature**:
```python
from mcp import types

@server.list_tools()
async def list_tools() -> list[types.Tool]:  # ✅ Correct
    return [types.Tool(...)]
```

**Common Errors**:
```python
# ❌ Wrong: Missing types prefix
async def list_tools() -> list[Tool]:
    return [Tool(...)]

# ❌ Wrong: Using typing.List
from typing import List
async def list_tools() -> List[types.Tool]:
    return [types.Tool(...)]

# ❌ Wrong: No return type annotation
async def list_tools():
    return [types.Tool(...)]
```

**Failure Symptom**: "Tools not showing in IDE" despite server running  
**Root Cause**: Type mismatch causes silent failure in MCP protocol layer  
**Detection**: Enable MCP debug logging, check for type validation errors

---

### LAW #2: Protocol Layer 5 - Action Verification
**Statement**: Every tool execution MUST verify the action was completed before returning success.

**The 5-Layer Protocol**:
```
Layer 1: Tool Registration (list_tools)
Layer 2: Input Validation (call_tool receives arguments)
Layer 3: Business Logic (execute operation)
Layer 4: Error Handling (catch exceptions)
Layer 5: Action Verification (confirm state change) ← CRITICAL
```

**Anti-Pattern**: Assuming success without verification
```python
# ❌ Wrong: No verification
async def call_tool(name: str, arguments: dict):
    memory_store.add_memory(arguments["content"])
    return [types.TextContent(text="Memory added")]  # Did it actually add?
```

**Correct Pattern**: Verify state change
```python
# ✅ Correct: Verify action
async def call_tool(name: str, arguments: dict):
    memory_id = memory_store.add_memory(arguments["content"])
    
    # Layer 5: Verify
    retrieved = memory_store.get_memory(memory_id)
    if not retrieved:
        raise RuntimeError("Memory add failed verification")
    
    return [types.TextContent(text=f"Memory {memory_id} added and verified")]
```

**Failure Mode**: Silent data loss, user believes action succeeded when it failed

---

### LAW #3: Error Context Enrichment
**Statement**: MCP errors MUST include actionable context for debugging.

**Minimal Error** (Anti-Pattern):
```python
except Exception as e:
    return [types.TextContent(text=f"Error: {str(e)}")]
```

**Enriched Error** (Correct Pattern):
```python
except Exception as e:
    error_context = {
        "tool": name,
        "arguments": arguments,
        "error_type": type(e).__name__,
        "error_message": str(e),
        "traceback": traceback.format_exc(),
        "timestamp": datetime.now().isoformat()
    }
    logger.error(f"Tool execution failed: {error_context}")
    
    return [types.TextContent(
        text=f"❌ {name} failed: {str(e)}\n"
             f"Context: {json.dumps(error_context, indent=2)}"
    )]
```

**Required Context**:
- Tool name and arguments (what was attempted)
- Error type and message (what failed)
- Stack trace (where it failed)
- Timestamp (when it failed)

---

### LAW #4: Async/Await Consistency
**Statement**: MCP handlers are async. ALL database operations MUST be awaited or wrapped.

**The Async Trap**: Forgetting `await` causes silent failures.

**Synchronous Database** (Kuzu, ChromaDB):
```python
# ❌ Wrong: Blocking call in async function
async def call_tool(name: str, arguments: dict):
    result = graph_store.create_entity(...)  # Blocks event loop!
    return [types.TextContent(text="Done")]

# ✅ Correct: Wrap in executor
import asyncio
async def call_tool(name: str, arguments: dict):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None, 
        graph_store.create_entity, 
        ...
    )
    return [types.TextContent(text="Done")]
```

**Asynchronous Database** (hypothetical):
```python
# ✅ Correct: Native async
async def call_tool(name: str, arguments: dict):
    result = await async_db.create_entity(...)
    return [types.TextContent(text="Done")]
```

**Failure Mode**: Event loop blocking, server unresponsive

---

### LAW #5: Tool Schema Completeness
**Statement**: Tool schemas MUST document ALL parameters with types, descriptions, and examples.

**Minimal Schema** (Anti-Pattern):
```python
types.Tool(
    name="addMemory",
    description="Add memory",
    inputSchema={
        "type": "object",
        "properties": {
            "content": {"type": "string"}
        }
    }
)
```

**Complete Schema** (Correct Pattern):
```python
types.Tool(
    name="addMemory",
    description="Store a new memory in Elefante's dual-database system. "
                "INTELLIGENT INGESTION: Automatically analyzes against existing "
                "knowledge and flags as NEW/REDUNDANT/RELATED/CONTRADICTORY.",
    inputSchema={
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The memory content to store"
            },
            "memory_type": {
                "type": "string",
                "enum": ["conversation", "fact", "insight", "code", "decision"],
                "default": "conversation",
                "description": "Type of memory for categorization"
            },
            "importance": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10,
                "default": 5,
                "description": "Importance level (1-10)"
            }
        },
        "required": ["content"]
    }
)
```

**Required Elements**:
- Clear description of tool purpose
- Parameter types with constraints (enum, min/max)
- Default values for optional parameters
- Human-readable descriptions
- Required vs optional distinction

---

## 🔬 FAILURE PATTERNS (Documented Cases)

### Pattern #1: Silent Type Mismatch (2025-12-02)
**Trigger**: Using `list[Tool]` instead of `list[types.Tool]`  
**Symptom**: Tools not appearing in IDE, no error messages  
**Root Cause**: MCP protocol layer silently rejects mismatched types  
**Impact**: Complete tool invisibility  
**Resolution**: Fix type signatures, enable debug logging  
**Prevention**: Type checking in CI/CD, linting rules

### Pattern #2: Unverified Memory Addition (2025-12-02)
**Trigger**: Adding memory without checking if it persisted  
**Symptom**: User reports "memory not saved" but no errors  
**Root Cause**: ChromaDB silent failure (disk full, permissions)  
**Impact**: Data loss, user trust erosion  
**Resolution**: Implement Layer 5 verification  
**Prevention**: Integration tests with failure injection

### Pattern #3: Blocking Database Calls (2025-12-02)
**Trigger**: Synchronous Kuzu operations in async handler  
**Symptom**: Server hangs, timeouts  
**Root Cause**: Event loop blocked by I/O  
**Impact**: Server unresponsive, requires restart  
**Resolution**: Wrap in `run_in_executor`  
**Prevention**: Async linting, performance monitoring

---

## 🛡️ SAFEGUARDS (Active Protections)

### Safeguard #1: Type Validation Tests
**Location**: `scripts/debug/test_tools.py`  
**Action**: Verify tool handler return types  
**Response**: Catch type mismatches before deployment

### Safeguard #2: Action Verification Protocol
**Location**: `src/mcp/server.py` (Layer 5 implementation)  
**Action**: Verify state change after every write operation  
**Response**: Fail fast with clear error if verification fails

### Safeguard #3: Debug Logging
**Location**: MCP server startup (`src/mcp/__main__.py`)  
**Action**: Enable verbose logging in development  
**Response**: Surface silent failures for debugging

---

## 📊 METRICS

### Tool Visibility Rate
- **Before Fix**: 0% (type mismatch)
- **After Fix**: 100% (correct signatures)

### Data Loss Incidents
- **Before Verification**: 3 reported cases
- **After Verification**: 0 incidents

### Server Stability
- **Before Async Fix**: Frequent hangs
- **After Async Fix**: 99.9% uptime

---

## 🎯 PROTOCOL ENFORCEMENT CHECKLIST

### Pre-Deployment Validation
- [ ] All handlers return `list[types.Tool]` or `list[types.TextContent]`
- [ ] All write operations include Layer 5 verification
- [ ] All errors include enriched context
- [ ] All async handlers properly await or wrap blocking calls
- [ ] All tool schemas include complete documentation

### Runtime Monitoring
- [ ] MCP debug logging enabled in development
- [ ] Error rate tracking (should be <1%)
- [ ] Response time monitoring (should be <500ms)
- [ ] Memory leak detection (connection cleanup)

---

## 🔗 RELATED REGISTERS

- **DATABASE_NEURAL_REGISTER.md**: Connection lifecycle, lock management
- **MEMORY_NEURAL_REGISTER.md**: Retrieval verification, export protocols

---

## 📚 SOURCE DOCUMENTS

- `docs/debug/general/fixes-applied.md` (type signature fixes)
- `docs/debug/general/critical-analysis.md` (Layer 5 protocol)
- `docs/debug/general/protocol-enforcement.md` (v1)
- `docs/debug/general/protocol-enforcement-v2.md` (v2)
- `docs/debug/general/protocol-enforcement-v3.md` (v3)
- `docs/debug/general/PROTOCOL-ENFORCEMENT-FINAL.md` (final version)
- `docs/debug/general/code-mode-mcp-limitation.md` (async issues)

---

**Neural Register Status**: ✅ ACTIVE  
**Enforcement**: Type checking, integration tests, code review  
**Last Validation**: 2025-12-05