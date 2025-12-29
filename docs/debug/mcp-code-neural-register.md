#  MCP CODE NEURAL REGISTER

## System Immunity: MCP Protocol Failure Laws

**Purpose**: Permanent record of MCP protocol violations and enforcement strategies  
**Status**: Active Neural Register  
**Last Updated**: 2025-12-28 (v1.6.0 Compliance Gate)

---

##  THE LAWS (Immutable Truths)

### LAW #1: Type Signature Exactness

**Statement**: MCP tool handlers MUST return `list[types.Tool]`, not `list[Tool]` or `List[types.Tool]`.

**The Python Type System Trap**: MCP SDK uses strict runtime type checking.

**Correct Signature**:

```python
from mcp import types

@server.list_tools()
async def list_tools() -> list[types.Tool]:  #  Correct
    return [types.Tool(...)]
```

**Common Errors**:

```python
#  Wrong: Missing types prefix
async def list_tools() -> list[Tool]:
    return [Tool(...)]

#  Wrong: Using typing.List
from typing import List
async def list_tools() -> List[types.Tool]:
    return [types.Tool(...)]

#  Wrong: No return type annotation
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
Layer 5: Action Verification (confirm state change) <- CRITICAL
```

**Anti-Pattern**: Assuming success without verification

```python
#  Wrong: No verification
async def call_tool(name: str, arguments: dict):
    memory_store.add_memory(arguments["content"])
    return [types.TextContent(text="Memory added")]  # Did it actually add?
```

**Correct Pattern**: Verify state change

```python
#  Correct: Verify action
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
        text=f" {name} failed: {str(e)}\n"
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
#  Wrong: Blocking call in async function
async def call_tool(name: str, arguments: dict):
    result = graph_store.create_entity(...)  # Blocks event loop!
    return [types.TextContent(text="Done")]

#  Correct: Wrap in executor
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
#  Correct: Native async
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
    name="elefanteMemoryAdd",
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
    name="elefanteMemoryAdd",
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
- Required vs optional distinction

---

### LAW #6: STDOUT PURITY (The JSON-RPC Sanctity)

**Statement**: The MCP Server process MUST NEVER write to `stdout` except for JSON-RPC messages. All logs/debugs MUST go to `stderr`.

---

### LAW #7: Transaction-Scoped Locking (v1.1.0)

**Statement**: Write operations MUST use transaction-scoped locks (milliseconds), NOT session-scoped locks (hours).

**The Multi-IDE Problem**: Session-based locks (v1.0.1) held database access until explicit `disable()`. If an IDE crashed or user forgot to disable, locks became stale and blocked ALL other IDEs indefinitely.

**Session-Based Locking** (v1.0.1 Anti-Pattern):

```python
#  Wrong: Lock held for entire session
class SessionLock:
    def enable(self):
        self.acquire_locks()  # Holds until disable()!
        self.is_enabled = True
    
    def disable(self):
        self.release_locks()
        self.is_enabled = False

# Usage - locks held for HOURS
manager.enable()  # Lock acquired
# ... user works for 8 hours ...
# ... user forgets to disable ...
# ... IDE crashes ...
# LOCKS ORPHANED FOREVER!
```

**Transaction-Scoped Locking** (v1.1.0 Correct Pattern):

```python
#  Correct: Lock held only during write operation
class TransactionLock:
    @contextmanager
    def write_lock(self):
        self._acquire()       # Lock acquired
        try:
            yield             # Work happens (milliseconds)
        finally:
            self._release()   # Lock ALWAYS released
    
    def _is_lock_stale(self, lock_info):
        # Auto-clear dead PIDs or locks > 30 seconds old
        return not pid_exists(lock_info.pid) or age > 30

# Usage in MCP handler
with transaction_lock.write_lock():
    memory_store.add_memory(content)  # Protected
