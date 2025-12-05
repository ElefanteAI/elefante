# Code Mode MCP Tool Access Limitation

**Date:** 2025-12-04  
**Severity:** High  
**Status:** Documented

## Issue

Code mode in Roo Cline does not have access to MCP (Model Context Protocol) tools, despite MCP server running and connected.

## Symptoms

1. User requests memory storage via MCP
2. Assistant in Code mode attempts to create Python scripts instead
3. `use_mcp_tool` is unavailable in Code mode
4. Only certain modes (e.g., "jaime" mode) have MCP tool access

## Root Cause

**Mode-based tool restrictions:** Roo Cline implements different tool availability per mode. Code mode is restricted to file operations, command execution, and browser actions. MCP tools are only available in specific modes.

## Modes with MCP Access

- ✅ `jaime` mode - Has full MCP tool access
- ❌ `code` mode - No MCP tool access
- ❌ `architect` mode - No MCP tool access (file restrictions apply)
- ❌ `ask` mode - No MCP tool access

## Workaround

**Option 1: Mode Switch (Preferred)**
```
User must explicitly switch to a mode with MCP access (e.g., "jaime" mode) before requesting MCP operations.
```

**Option 2: Python Script Execution**
```python
# Create script that directly calls orchestrator
# Run via execute_command
# Less efficient, requires MCP server restart risk
```

## Impact

- **User Experience:** Confusing when assistant creates scripts instead of using MCP
- **Efficiency:** Mode switching adds friction
- **Error Prone:** Scripts can conflict with running MCP server (database locks)

## Recommendations

1. **User Education:** Document which modes support MCP in mode descriptions
2. **Assistant Behavior:** Immediately switch to MCP-enabled mode when MCP operation requested
3. **Mode Design:** Consider enabling MCP tools in Code mode for consistency

## Related Issues

- Database lock conflicts when script runs while MCP server active
- Kuzu error 15105 (file access) from concurrent access
- User confusion about mode capabilities

## Resolution Path

**Immediate:** Use mode switching workflow  
**Long-term:** Request MCP tool access in Code mode from Roo Cline maintainers

---
*Discovered during user persona storage attempt 2025-12-04*