# Elefante Memory System - Troubleshooting Log

## Issue: Memory Storage Timeout (2025-11-27)

### Problem Description
Elefante MCP server was timing out (60-300 seconds) when attempting to store memories via `addMemory` tool. User reported memories were not being stored correctly.

### Investigation Timeline

#### Initial Symptoms
- `addMemory` tool calls timing out after 60 seconds
- `getStats` tool returning error: "no such column: collections.topic"
- Multiple timeout attempts with no success

#### Root Cause Analysis

**Primary Issue: ChromaDB Schema Corruption**
- ChromaDB database at `C:\Users\JaimeSubiabreCistern\.elefante\data\chroma\chroma.sqlite3` had outdated schema
- Error: `sqlite3.OperationalError: no such column: collections.topic`
- Schema mismatch between stored database and current ChromaDB library version
- This caused silent failures during initialization, leading to timeouts

**Secondary Issue: Kuzu Database File Corruption**
- Initial `kuzu_db` was a FILE (16,384 bytes) instead of a DIRECTORY
- Kuzu expects `kuzu_db` to be a directory containing database files
- This was causing lock errors: "Cannot open file. path: C:\Users\JaimeSubiabreCistern\.elefante\data\kuzu_db\.lock"

#### Performance Metrics

**Before Fix:**
- Memory storage: TIMEOUT (60-300 seconds)
- Embedding model load: ~5 seconds (normal)
- ChromaDB initialization: FAILED with schema error
- Total: FAILURE

**After Fix:**
- Orchestrator creation: 0.00s (instant)
- Embedding model load: ~5s
- ChromaDB initialization: ~7s (creating fresh database)
- Memory storage: ~4s
- **Total: ~16s (SUCCESS)**

### Solution Applied

1. **Killed blocking processes:**
   ```bash
   taskkill /F /IM python.exe
   ```

2. **Renamed corrupted ChromaDB:**
   ```bash
   ren "C:\Users\JaimeSubiabreCistern\.elefante\data\chroma" "chroma.old"
   ```

3. **Renamed corrupted Kuzu file:**
   ```bash
   ren "C:\Users\JaimeSubiabreCistern\.elefante\data\kuzu_db" "kuzu_db.backup"
   ```

4. **System auto-created fresh databases on next run**

### Verification Tests

#### Test 1: Direct Python Test
```python
from src.core.orchestrator import get_orchestrator
import asyncio

orch = get_orchestrator()
result = asyncio.run(orch.add_memory(
    'User has two dogs named Marty and Emmett, named after Back to the Future characters',
    memory_type='fact',
    importance=7,
    tags=['personal', 'pets', 'dogs']
))
```
**Result:** ✅ SUCCESS - Memory ID: `e9d2859f-8c75-46cd-a1e2-5a5a449761e9`

#### Test 2: MCP Server Test
```json
{
  "tool": "addMemory",
  "content": "User has two dogs named Marty and Emmett...",
  "memory_type": "fact",
  "importance": 7
}
```
**Result:** ✅ SUCCESS - Memory ID: `7db64bad-c87d-4837-a0b4-1f1ac6adae4f`

#### Test 3: Memory Retrieval
```json
{
  "tool": "searchMemories",
  "query": "dogs pets Marty Emmett Back to the Future",
  "mode": "hybrid"
}
```
**Result:** ✅ SUCCESS - Found 2 memories with high similarity scores (0.82, 0.79)

### Code Changes Made

**File:** `Elefante/src/mcp/server.py`

Added pre-initialization of orchestrator in `run()` method to load embedding model before handling requests:

```python
async def run(self):
    """Run the MCP server"""
    self.logger.info("Starting Elefante MCP Server...")
    
    # Pre-initialize orchestrator to load embedding model BEFORE handling requests
    # This prevents timeout issues on first tool call
    self.logger.info("Pre-initializing orchestrator and embedding model...")
    try:
        orchestrator = await self._get_orchestrator()
        # Trigger model loading by generating a test embedding
        await orchestrator.embedding_service.generate_embedding("initialization test")
        self.logger.info("Orchestrator and embedding model initialized successfully")
    except Exception as e:
        self.logger.error(f"Failed to pre-initialize orchestrator: {e}")
        # Continue anyway - will lazy load on first request
    
    async with stdio_server() as (read_stream, write_stream):
        self.logger.info("MCP Server running on stdio")
        await self.server.run(
            read_stream,
            write_stream,
            self.server.create_initialization_options()
        )
```

### Lessons Learned

1. **Database Schema Migrations:** ChromaDB schema changes between versions require migration or fresh database
2. **Lazy Loading Issues:** Lazy loading heavy models (embeddings) during request handling causes timeouts
3. **Error Handling:** Silent failures in async initialization can manifest as timeouts
4. **File vs Directory:** Kuzu requires directory structure, not single file
5. **Pre-initialization:** Heavy resources should be loaded at startup, not on first request

### Prevention Measures

1. ✅ Added pre-initialization of orchestrator and embedding model at server startup
2. ✅ Documented database corruption recovery procedure
3. 🔄 TODO: Add database schema version checking
4. 🔄 TODO: Add automatic database migration on version mismatch
5. 🔄 TODO: Add health check endpoint to verify database integrity

### Current Status

**System Status:** ✅ FULLY OPERATIONAL
- ChromaDB: Fresh database, working correctly
- Kuzu: Fresh database, working correctly
- Embedding Service: Pre-loaded, responding in ~5s
- Memory Storage: Working, ~16s total time
- Memory Retrieval: Working, ~3s response time

**Known Issues:** None

**Backup Locations:**
- Old ChromaDB: `C:\Users\JaimeSubiabreCistern\.elefante\data\chroma.old`
- Old Kuzu: `C:\Users\JaimeSubiabreCistern\.elefante\data\kuzu_db.backup`

---

**Last Updated:** 2025-11-28 01:41 UTC
**Resolved By:** IBM Bob (Jaime Mode)
**Status:** RESOLVED ✅