# Lock released IMMEDIATELY
```

**Critical Incident** (Dec 26, 2025): Lock from PID 4563 (Dec 14) blocked all access for 12 days. User had two IDE instances, neither could access Elefante.

**Resolution**: Implemented transaction-scoped locking with:
- Per-operation locks (acquire → work → release in milliseconds)
- Stale lock detection (dead PID or age > 30 seconds)
- Auto-clearing of stale locks on next operation
- `enable()`/`disable()` become no-ops (backward compatible)

**Failure Symptom**: "Elefante Mode disabled" despite prior `enable()` call  
**Root Cause**: Another IDE session holding stale lock  
**Detection**: Check `~/.elefante/locks/write.lock` for stale entries

**The Stdio Trap**:
MCP communicates via stdin/stdout. Any stray `print()` or `logging.StreamHandler(sys.stdout)` corrupts the protocol stream.

**The Symptom**:
`connection closed: calling "tools/call": client is closing: invalid character 'I' looking for beginning of value`  
(The 'I' usually comes from `INFO: ...` or `ImportError: ...` or `Initializing...` printed to stdout).

**Correct Pattern**:

```python
#  WRONG
print("Initializing server...")  # BREAKS MCP
logging.basicConfig(stream=sys.stdout) # BREAKS MCP

