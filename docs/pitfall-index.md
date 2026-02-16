# PITFALL INDEX - Quick Search Reference

> **Purpose:** Searchable index of all documented pitfalls  
> **Usage:** Search this file BEFORE completing any task  
> **Format:** Each entry is a searchable trigger-action pair

---

## PRE-ACTION CHECKPOINT PROTOCOL

Before completing ANY task, MUST:

1. IDENTIFY task category (dashboard, install, memory, database)
2. SEARCH this file for `pitfall: [category]`
3. CHECK relevant Neural Register in `docs/debug/`
4. APPLY any found warnings
5. THEN complete the task

| Category | Primary Pitfall | Quick Fix |
|----------|-----------------|-----------|
| Dashboard | Browser cache | `Ctrl+Shift+R` |
| Installation | Kuzu pre-existing dir | Do not mkdir before Kuzu init |
| MCP | Type signature | `list[types.Tool]` not `List[Tool]` |
| Database | Reserved words | `props` not `properties` |
| Memory | API vs raw access | `_collection.get()` for export |
| **Documentation** | **Archive without index update** | **Update ALL READMEs that link to moved files** |

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

### pitfall: dashboard empty relative path

**Trigger**: Dashboard works but is empty (0 nodes)
**Action**: Check `server.py` uses `src.utils.config.DATA_DIR`
**Why**: Relative paths (`./data`) depend on CWD. Use absolute `~/.elefante/data`.
**Source**: debug/dashboard-neural-register.md Pattern #7

---

## INSTALLATION PITFALLS

### pitfall: kuzu database directory pre-exists

**Trigger:** Installing Elefante, "path cannot be a directory"  
**Action:** Do NOT pre-create kuzu_db directory (System now auto-heals empty dirs)  
**Why:** Kuzu 0.11+ creates its own structure. Empty dir blocks it.  
**Source:** debug/installation-neural-register.md Law #1 & Law #7

### pitfall: installation python version

**Trigger:** Installing dependencies, cryptic errors  
**Action:** Verify Python 3.11  
**Why:** Type hints, async features, and dependency compatibility require 3.11  
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

### pitfall: mcp vscode duplicate server scopes

**Trigger:** VS Code shows two identical `elefante` MCP servers  
**Action:** Keep `elefante` only in User `mcp.json`; ensure `.vscode/mcp.json` does not define `servers.elefante`; remove `chat.mcp.servers.elefante` / `roo-cline.mcpServers.elefante` if present; reload window  
**Why:** VS Code merges User + Workspace MCP servers; multiple mechanisms/scopes can register the same server name  
**Source:** debug/mcp-code-neural-register.md Law #7, technical/ide-mcp-configuration.md

### pitfall: mcp connection crash uvicorn

**Trigger**: `invalid character 'I'` when launching dashboard
**Action**: Redirect Uvicorn logs to `sys.stderr`
**Why**: `INFO` logs on stdout corrupt MCP JSON-RPC protocol
**Source**: debug/mcp-code-neural-register.md Pattern #5

### pitfall: memory export chromadb api

**Trigger:** Export returns only 10 memories instead of all  
**Action:** Use `collection._collection.get()` not `query()`  
**Why:** API filters by semantic relevance  
**Source:** debug/memory-neural-register.md Law #1

### pitfall: memory search vs list all

**Trigger:** User says "show all memories about X"  
**Action:** Use `elefante-MemorySearch (list_all=true)` + filter, not `elefante-MemorySearch`  
**Why:** `elefante-MemorySearch` returns top-N by relevance  
**Source:** debug/memory-neural-register.md Law #2

---

## DOCUMENTATION PITFALLS

### pitfall: documentation archive without index update CRITICAL

**Trigger:** Moving/archiving ANY file that is linked from an index (README.md, technical/README.md, etc.)  
**Action:** BEFORE archiving, grep for all references: `grep -r "filename" docs/`; update ALL indexes that link to the file  
**Why:** Archiving files without updating indexes creates ghost links. Documentation becomes obsolete. Future agents/users hit 404s.  
**Source:** 2025-12-27 incident: v2 schema files archived Dec 11, but docs/README.md and docs/technical/README.md still linked to them for 16 days.

### pitfall: documentation partial refactor

**Trigger:** Renaming, moving, or deleting documentation files  
**Action:** Complete the full chain: (1) Move file → (2) Update ALL inbound links → (3) Update ALL index files → (4) Verify with `grep -r "oldname" docs/`  
**Why:** Partial refactors leave broken links and confusion. One file can be referenced from 5+ places.  
**Source:** Developer Etiquette LAW 6 (File and Artifact Hygiene)

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
