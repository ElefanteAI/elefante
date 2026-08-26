# Legacy ChromaDB to SQLite Support Path

> **Status:** COMPLETED for fresh installations. SQLite is the released default;
> this document remains only for operators with an existing legacy ChromaDB store.

## Current decision

Fresh Elefante v2.12.3 installations use the embedded SQLite vector store plus
Kuzu. ChromaDB is not in the production dependency lock. Elefante does not
silently inspect, convert, or delete a legacy ChromaDB store.

The support utility `scripts/lifecycle/migrate_chroma_to_sqlite.py` stages and
verifies a legacy conversion. It does not switch the configured backend and it
does not remove the source store.

## Why SQLite became the default

- It is embedded and local-only.
- It stores the complete versioned `Memory` JSON plus explicit float32 vectors.
- Exact cosine search is deterministic.
- It removed the former ChromaDB production advisory and dependency footprint.

Kuzu remains the released graph store. Replacing it is a separate architectural
decision and is not implied by the vector-store change.

## Fresh-install contract

```yaml
elefante:
  vector_store:
    type: sqlite
    persist_directory: ~/.elefante/data/vector
```

`ELEFANTE_VECTOR_STORE_TYPE=sqlite` and `ELEFANTE_DATA_DIR` are supported. The
SQLite file is named `<collection_name>.sqlite3`. Backup, restore, export,
factory-reset, shutdown, and dashboard-snapshot code use the configured store.

## Legacy migration gate

Only use this path for an existing ChromaDB installation:

1. Stop the daemon and every process that can own either database.
2. Create and verify a checksummed Elefante backup.
3. Run the migration utility without `--apply`; inspect its parity report.
4. Re-run with `--apply`, the verified backup, and
   `--confirm-stopped STOPPED`. The tool writes a new SQLite destination.
5. Verify record IDs, reconstructed memory JSON, embedding dimensions, and
   representative search parity.
6. Change configuration only after validation. Preserve both the ChromaDB
   source and backup until the SQLite runtime is accepted.

The migration is an explicit support operation, not part of normal customer
installation and not a marketing feature.

## Verification

```bash
./.venv/bin/python -m pytest tests/test_sqlite_vector_store.py -q
uv tool run pip-audit --requirement requirements.lock --disable-pip --require-hashes --strict --progress-spinner off
```

`scripts/demo/benchmark_sqlite_vector_store.py` provides a disposable local
latency measurement. Historical measurements are not a cross-platform SLO.