#  CORRECT
import sys
import logging
# Use stderr for logs
logging.basicConfig(stream=sys.stderr)
print("Initializing...", file=sys.stderr)
```

**Failure Mode**: Immediate connection death on tool call.
**Resolution**: Grep for `print(` and check logging config. Redirect all library logs to stderr.

---

### LAW #7: SINGLE REGISTRATION (The IDE Scope Merge Trap)

**Statement**: A given MCP server identity (e.g., `elefante`) MUST be registered in exactly one IDE configuration scope/mechanism. If you register the same server name in multiple places, IDEs may display duplicates and operators will debug the wrong layer.

**The Trap**:

- VS Code merges **User** (`.../User/mcp.json`) and **Workspace** (`.vscode/mcp.json`) MCP servers.
- Some VS Code builds/extensions can also load MCP servers from `settings.json` via `chat.mcp.servers` (or extension-specific keys like `roo-cline.mcpServers`).

**The Symptom**:

- IDE shows **two identical MCP servers** (same name, same command) and may start/stop the “wrong one”.
- Confusing startup behavior (one works, one fails), duplicated tool lists, or phantom “connection closed” noise.

**Required Fix (Elefante global policy)**:

- Keep `elefante` only in **User** `mcp.json`.
- Ensure workspace `.vscode/mcp.json` does **not** define `servers.elefante` (workspace can be empty).
- If `chat.mcp.servers.elefante` (or `roo-cline.mcpServers.elefante`) exists, remove it when using `mcp.json`.

**Authoritative Reference**: `docs/technical/ide-mcp-configuration.md`

---

### LAW #8: Compliance Gate - Search Before Write (v1.6.0)

**Statement**: Write operations MUST be blocked until a search has been performed in the current session.

**The Agent Drift Problem**: Agents using Elefante tools often skip `elefanteMemorySearch` entirely, leading to:
- Duplicate memories (same info stored multiple times)
- Lost context (agent doesn't know what's already stored)
- Instruction drift (agents ignore "search first" prompts to save tokens)

**Instructions-Only** (Anti-Pattern):
```
# .github/copilot-instructions.md
"You MUST call elefanteMemorySearch before elefanteMemoryAdd"
# Agent: "Understood!" *proceeds to call elefanteMemoryAdd directly*
```

**Compliance Gate** (v1.6.0 Correct Pattern):
```python
# Server-side enforcement - MECHANICAL, not instruction-based
_compliance_state = {"search_performed": False, ...}

def _check_compliance_gate(self, tool_name):
    GATED_TOOLS = {"elefanteMemoryAdd", "elefanteGraphEntityCreate", ...}
    if tool_name in GATED_TOOLS and not self._compliance_state["search_performed"]:
        return {
            "success": False,
            "error": "COMPLIANCE GATE: Search required before write",
            "gate_status": "BLOCKED",
            "action_required": "Call elefanteMemorySearch first"
        }
    return None  # Gate passes

# Search handler unlocks the gate
async def _handle_search_memories(self, args):
    # ... perform search ...
    self._compliance_state["search_performed"] = True
    response["gate_status"] = "UNLOCKED"
    return response
```

**Gated Tools**: `elefanteMemoryAdd`, `elefanteGraphEntityCreate`, `elefanteGraphRelationshipCreate`, `elefanteGraphConnect`  
**Gate Unlocker**: `elefanteMemorySearch`  
**Layered Defense**: `.github/copilot-instructions.md` provides instructions; gate provides enforcement

**Failure Symptom**: Agent receives `gate_status: BLOCKED` when trying to write  
**Root Cause**: Agent skipped search step  
**Resolution**: Agent must call `elefanteMemorySearch` first, then retry write  
**Prevention**: Gate is mechanical - cannot be bypassed by reasoning

---

##  FAILURE PATTERNS (Documented Cases)

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

### Pattern #4: Long-Running Server Code Caching (2025-12-07)

**Trigger**: MCP server running 12+ hours, code files edited  
**Symptom**: Migration tool reports success, but data unchanged  
**Root Cause**: Python imports are cached; server uses OLD code version  
**Impact**: 8+ hours debugging - tool "worked" but used stale logic  
**Resolution**: Created standalone script (`scripts/migrate_memories_v3_direct.py`) to bypass cache  
**Prevention**: Restart servers after code changes; use `--reload` flag in development

### Pattern #5: Uvicorn Stdout Pollution (2025-12-09)

**Trigger**: Launching Dashboard Server (FastAPI/Uvicorn) from within MCP tool
**Symptom**: `connection closed: invalid character 'I'` immediately upon launch
**Root Cause**: Uvicorn defaults to logging startup info (`INFO: Started server...`) to `stdout`
**Impact**: Immediate MCP connection termination (protocol corruption)
**Resolution**: Configure Uvicorn logging to use `sys.stderr` explicitly
**Prevention**: **ALWAYS** configure `log_config` for any subprocess or library that might print to stdout. **NEVER** assume a library is silent.

### Pattern #6: Agent Drift - Ignoring Memory Search (2025-12-28) [v1.6.0]

**Trigger**: Agent using Elefante MCP tools without calling search first
**Symptom**: Duplicate memories created, context ignored, agent operates on stale knowledge
**Root Cause**: Instructions-only enforcement leads to "drift" - agents skip search to save tokens/time
**Impact**: Memory pollution, redundant data, lost context that was already stored
**Resolution**: **Compliance Gate** - Server-side enforcement that BLOCKS write operations until search is performed
**Prevention**: Gate is mechanical, not instruction-based. Cannot be bypassed by agent reasoning.

**Implementation** (v1.6.0):
```python
# Session state tracking
_compliance_state = {
    "search_performed": False,
    "search_count": 0,
    "search_timestamp": None,
    "last_query": None
}

# Gate check before write
def _check_compliance_gate(tool_name):
    GATED_TOOLS = {"elefanteMemoryAdd", "elefanteGraphEntityCreate", ...}
    if tool_name in GATED_TOOLS and not _compliance_state["search_performed"]:
        return {"success": False, "gate_status": "BLOCKED", ...}
    return None  # Gate passes
```

**Gated Tools**: `elefanteMemoryAdd`, `elefanteGraphEntityCreate`, `elefanteGraphRelationshipCreate`, `elefanteGraphConnect`
**Gate Unlocker**: `elefanteMemorySearch` (sets `search_performed=True`)

---

##  SAFEGUARDS (Active Protections)

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

### Safeguard #4: Compliance Gate (v1.6.0)

**Location**: `src/mcp/server.py` (`_check_compliance_gate`, `_compliance_state`)  
**Action**: Block write operations until search is performed  
**Response**: Return structured error with `gate_status: BLOCKED` and actionable hint  
**Layered Defense**: `.github/copilot-instructions.md` injected into Copilot requests  
**Test Coverage**: `tests/test_compliance_gate.py` (6 tests)

---

##  METRICS

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

##  PROTOCOL ENFORCEMENT CHECKLIST

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

##  RELATED REGISTERS

- **DATABASE_NEURAL_REGISTER.md**: Connection lifecycle, lock management
- **MEMORY_NEURAL_REGISTER.md**: Retrieval verification, export protocols

---

##  SOURCE DOCUMENTS

- `docs/debug/ai-behavior-compendium.md` (protocol enforcement, type fixes, async issues)

---

**Neural Register Status**:  ACTIVE  
**Enforcement**: Type checking, integration tests, code review  
**Last Validation**: 2025-12-06
