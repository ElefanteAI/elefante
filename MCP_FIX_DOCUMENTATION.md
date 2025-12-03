# MCP Integration Fix - Database Lock Issue

**Date:** 2024-12-02  
**Issue:** MCP `addMemory` tool returns `'NoneType' object has no attribute 'query'`  
**Status:** ✅ FIXED

---

## Problem Description

### Symptom
When calling the `addMemory` MCP tool, it fails with:
```
{
  "error": "'NoneType' object has no attribute 'query'",
  "tool": "addMemory",
  "success": false
}
```

### Root Cause
**Database Concurrency Conflict:**

1. **Kuzu Database Locking**: Kuzu (the graph database) uses file-based locking and only allows one process to access the database at a time.

2. **Dashboard Server Conflict**: When the dashboard server is running (`python -m src.dashboard.server`), it holds a lock on the Kuzu database.

3. **MCP Initialization Failure**: When the MCP server tries to initialize, it attempts to connect to the Kuzu database but fails silently because the database is locked.

4. **Silent Failure**: The `_initialize_connection()` method catches the exception but leaves `self._conn = None`.

5. **Runtime Error**: When `addMemory` tries to use the None connection object, it crashes with the NoneType error.

---

## Solution Implemented

### Changes Made

#### 1. Enhanced Error Handling in MCP Server
**File:** `src/mcp/server.py` (lines 403-445)

Added explicit checks and clear error messages:

```python
async def _handle_add_memory(self, args: Dict[str, Any]) -> Dict[str, Any]:
    """Handle addMemory tool call"""
    try:
        orchestrator = await self._get_orchestrator()
        
        # Verify orchestrator is properly initialized
        if orchestrator.graph_store._conn is None:
            raise RuntimeError(
                "Graph store not initialized. "
                "This usually means the Kuzu database is locked by another process (e.g., dashboard server). "
                "Please stop the dashboard server before using MCP tools, or use the Python scripts in scripts/utils/ instead."
            )
        
        memory = await orchestrator.add_memory(...)
        
        return {
            "success": True,
            "memory_id": str(memory.id),
            "message": "Memory stored successfully",
            "memory": memory.to_dict()
        }
    except RuntimeError as e:
        self.logger.error(f"Database lock error: {str(e)}")
        raise
    except AttributeError as e:
        if "'NoneType' object has no attribute" in str(e):
            raise RuntimeError(
                "Database initialization failed. "
                "The Kuzu database may be locked by another process (dashboard server). "
                "Stop the dashboard server and try again, or use scripts/utils/add_memories.py instead."
            )
        raise
```

#### 2. Improved Graph Store Error Messages
**File:** `src/core/graph_store.py` (lines 85-130)

Added specific handling for database lock errors:

```python
def _initialize_connection(self):
    """Initialize Kuzu connection (lazy loading)"""
    if self._conn is not None:
        return
    
    try:
        import kuzu
        # ... initialization code ...
        
    except RuntimeError as e:
        error_msg = str(e)
        if "Could not set lock on file" in error_msg or "IO exception" in error_msg:
            logger.error("kuzu_database_locked", error=error_msg)
            raise RuntimeError(
                f"Kuzu database is locked by another process. "
                f"This usually means the dashboard server or another MCP instance is running. "
                f"Database path: {self.database_path}\n"
                f"Solution: Stop the dashboard server or other processes accessing the database."
            ) from e
        logger.error("failed_to_initialize_kuzu", error=error_msg)
        raise
```

---

## How to Use MCP Tools Now

### Option 1: Stop Dashboard First (Recommended for MCP)
```bash
# Stop dashboard if running (Ctrl+C in dashboard terminal)
# Then use MCP tools normally in Roo-Cline
```

### Option 2: Use Python Scripts (Recommended for Batch Operations)
```bash
cd Elefante
.venv\Scripts\python.exe scripts/utils/add_memories.py
```

### Option 3: Use Dashboard Only (Recommended for Visualization)
```bash
cd Elefante
.venv\Scripts\python.exe -m src.dashboard.server
# Open http://127.0.0.1:8000
# Add memories via browser refresh after using scripts
```

---

## Error Messages You'll See Now

### Before Fix
```json
{
  "error": "'NoneType' object has no attribute 'query'",
  "tool": "addMemory",
  "success": false
}
```
**Problem:** Cryptic, doesn't explain the issue.

### After Fix
```json
{
  "error": "Graph store not initialized. This usually means the Kuzu database is locked by another process (e.g., dashboard server). Please stop the dashboard server before using MCP tools, or use the Python scripts in scripts/utils/ instead.",
  "tool": "addMemory",
  "success": false
}
```
**Better:** Clear explanation and actionable solutions.

---

## Technical Details

### Why Kuzu Locks the Database

Kuzu uses **file-based locking** to ensure data integrity:
- Only one process can write to the database at a time
- This prevents data corruption from concurrent writes
- The lock is held for the entire duration the database is open

### Why We Can't Fix the Concurrency Issue

**Architectural Limitation:**
- Kuzu is designed for single-writer access
- Multiple readers are not supported in the current version
- This is a fundamental design choice of the database

**Potential Solutions (Not Implemented):**
1. **Use a different graph database** (e.g., Neo4j) - Major refactor
2. **Implement a queue system** - Adds complexity
3. **Use read-only mode for dashboard** - Limits functionality

**Current Approach:**
- Accept the limitation
- Provide clear error messages
- Document workarounds

---

## Testing the Fix

### Test 1: MCP with Dashboard Running
```bash
# Terminal 1: Start dashboard
cd Elefante
.venv\Scripts\python.exe -m src.dashboard.server

# Terminal 2: Try MCP addMemory tool
# Expected: Clear error message about database lock
```

### Test 2: MCP with Dashboard Stopped
```bash
# Stop dashboard (Ctrl+C)
# Try MCP addMemory tool
# Expected: Success
```

### Test 3: Python Scripts (Always Work)
```bash
cd Elefante
.venv\Scripts\python.exe scripts/utils/add_memories.py
# Expected: Success (scripts handle database access properly)
```

---

## Future Improvements

### Short Term
- [ ] Add automatic dashboard detection in MCP server
- [ ] Provide "stop dashboard" button in error message
- [ ] Create unified CLI tool that manages both services

### Long Term
- [ ] Evaluate alternative graph databases with better concurrency
- [ ] Implement read-only dashboard mode
- [ ] Add queue-based write system for concurrent access

---

## Related Files

- `src/mcp/server.py` - MCP server implementation
- `src/core/graph_store.py` - Kuzu database wrapper
- `src/core/orchestrator.py` - Memory orchestration layer
- `scripts/utils/add_memories.py` - Direct memory addition script
- `scripts/dashboard/restart_dashboard.bat` - Dashboard management

---

## Changelog

**2024-12-02:**
- ✅ Added explicit database lock detection
- ✅ Improved error messages with actionable solutions
- ✅ Added RuntimeError handling for lock conflicts
- ✅ Documented workarounds and usage patterns

---

**Status:** Production-ready with known limitations documented.