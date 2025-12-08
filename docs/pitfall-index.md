# 🚨 PITFALL INDEX - Quick Search Reference

> **Purpose:** Searchable index of all documented pitfalls  
> **Usage:** Search this file BEFORE completing any task  
> **Format:** Each entry is a searchable trigger → action pair

---

## DASHBOARD PITFALLS

### pitfall: dashboard build browser cache refresh

**Trigger:** After `npm run build` or any frontend changes  
**Action:** Tell user to press `Ctrl+Shift+R` (hard refresh)  
**Why:** Browser caches old JS/CSS, shows stale version  
**Source:** debug/dashboard/dashboard-compendium.md, debug/dashboard-neural-register.md

### pitfall: dashboard data snapshot stale

**Trigger:** After adding/changing memories via MCP  
**Action:** Run `python scripts/update_dashboard_data.py`  
**Why:** Dashboard reads from snapshot file, not live database  
**Source:** debug/dashboard/dashboard-compendium.md Law #1

### pitfall: dashboard kuzu lock conflict

**Trigger:** Dashboard won't start, "cannot acquire lock"  
**Action:** Kill Python processes, remove `kuzu_db/.lock`  
**Why:** Kuzu single-writer architecture  
**Source:** debug/database-neural-register.md Law #2

---

## INSTALLATION PITFALLS

### pitfall: kuzu database directory pre-exists

**Trigger:** Installing Elefante, "path cannot be a directory"  
**Action:** Do NOT pre-create kuzu_db directory (System now auto-heals empty dirs)  
**Why:** Kuzu 0.11+ creates its own structure. Empty dir blocks it.  
**Source:** debug/installation-neural-register.md Law #1 & Law #7

### pitfall: installation python version

**Trigger:** Installing dependencies, cryptic errors  
**Action:** Verify Python 3.8+  
**Why:** Type hints and async features require 3.8+  
**Source:** technical/installation-safeguards.md

---

## DATABASE PITFALLS

### pitfall: kuzu reserved word properties

**Trigger:** Entity creation fails, "Cannot find property"  
**Action:** Use `props` not `properties`  
**Why:** `properties` is reserved in Cypher but valid in SQL DDL  
**Source:** debug/database-neural-register.md Law #1, technical/kuzu-best-practices.md

### pitfall: kuzu reserved word type label

**Trigger:** Schema works but CREATE fails  
**Action:** Use `entity_type`, `entity_label` instead  
**Why:** Reserved words valid in schema, invalid in DML  
**Source:** technical/kuzu-best-practices.md

### pitfall: kuzu schema operation validation

**Trigger:** New property added to schema  
**Action:** Test BOTH schema creation AND Cypher CREATE  
**Why:** SQL-valid names can be Cypher-invalid  
**Source:** debug/database-neural-register.md Law #3

---

## MCP / MEMORY PITFALLS

### pitfall: mcp type signature list types tool

**Trigger:** Tools not showing in IDE  
**Action:** Use `list[types.Tool]` not `List[Tool]`  
**Why:** MCP SDK uses strict runtime type checking  
**Source:** debug/mcp-code-neural-register.md Law #1

### pitfall: memory export chromadb api

**Trigger:** Export returns only 10 memories instead of all  
**Action:** Use `collection._collection.get()` not `query()`  
**Why:** API filters by semantic relevance  
**Source:** debug/memory-neural-register.md Law #1

### pitfall: memory search vs list all

**Trigger:** User says "show all memories about X"  
**Action:** Use `listAllMemories` + filter, not `searchMemories`  
**Why:** searchMemories returns top-N by relevance  
**Source:** debug/memory-neural-register.md Law #2

---

## VERIFICATION PITFALLS

### pitfall: verification layer 5 action

**Trigger:** Tool says "success" but user sees nothing  
**Action:** Verify state change before returning success  
**Why:** Operation may silently fail  
**Source:** debug/mcp-code-neural-register.md Law #2

### pitfall: verification browser cache

**Trigger:** Code changed but nothing looks different  
**Action:** Hard refresh (`Ctrl+Shift+R`)  
**Why:** Browser serves cached version  
**Source:** debug/dashboard/dashboard-compendium.md Law #5

---

## HOW TO USE THIS INDEX

### Before Completing a Task:

```
1. Identify your task category: [dashboard/install/database/mcp/memory]
2. Search this file for: "pitfall: [category]"
3. Read matching entries
4. Apply any relevant actions
5. THEN complete task
```

### Search Examples:

- Building dashboard? Search: `pitfall: dashboard build`
- Changing Kuzu schema? Search: `pitfall: kuzu`
- Memory export failing? Search: `pitfall: memory export`
- Tools not showing? Search: `pitfall: mcp type`

---

## ADDING NEW PITFALLS

When you encounter a new repeated mistake:

```markdown
### pitfall: [category] [keywords]

**Trigger:** [what action causes this]  
**Action:** [what to do]  
**Why:** [root cause]  
**Source:** [document reference]
```

---

**Search this file. Don't repeat history.**
