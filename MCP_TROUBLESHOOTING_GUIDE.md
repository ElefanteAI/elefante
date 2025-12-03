# 🔧 ELEFANTE MCP TROUBLESHOOTING GUIDE

## Current Status: MCP Server Disconnected

The MCP server connection was lost after killing the Python process. This is expected behavior.

---

## 🎯 SOLUTION: Restart Bob IDE

**The MCP server is managed by Bob IDE and must be restarted through the IDE, not manually.**

### Steps to Fix:

1. **Close Bob IDE completely**
   - File → Exit (or Alt+F4)
   - Ensure all Bob processes are terminated

2. **Restart Bob IDE**
   - The MCP server will automatically reconnect
   - Check the MCP section in Output panel to confirm connection

3. **Verify Connection**
   - Try using `searchMemories` or `getStats` MCP tool
   - Should work without errors

---

## 🔍 Root Cause Analysis

### The Kuzu Database Lock Issue

**Problem:** Kuzu uses file-based locking (single-writer architecture)
- Only ONE process can access the database at a time
- When multiple processes try to access: `Error 15105: unknown error` or `'NoneType' object has no attribute 'query'`

**Affected Scenarios:**
1. Dashboard running + MCP tool call = ❌ CONFLICT
2. Python script running + MCP tool call = ❌ CONFLICT  
3. MCP tool call + MCP tool call = ✅ OK (same process)
4. Python script alone = ✅ OK
5. Dashboard alone = ✅ OK

---

## 📋 Workaround Strategies

### Strategy 1: Use MCP Tools (Recommended for Interactive Use)
```
✅ Best for: Quick queries, adding single memories, interactive exploration
❌ Limitation: Cannot run while dashboard is active
```

**How to use:**
1. Ensure dashboard is NOT running
2. Use MCP tools directly in Bob IDE:
   - `searchMemories` - Find memories
   - `addMemory` - Store new memory
   - `getStats` - Check system health
   - `queryGraph` - Run Cypher queries

### Strategy 2: Use Python Scripts (Recommended for Batch Operations)
```
✅ Best for: Bulk operations, complex workflows, automation
❌ Limitation: Requires command line execution
```

**How to use:**
```bash
cd Elefante
.venv\Scripts\activate
python scripts/utils/add_user_profile.py
python verify_memories.py
```

### Strategy 3: Use Dashboard (Recommended for Visualization)
```
✅ Best for: Visual exploration, graph navigation, memory browsing
❌ Limitation: Blocks MCP tools and scripts while running
```

**How to use:**
```bash
cd Elefante
.venv\Scripts\python -m src.dashboard.app
```
Then open browser to http://localhost:8000

---

## 🚨 Common Errors & Solutions

### Error: "Not connected"
**Cause:** MCP server disconnected from Bob IDE  
**Solution:** Restart Bob IDE completely

### Error: "Cannot open file... .lock - Error 15105"
**Cause:** Another process is accessing Kuzu database  
**Solution:** 
1. Stop dashboard: `taskkill /F /PID <pid>` or close dashboard window
2. Kill stray Python processes: `tasklist | findstr python` then `taskkill /F /PID <pid>`
3. Restart Bob IDE

### Error: "'NoneType' object has no attribute 'query'"
**Cause:** Kuzu connection failed due to lock conflict  
**Solution:** Same as Error 15105 above

### Error: "searchMemories returns 0 results" but memories exist
**Cause:** MCP server has stale connection or wrong database path  
**Solution:**
1. Restart Bob IDE
2. Verify database path in MCP config matches actual location
3. Run `getStats` to confirm connection

---

## 🔬 Diagnostic Commands

### Check if database is locked:
```bash
# Windows
tasklist | findstr python
dir "C:\Users\JaimeSubiabreCistern\.elefante\data"

# Look for kuzu_db file (not a directory)
```

### Verify memories exist:
```bash
cd Elefante
.venv\Scripts\python verify_memories.py
```

### Check MCP server status:
```
In Bob IDE:
1. Open Output panel (View → Output)
2. Select "MCP" from dropdown
3. Look for connection status and errors
```

---

## 📊 System Architecture (Why This Happens)

```
┌─────────────────────────────────────────────────────────┐
│                    ELEFANTE SYSTEM                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐      ┌──────────────┐                │
│  │   ChromaDB   │      │  Kuzu Graph  │                │
│  │ (Vector DB)  │      │  (File Lock) │◄───── SINGLE   │
│  │              │      │              │       WRITER   │
│  │ Multi-access │      │ Single-access│       ONLY!    │
│  └──────────────┘      └──────────────┘                │
│         ▲                      ▲                        │
│         │                      │                        │
│         └──────────┬───────────┘                        │
│                    │                                    │
│         ┌──────────▼──────────┐                        │
│         │  MemoryOrchestrator │                        │
│         └──────────┬──────────┘                        │
│                    │                                    │
│         ┌──────────┴──────────┐                        │
│         │                     │                        │
│    ┌────▼─────┐        ┌─────▼────┐                   │
│    │MCP Server│        │Dashboard │                    │
│    │(Process 1)│       │(Process 2)│                   │
│    └──────────┘        └──────────┘                    │
│         ▲                     ▲                         │
│         │                     │                         │
│         │                     └─── CONFLICT! ───┐       │
│         │                                       │       │
│         └─── Both try to access Kuzu ──────────┘       │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

**Key Insight:** ChromaDB allows concurrent access, but Kuzu does not. This is a fundamental architectural limitation, not a bug.

---

## 🎯 Best Practices

### For Daily Use:
1. **Use MCP tools for quick interactions** (search, add single memory)
2. **Use Python scripts for batch operations** (bulk import, data migration)
3. **Use dashboard for exploration** (visual graph navigation)
4. **Never run dashboard + MCP tools simultaneously**

### For Development:
1. Always check for running processes before starting new operations
2. Use `restart_mcp.bat` to clean up stale connections
3. Keep Bob IDE Output panel open to monitor MCP status
4. Test MCP tools after any system changes

### For Troubleshooting:
1. Restart Bob IDE first (solves 90% of issues)
2. Check for stray Python processes second
3. Verify database files exist third
4. Check MCP configuration last

---

## 📝 Quick Reference

### Kill All Python Processes:
```bash
taskkill /F /IM python.exe
```

### Restart MCP Server:
```bash
cd Elefante
restart_mcp.bat
# Then restart Bob IDE
```

### Verify System Health:
```bash
cd Elefante
.venv\Scripts\python verify_memories.py
```

### Check MCP Connection:
Use MCP tool `getStats` in Bob IDE - if it returns data, connection is good.

---

## 🆘 When All Else Fails

1. **Full Reset:**
   ```bash
   # Kill all Python processes
   taskkill /F /IM python.exe
   
   # Restart Bob IDE
   # Try MCP tools again
   ```

2. **Nuclear Option (Last Resort):**
   ```bash
   # Backup database
   xcopy "C:\Users\JaimeSubiabreCistern\.elefante\data" "C:\Users\JaimeSubiabreCistern\.elefante\data_backup" /E /I
   
   # Restart Bob IDE
   # Reinitialize if needed
   ```

3. **Contact Support:**
   - Include: MCP Output panel logs
   - Include: `verify_memories.py` output
   - Include: This troubleshooting guide section attempted

---

**Last Updated:** 2025-12-02  
**Status:** MCP server requires Bob IDE restart to reconnect