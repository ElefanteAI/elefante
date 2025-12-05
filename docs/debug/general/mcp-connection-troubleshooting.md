# MCP Connection Troubleshooting Guide

**Date:** 2025-12-04  
**Issue:** Bob-IDE MCP "Not connected" error despite correct configuration  
**Resolution:** Multiple process conflict + IDE restart required

## Problem Summary

MCP server configured correctly in Bob-IDE settings but `use_mcp_tool` fails with "Not connected" error.

## Root Causes Identified

### 1. Multiple Python Process Conflict
**Symptom:** MCP server running in terminal while IDE tries to auto-start its own instance  
**Detection:** `tasklist | findstr python` shows multiple python.exe processes  
**Impact:** Database lock conflicts, connection failures

### 2. Kuzu Database Lock
**Symptom:** Error 15105 "Cannot open file" on kuzu_db files  
**Cause:** Previous process crashed without cleanup, `.lock` file persists  
**Impact:** Blocks all database operations

### 3. IDE MCP Client Not Initialized
**Symptom:** MCP server running but IDE reports "Not connected"  
**Cause:** IDE needs restart after MCP server configuration changes  
**Impact:** MCP tools unavailable despite server being active

## Resolution Steps

### Step 1: Kill All Python Processes
```cmd
taskkill /F /IM python.exe
```

### Step 2: Remove Database Lock
```cmd
del C:\Users\<username>\.elefante\data\kuzu_db\.lock
```

### Step 3: Verify Database Clean
```cmd
cd Elefante && python scripts/debug/nuclear_reset_kuzu.py
```
Should report: "No lock file found - Database appears ready for use"

### Step 4: Restart IDE
- Close Bob-IDE completely (File → Exit)
- Relaunch Bob-IDE
- MCP server should auto-start (check settings: `autoStart: true`)

### Step 5: Verify Connection
Use MCP tool to test:
```
use_mcp_tool → elefante → getStats
```
Should return database statistics without "Not connected" error.

## Prevention

### Best Practices
1. **Never run MCP server manually in terminal** when IDE has `autoStart: true`
2. **Always check for orphaned processes** before starting new sessions
3. **Clean shutdown:** Close IDE properly to prevent lock files
4. **Monitor database locks:** Check for `.lock` files if connection fails

### Configuration Checklist
```json
{
  "chat.mcp.servers": {
    "elefante": {
      "command": "python",
      "args": ["-m", "src.mcp.server"],
      "cwd": "path/to/Elefante",
      "autoStart": true,  // Let IDE manage server
      "disabled": false
    }
  }
}
```

## Diagnostic Commands

### Check Running Processes
```cmd
tasklist | findstr python
```

### Check Database Lock
```cmd
dir C:\Users\<username>\.elefante\data\kuzu_db\.lock
```

### Test MCP Server Manually (for debugging only)
```cmd
cd Elefante
python -m src.mcp.server
```
Should output: "MCP Server running on stdio"

## Common Mistakes

### ❌ Running Server in Terminal + IDE Auto-Start
**Problem:** Two servers compete for database access  
**Solution:** Use ONLY IDE auto-start OR manual terminal, never both

### ❌ Assuming Connection Works Without Testing
**Problem:** Server running doesn't mean IDE is connected  
**Solution:** Always test with actual MCP tool call

### ❌ Ignoring Lock Files
**Problem:** Database corruption from concurrent access  
**Solution:** Clean locks before restart, never force-delete database files

## Related Issues

- [Code Mode MCP Limitation](code-mode-mcp-limitation.md) - Mode-based tool restrictions
- [Kuzu Lock Analysis](../database/kuzu-lock-analysis.md) - Database locking mechanisms
- [Database Corruption](../database/database-corruption-2025-12-02.md) - Recovery procedures

## Lessons Learned

1. **Process Management:** MCP server lifecycle must be managed by ONE authority (IDE or manual)
2. **State Verification:** "Server running" ≠ "Client connected" - always verify end-to-end
3. **Clean Shutdown:** Proper IDE exit prevents 90% of lock file issues
4. **Diagnostic First:** Check processes and locks BEFORE attempting fixes

---
*Discovered during user persona storage attempt 2025-12-04*