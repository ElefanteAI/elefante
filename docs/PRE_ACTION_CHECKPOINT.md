# 🛑 PRE-ACTION CHECKPOINT PROTOCOL

> **Purpose:** Force AI agents to consult Elefante BEFORE completing tasks  
> **Status:** MANDATORY - Built from repeated failures  
> **Last Updated:** 2025-12-05

---

## THE PROBLEM

AI agents (including Claude) have access to Elefante's memory but **don't use it proactively**. We store lessons, then ignore them. The knowledge exists; the retrieval doesn't happen.

**Example:** "Hard refresh browser after frontend builds" was documented in 5 places. I still didn't check before claiming "done."

---

## THE PROTOCOL

### Before Completing ANY Task, MUST:

```
┌─────────────────────────────────────────────────────────┐
│  🛑 PRE-ACTION CHECKPOINT                               │
│                                                         │
│  BEFORE saying "Done" or "Complete":                    │
│                                                         │
│  1. IDENTIFY task category (dashboard, install, memory) │
│  2. SEARCH Elefante: "[category] common mistakes"       │
│  3. CHECK relevant Neural Register                      │
│  4. APPLY any found warnings                            │
│  5. THEN complete the task                              │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## TASK-SPECIFIC CHECKPOINTS

### 🎨 DASHBOARD / FRONTEND TASKS

**After ANY of these:**
- `npm run build`
- `npm run dev`
- Editing `.tsx` / `.css` files
- Changing visualization code

**MUST DO:**
- [ ] Tell user: **"Press Ctrl+Shift+R to hard refresh"**
- [ ] Or run script to bust cache automatically

**Search Query:** `searchMemories("dashboard browser cache refresh common mistakes")`

**Neural Register:** `docs/debug/DASHBOARD_NEURAL_REGISTER.md`

---

### 📦 INSTALLATION TASKS

**After ANY of these:**
- Modifying `config.py` or `config.yaml`
- Changing database paths
- Upgrading dependencies

**MUST DO:**
- [ ] Check Kuzu version compatibility (0.11+ path issue)
- [ ] Verify no pre-created directories
- [ ] Run pre-flight checks

**Search Query:** `searchMemories("installation kuzu database path common mistakes")`

**Neural Register:** `docs/debug/INSTALLATION_NEURAL_REGISTER.md`

---

### 🧠 MEMORY / MCP TASKS

**After ANY of these:**
- Modifying `orchestrator.py` or `mcp/server.py`
- Changing memory schema
- Updating vector store

**MUST DO:**
- [ ] Verify type signatures (list[types.Tool] not List[Tool])
- [ ] Check ChromaDB collection access
- [ ] Test both add and search operations

**Search Query:** `searchMemories("MCP memory ChromaDB type signature common mistakes")`

**Neural Register:** `docs/debug/MCP_CODE_NEURAL_REGISTER.md`

---

### 🗄️ DATABASE TASKS

**After ANY of these:**
- Modifying Kuzu schema
- Adding new properties
- Changing entity definitions

**MUST DO:**
- [ ] Check property name is NOT a Cypher reserved word
- [ ] Never use: `properties`, `type`, `label`, `id` (use alternatives)
- [ ] Test CREATE operation, not just schema

**Search Query:** `searchMemories("kuzu reserved words properties database common mistakes")`

**Neural Register:** `docs/debug/DATABASE_NEURAL_REGISTER.md`

---

## QUICK REFERENCE: COMMON PITFALLS BY CATEGORY

| Category | #1 Pitfall | Quick Fix |
|----------|------------|-----------|
| Dashboard | Browser cache | `Ctrl+Shift+R` |
| Installation | Kuzu pre-existing dir | Don't mkdir before Kuzu init |
| MCP | Type signature | `list[types.Tool]` not `List[Tool]` |
| Database | Reserved words | `props` not `properties` |
| Memory | API vs raw access | `_collection.get()` for export |

---

## ENFORCEMENT

### For AI Agents (Claude, GPT, etc.)

**Inject this at task completion:**

```
STOP. Before claiming this task is complete:
1. What category is this task? [dashboard/install/memory/database]
2. Did you search Elefante for "[category] common mistakes"?
3. Did you check the Neural Register for this domain?
4. Did you apply any warnings found?

If NO to any: DO NOT PROCEED. Search first.
```

### For Humans

If AI says "Done" without mentioning relevant pitfalls, ask:
> "Did you check Elefante for common mistakes in this area?"

---

## META-LESSON

This document exists because:
1. We stored lessons learned ✅
2. We didn't retrieve them when relevant ❌
3. We repeated the same mistakes ❌

**The fix is not more documentation. The fix is mandatory retrieval.**

---

## RELATED FILES

- `docs/debug/DASHBOARD_NEURAL_REGISTER.md`
- `docs/debug/INSTALLATION_NEURAL_REGISTER.md`
- `docs/debug/DATABASE_NEURAL_REGISTER.md`
- `docs/debug/MCP_CODE_NEURAL_REGISTER.md`
- `docs/debug/MEMORY_NEURAL_REGISTER.md`
- `docs/debug/dashboard/dashboard-compendium.md`

---

**The irony of not using your own memory system ends here.**
