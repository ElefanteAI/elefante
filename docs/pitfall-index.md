# Pitfall Index

**Purpose**: Canonical operational reference. Search this file BEFORE completing any task.  
**Structure**: Domain sections → quick-fix entries → source links for depth.  
**Depth**: Full post-mortems live in `docs/debug/*-compendium.md`.

---

## Pre-Action Checkpoint

Before completing ANY task:

1. Identify task category: `dashboard` / `installation` / `database` / `mcp` / `memory` / `documentation`
2. Search this file for `pitfall: [category]`
3. Apply any found warnings
4. Then complete the task

| Category     | Most Common Pitfall                       | Jump To                                           |
| ------------ | ----------------------------------------- | ------------------------------------------------- |
| Dashboard    | Stale snapshot / browser cache            | [Dashboard Pitfalls](#dashboard-pitfalls)         |
| Installation | Pre-existing kuzu dir / wrong Python path | [Installation Pitfalls](#installation-pitfalls)   |
| Windows      | fcntl import / version parse / ExecPolicy | [Windows Pitfalls](#windows-pitfalls)             |
| Database     | Reserved word `properties` / stale lock   | [Database Pitfalls](#database-pitfalls)           |
| MCP          | Wrong type signature / stdout pollution   | [MCP Pitfalls](#mcp-pitfalls)                     |
| Memory       | Export truncated / search vs browse       | [Memory Pitfalls](#memory-pitfalls)               |
| Docs         | Ghost links after archive                 | [Documentation Pitfalls](#documentation-pitfalls) |

---

## Dashboard Pitfalls

### pitfall: dashboard build browser cache refresh

**Trigger:** After `npm run build` or any frontend changes  
**Action:** Tell user to press `Ctrl+Shift+R` (hard refresh)  
**Why:** Browser caches old JS/CSS, shows stale version  
**Source:** `docs/debug/dashboard-compendium.md`

### pitfall: dashboard data snapshot stale

**Trigger:** After adding/changing memories via MCP  
**Action:** Run `python scripts/update_dashboard_data.py`  
**Why:** Dashboard reads from `snapshot.json`, not live database. Direct Kuzu access from the dashboard triggers lock conflicts.  
**Source:** `docs/debug/dashboard-compendium.md` Issue #1

### pitfall: dashboard kuzu lock conflict

**Trigger:** Dashboard won't start, "cannot acquire lock"  
**Action:** Kill Python processes, remove `~/.elefante/locks/write.lock`  
**Why:** Kuzu single-writer architecture; v1.1.0+ uses transaction-scoped locks (auto-expire 30s) but a crashed process can leave a stale lock  
**Source:** `docs/debug/database-compendium.md` Issue #2

### pitfall: dashboard empty relative path

**Trigger:** Dashboard opens but shows 0 nodes  
**Action:** Ensure `server.py` imports `DATA_DIR` from `src.utils.config` — never use `./data`  
**Why:** Relative paths depend on CWD. MCP server writes to `~/.elefante/data`; if the dashboard reads from `./data` they never see the same files.  
**Source:** `docs/debug/dashboard-compendium.md` (Pattern "Ghost Data")

### pitfall: dashboard server binding localhost ipv6

**Trigger:** `curl localhost:8000` works but browser shows blank screen  
**Action:** Bind uvicorn to `host="0.0.0.0"`, not `127.0.0.1` or `localhost`  
**Why:** Modern browsers default to IPv6 `[::1]`; Python uvicorn defaults to IPv4 `127.0.0.1`. They never meet.  
**Source:** `docs/debug/dashboard-compendium.md` (LAW #6)

### pitfall: dashboard api response envelope

**Trigger:** Frontend shows `undefined` for stats despite API returning 200  
**Action:** Return the data object directly from FastAPI — no `{"success": True, "data": ...}` wrapper  
**Why:** Frontend reads `response.memories` directly. Envelope shifts the shape.  
**Source:** `docs/debug/dashboard-compendium.md` (LAW #7)

### pitfall: dashboard npm dependency unlocked

**Trigger:** Fresh `npm install` breaks the build  
**Action:** Pin exact versions (`"react": "18.2.0"` not `"^18.2.0"`); commit `package-lock.json`  
**Why:** Unlocked minor versions introduce silent breaking changes  
**Source:** `docs/debug/dashboard-compendium.md` Issue #3

---

## Installation Pitfalls

### pitfall: installation kuzu directory pre-exists

**Trigger:** Installing Elefante — `Runtime exception: Database path cannot be a directory`  
**Action:** Do NOT pre-create `kuzu_db/`. The app auto-heals empty dirs via `GraphStore.__init__`. If blocked: remove/rename the directory.  
**Why:** Kuzu 0.11+ requires path to be non-existent or a valid DB. Empty dirs crash it.  
**Source:** `docs/debug/installation-compendium.md` Issue #1

### pitfall: installation python version wrong

**Trigger:** Cryptic dependency errors, type hint failures  
**Action:** Verify Python 3.11 exactly. Check `python --version` and ensure venv uses the right interpreter.  
**Why:** Type hints, async features, and dependency compatibility all require 3.11.  
**Source:** `docs/technical/python-version-requirements.md`

### pitfall: installation python executable path ambiguous

**Trigger:** MCP server works manually but not in IDE; `ImportError` or wrong library version  
**Action:** Use `sys.executable` (absolute path) in ALL MCP/script configurations — never `"command": "python"`  
**Why:** `"python"` resolves to the system Python or a different venv. `sys.executable` is deterministic.  
**Source:** `docs/debug/installation-compendium.md` Issue #4 (LAW #6, LAW #8)

### pitfall: installation stale bytecode ghost errors

**Trigger:** Fixed the code but error persists  
**Action:** Delete all `__pycache__/` and `.pyc` files before restarting  
**Why:** Python may load stale bytecode metadata even after source changes  
**Source:** `docs/debug/installation-compendium.md` Issue #4 (LAW #9)

### pitfall: installation mcp handshake not verified

**Trigger:** Install reports success but IDE shows "Connection Refused"  
**Action:** Run `scripts/verify_mcp_handshake.py` — checks actual JSON-RPC `initialize` handshake, not just process PID  
**Why:** "Process running" ≠ "Server working". Port-open checks miss protocol failures.  
**Source:** `docs/debug/installation-compendium.md` Issue #4 (LAW #10)

### pitfall: installation broken venv trap

**Trigger:** Any `python scripts/install.py` call fails with ImportError or module errors inside VS Code/Copilot  
**Action:** Escape via system Python with absolute path: `/opt/homebrew/bin/python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt`  
**Why:** VS Code runs Python from workspace `.venv`. When that venv is corrupted, the agent cannot fix itself from within.  
**Source:** `docs/debug/installation-compendium.md` Issue #5

### pitfall: installation fcntl windows incompatibility

**Trigger:** `ImportError: No module named 'fcntl'` on Windows during MCP server startup or lock operations  
**Action:** Add a `sys.platform` guard — import `fcntl` only on non-Windows: `if sys.platform != "win32": import fcntl`  
**Why:** `fcntl` is a Unix-only module. Any file that imports it unconditionally will crash on Windows.  
**Affected file:** `src/utils/elefante_mode.py`  
**Source:** Discovered during Windows first-run, February 26, 2026

---

## Windows Pitfalls

### pitfall: windows python version check tokens

**Trigger:** `install.bat` version check fails silently or reports wrong version (e.g. `3.` instead of `3.11`)  
**Action:** Ensure `install.bat` uses `tokens=1,2,3` (not `tokens=1,2`) in the `for /f` loop that parses `python --version`. Fixed in current version.  
**Why:** `Python 3.11.9` split by dot+space yields 4 tokens. With `tokens=1,2`, %%c (the minor version) is never defined — MINOR stays empty.  
**Source:** Discovered February 26, 2026

### pitfall: windows python launcher not tried

**Trigger:** `install.bat` fails to find Python 3.11 even though it is installed  
**Action:** Install Python via the official installer with "Python Launcher" checked. The launcher provides `py -3.11` which is the most reliable way to invoke a specific version on Windows.  
**Why:** Windows doesn't always add `python3.11` to PATH — only `python`. `py -3.11` routes via the launcher regardless of PATH order.  
**Source:** `install.bat` updated February 26, 2026 to try `py -3.11` before `python`

### pitfall: windows powershell execution policy blocks venv

**Trigger:** Activating `.venv\Scripts\Activate.ps1` in PowerShell fails: `running scripts is disabled on this system`  
**Action:** Run once in PowerShell (as user, not admin): `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`  
**Why:** Windows default execution policy (`Restricted`) blocks unsigned `.ps1` scripts. `RemoteSigned` allows local scripts.  
**Note:** Use `call .venv\Scripts\activate.bat` from Command Prompt instead — no policy change needed.

### pitfall: windows venv activate path difference

**Trigger:** Documentation shows `.venv/bin/python` — command not found on Windows  
**Action:** On Windows, the venv layout uses `Scripts\` not `bin\`. Use `.venv\Scripts\python.exe` everywhere `.venv/bin/python` appears in macOS/Linux docs.  
**Why:** CPython venv uses `Scripts/` on Windows and `bin/` on Unix — deliberate platform difference.

### pitfall: windows mcp json path wrong

**Trigger:** MCP server configured but VS Code doesn't show Elefante tools  
**Action:** Verify MCP config is at `%APPDATA%\Code\User\mcp.json` (not `~/.config/Code/User/mcp.json`). Run `python scripts\configure_vscode_bob.py` to write it automatically.  
**Why:** `%APPDATA%` expands to `C:\Users\<name>\AppData\Roaming`. `~/.config` does not exist on Windows.

### pitfall: windows kuzu_dir constant wrong

**Trigger:** Database initialization passes but queries return empty results; `FileNotFoundError` on `kuzu_db`  
**Action:** Verify `KUZU_DIR = DATA_DIR / "kuzu_db"` in `src/utils/config.py`. Was `"kuzu"` in early versions — fixed February 26, 2026.  
**Why:** Constant mismatch means `GraphStore` opens a different path than `init_databases.py` creates.

### pitfall: windows lock dir tilde path

**Trigger:** `~/.elefante/locks/` does not exist on Windows after first run  
**Action:** Normal — `~` on Windows expands to `C:\Users\<name>`. The lock directory is auto-created by `TransactionLock._acquire()`. If missing after enable: check `ELEFANTE_HOME` in `src/utils/config.py` resolves to `Path.home() / ".elefante"`.  
**Why:** `Path.home()` is cross-platform. `~` in shell commands may not expand the same way on all Windows terminals.
### pitfall: windows script read_text encoding cp1252

**Trigger:** Any Python script that calls `Path.read_text()` or `Path.write_text()` crashes on Windows with `UnicodeDecodeError: 'charmap' codec can't decode byte...`  
**Action:** Always pass `encoding='utf-8'` explicitly: `path.read_text(encoding='utf-8')` and `path.write_text(content, encoding='utf-8')`.  
**Why:** On Windows, `Path.read_text()` defaults to `cp1252` (the Windows ANSI code page). UTF-8 text with non-ASCII characters (e.g., `ó`, emoji, curly quotes in doc files) will crash it.  
**Affected:** `scripts/bump_version.py` — fixed February 26, 2026.
---

## Database Pitfalls

### pitfall: kuzu reserved word properties

**Trigger:** Entity creation fails — `Binder exception: Cannot find property properties for e`  
**Action:** Use `props` not `properties`; use `entity_type` not `type`; use `entity_label` not `label`  
**Why:** Kuzu uses SQL for schema (DDL) but Cypher for operations (DML). Names must be valid in both. `properties` passes DDL, fails DML.  
**Source:** `docs/technical/kuzu-best-practices.md`, `docs/debug/database-compendium.md` Issue #1

### pitfall: kuzu schema operation validation gap

**Trigger:** New property added and schema applies cleanly, but CREATE operations fail  
**Action:** Test BOTH `CREATE NODE TABLE (...)` AND a `CREATE (entity {...})` statement in the same test  
**Why:** SQL-valid names can be Cypher-invalid. Schema creation and data operations use different parsers.  
**Source:** `docs/debug/database-compendium.md` Issue #1 (LAW #3)

### pitfall: kuzu stale lock blocking access

**Trigger:** "Elefante Mode is DISABLED" despite prior `enable()`, or "Could not acquire lock"  
**Action:** Check `~/.elefante/locks/write.lock`; if PID is dead or timestamp > 30s, delete it. v1.1.0+ auto-clears on next operation.  
**Why:** v1.0.1 used session-scoped locks held indefinitely. A crashed IDE leaves an orphaned lock. v1.1.0 uses transaction-scoped locks (auto-expire 30s).  
**Source:** `docs/debug/database-compendium.md` Issue #2, `docs/technical/kuzu-lock-monitoring.md`

### pitfall: kuzu database corrupted single file

**Trigger:** `kuzu_db` exists as a single file (not a directory); `Cannot open file` errors  
**Action:** Backup, delete `kuzu_db`, reinitialize. ChromaDB is unaffected.  
**Why:** Interrupted database creation or permissions issue produces a file instead of a directory structure.  
**Source:** `docs/debug/database-compendium.md` Issue #3

---

## MCP Pitfalls

### pitfall: mcp type signature list types tool

**Trigger:** Tools not showing in IDE  
**Action:** Return `list[types.Tool]` — not `List[Tool]`, not `list[Tool]`, not unannotated  
**Why:** MCP SDK uses strict runtime type checking; mismatches cause silent failure  
**Source:** `docs/debug/ai-behavior-compendium.md` (MCP LAW #1)

### pitfall: mcp action verification missing

**Trigger:** Tool returns "success" but user reports no change  
**Action:** After every write, read back the written record and fail explicitly if not found  
**Why:** ChromaDB and Kuzu can fail silently (disk full, permissions). Unverified success = silent data loss.  
**Source:** `docs/debug/ai-behavior-compendium.md` (Layer 5 Protocol)

### pitfall: mcp error missing context

**Trigger:** MCP tool throws but error message is just `"Error: str(e)"`  
**Action:** Include tool name, arguments, `type(e).__name__`, traceback, and timestamp in error response  
**Why:** Without context, debugging MCP errors requires re-running under special conditions  
**Source:** `docs/debug/ai-behavior-compendium.md` (MCP LAW #3)

### pitfall: mcp async blocking database call

**Trigger:** Server hangs or times out on database operations  
**Action:** Wrap synchronous Kuzu/ChromaDB calls in `asyncio.get_event_loop().run_in_executor(None, fn, ...)`  
**Why:** Kuzu and ChromaDB are synchronous. Calling them directly inside `async def` blocks the event loop.  
**Source:** `docs/debug/ai-behavior-compendium.md` (MCP LAW #4)

### pitfall: mcp stdout pollution json-rpc corrupt

**Trigger:** `invalid character 'I' looking for beginning of value` on connection  
**Action:** Route ALL logging to `sys.stderr`. `print()` to stdout breaks MCP. Check uvicorn `log_config`.  
**Why:** MCP communicates over stdin/stdout JSON-RPC. Any `INFO:` line on stdout instantly corrupts the stream.  
**Source:** `docs/debug/ai-behavior-compendium.md` (MCP LAW #6)

### pitfall: mcp vscode duplicate server scopes

**Trigger:** VS Code shows two identical `elefante` MCP servers  
**Action:** Keep `elefante` only in User `mcp.json`; ensure `.vscode/mcp.json` does NOT define `servers.elefante`; remove `chat.mcp.servers.elefante` / `roo-cline.mcpServers.elefante` if present; reload window  
**Why:** VS Code merges User + Workspace MCP configs; multiple scopes can register the same server name  
**Source:** `docs/technical/ide-mcp-configuration.md` (MCP LAW #8)

### pitfall: mcp write blocked compliance gate

**Trigger:** Write tool returns `gate_status: BLOCKED`  
**Action:** Call `elefante-MemorySearch` first (any query), then retry the write  
**Why:** Compliance gate (v1.6.0) mechanically blocks `MemoryAdd`, `MemoryUpdate`, `MemoryDelete`, `GraphConnect` until a search has been performed in the current session  
**Source:** `docs/debug/ai-behavior-compendium.md` (MCP LAW #9)

### pitfall: mcp response bloat token waste

**Trigger:** Returning massive JSON arrays with null properties.  
**Action:** Use recursive mathematical null-stripping (`_strip_nulls`) to compress the payload.  
**Why:** Agents have limited context windows. Passing empty arrays or null variables wastes thousands of tokens.  
**Source:** `docs/debug/memory-compendium.md` Issue #7

### pitfall: mcp actionable integration missing

**Trigger:** Agent retrieves memories but completely ignores the rules they contain.  
**Action:** Inject a hardcoded `suggested_action` header acting as a system prompt directive before the memory list.  
**Why:** Passive semantic matches are just "facts." Agents act on directives. A directive forces compliance.  
**Source:** `docs/debug/memory-compendium.md` Issue #9

---

## Memory Pitfalls

### pitfall: memory export chromadb api truncated

**Trigger:** Export returns 10 memories instead of all  
**Action:** Use `collection._collection.get(include=["documents","metadatas","embeddings"])` not `collection.query()`  
**Why:** `query()` applies semantic relevance filtering even with high `n_results`  
**Source:** `docs/debug/memory-compendium.md` Issue #1 (LAW #1)

### pitfall: memory search vs browse all

**Trigger:** User says "show me ALL my memories about X" — only top 10 returned  
**Action:** Use `elefante-MemorySearch(list_all=true)` + client-side filtering, not `elefante-MemorySearch` alone  
**Why:** `elefante-MemorySearch` returns top-N by semantic relevance, not completeness  
**Source:** `docs/debug/memory-compendium.md` Issue #2 (LAW #2)

### pitfall: memory temporal decay not active

**Trigger:** Memory scores not reflecting age  
**Action:** Verify temporal decay is active in `calculate_relevance_score()` (`src/models/memory.py`); decay runs in `_search_structured` and `_search_semantic`  
**Why:** Memory scores must decay over time (Ebbinghaus model) unless reinforced by retrieval  
**Source:** `docs/technical/temporal-memory-decay.md`

### pitfall: memory session vs persistent confusion

**Trigger:** User restarts IDE, AI has no memory of recent conversation  
**Action:** Explicitly save important turns with `elefante-MemoryAdd`; session buffer is NOT auto-persisted  
**Why:** Session buffer (RAM) and persistent memory (ChromaDB + Kuzu) are separate systems. Buffer clears on restart.  
**Source:** `docs/debug/memory-compendium.md` Issue #4 (LAW #4)

### pitfall: memory schema field roundtrip missing

**Trigger:** Memory stored with extra fields but retrieved with defaults  
**Action:** When adding a field to the schema, update BOTH `add_memory()` write path AND `_reconstruct_memory()` read path  
**Why:** Field must be mapped in both directions. Missing from read = always shows default.  
**Source:** `docs/debug/memory-compendium.md` Issue #7 (Pattern #4)

### pitfall: memory scoring similarity override suppress

**Trigger:** Excellent semantic matches (`sim > 0.85`) receive terrible composite scores due to heuristic penalties.  
**Action:** Use V4/V5 Cognitive Multi-Signal Scoring with a Smoothed Vector Baseline.  
**Why:** A pure heuristic equation can suppress highly relevant facts if they lack access count. Baseline guarantees true semantic matches floor at >=85% of their raw similarity.  
**Source:** `docs/debug/memory-compendium.md` Issue #8

---

## Documentation Pitfalls

### pitfall: documentation archive without index update CRITICAL

**Trigger:** Moving or archiving ANY file that is linked from an index  
**Action:** Before archiving: `grep -r "filename" docs/` — then update ALL index files that link to it  
**Why:** Ghost links remain for weeks. Future agents hit 404s. This happened Dec 11 → Dec 27 with schema files.  
**Source:** Developer practice — see also `pitfall: documentation partial refactor`

### pitfall: documentation partial refactor

**Trigger:** Renaming, moving, or deleting documentation files  
**Action:** Complete the full chain: (1) Move file → (2) Update ALL inbound links → (3) Update ALL index READMEs → (4) `grep -r "oldname" docs/` to verify clean  
**Why:** One file can be referenced from 5+ places. Partial refactors leave broken links silently.

---

## Quick Reference

| Category     | Most Common Pitfall        | Quick Fix                                             |
| ------------ | -------------------------- | ----------------------------------------------------- |
| Dashboard    | Stale snapshot             | `python scripts/update_dashboard_data.py`             |
| Dashboard    | Browser cache              | `Ctrl+Shift+R`                                        |
| Installation | Kuzu pre-existing dir      | Do not mkdir; let `GraphStore.__init__` handle it     |
| Installation | Wrong Python path          | Use `sys.executable` not `"python"`                   |
| Windows      | fcntl import               | `if sys.platform != "win32": import fcntl`            |
| Windows      | Activate.ps1 blocked       | `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` |
| Windows      | Wrong venv path            | Use `.venv\Scripts\python.exe` not `.venv/bin/python` |
| Windows      | MCP config not found       | `python scripts\configure_vscode_bob.py`              || Windows      | read_text encoding crash   | Always pass `encoding='utf-8'` to `read_text/write_text` || Database     | Reserved word `properties` | Use `props`                                           |
| Database     | Stale lock                 | Check `~/.elefante/locks/write.lock`, delete if stale |
| MCP          | Tools not showing          | `list[types.Tool]` not `List[Tool]`                   |
| MCP          | stdout pollution           | All logs → `sys.stderr`                               |
| MCP          | Write gate blocked         | Call `elefante-MemorySearch` first                    |
| MCP          | Response Bloat             | Recursive null-stripping payload                      |
| MCP          | Rules Ignored              | Use `suggested_action` directive                      |
| Memory       | Export truncated           | `collection._collection.get()` not `query()`          |
| Memory       | High sim, low score        | Smoothed Vector Baseline                              |
| Docs         | Ghost links after archive  | `grep -r "filename" docs/` before moving any file     |

---

## Adding New Pitfalls

When you encounter a new repeated mistake:

```markdown
### pitfall: [category] [keywords]

**Trigger:** [what action causes this]  
**Action:** [what to do]  
**Why:** [root cause]  
**Source:** [compendium file and issue number]
```

Full post-mortems belong in the relevant `docs/debug/*-compendium.md` file.

---

_Last updated: 2026-02-26 | Elefante v2.1.3 | Windows validated_
