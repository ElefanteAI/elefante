# Troubleshooting Protocol

**Philosophy:** Verify layers sequentially. Do not assume the layer below is working.

## Layer 1: The Metal (Environment)

- **Issue:** "ChromaDB not found" or Import Errors.
- **Fix:** Ensure you are using the `.venv` Python.
  - _Check:_ `pip install -r requirements.txt`.
- **Issue:** "Embedding model download failed."
  - _Fix:_ Force download: `python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"`.

## Layer 2: The Data (Persistence)

- **Issue:** Database corruption or initialization failure.
- **Fix:** Reset the data directories (Warning: Data Loss).

  ```bash
  rm -rf data/
  python scripts/init_databases.py
  ```

- **Issue:** "IO exception: Could not set lock on file" (KuzuDB).
- **Cause:** KuzuDB is single-writer. If the MCP server is running, it holds the write lock.
- **Fix 1 (CLI/Scripts):** Open the database in **Read-Only** mode.
  ```python
  kuzu.Database(path, read_only=True)
  ```
- **Fix 2 (Dashboard/Apps):** **Snapshotting**. Do not connect directly.
  - Fetch data via MCP or generate a JSON snapshot.
  - Read the snapshot in the app.

## Layer 3: The Connection (MCP)

- **Issue:** Server won't start in IDE.
- **Check 1:** Verify `settings.json` uses **Absolute Paths** for both `cwd` and `env.PYTHONPATH`.
- **Check 2:** Check logs in `logs/elefante.log`.

## System Health Check

Run the built-in diagnostic tool to validate all components:

```bash
python scripts/health_check.py
```

**Success Criteria:** All systems (Config, Embedding, Vector, Graph, Orchestrator) must report `HEALTHY`.

# Post-Mortems & Protocols

## 1. The Browser Loop (CRITICAL)

**Issue:** Repeated failures when verifying UI with `browser_subagent`, triggering system browser and annoying user.
**Root Cause:** Treating the internal browser as a robust, retryable resource.
**Protocol:** **"One Strike Rule"**.

1.  Try Internal Browser **ONCE**.
2.  If it fails (`target closed`, `page not found`), **STOP**.
3.  **Fallback**: Use `curl` or check server logs.
4.  **Never** escalate to the system browser automatically.

## 2. The "Garbage" Data

**Issue:** Raw database visualization was unintelligible (UUIDs, duplicates).
**Root Cause:** Direct mapping of DB schema to UI.
**Protocol:** **"Semantic Presentation Layer"**.

- **Deduplicate**: Merge entities by `(name, type)` before rendering.
- **Label**: Use content snippets, not IDs.
- **Size**: Use Degree Centrality for visual hierarchy.

## 3. Syntax Verification

**Issue:** `SyntaxError` in production code during rapid iteration.
**Protocol:** **"Compile Check"**.

- Always run `python -m py_compile <file>` before verifying behavior.
- Speed is useless if the code doesn't parse.
