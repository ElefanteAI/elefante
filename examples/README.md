# Elefante Agent Tutorial

> **For AI Agents** - Step-by-step MCP tool usage guide

## First-Time Setup

When Elefante MCP is installed, run the tutorial:

```
Call: elefante-System with action="enable"
Then follow: examples/AGENT_TUTORIAL.md
```

## Files

| File | Purpose |
|------|---------|
| `AGENT_TUTORIAL.md` | Step-by-step MCP tool guide for agents |
| `system-prompt-template.md` | Paste-in prompt for non-workspace MCP clients (Claude Desktop, etc.) |

## Quick Reference

### Core Tools (in order of use)

1. `elefante-System` (action="enable") - Enable before any operation
2. `elefante-MemoryAdd` - Store a memory
3. `elefante-MemorySearch` - Retrieve memories
4. `elefante-ContextGet` - Get session context
5. `elefante-System` (action="disable") - Release locks when done

---

