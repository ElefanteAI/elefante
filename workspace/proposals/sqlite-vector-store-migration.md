# SQLite Vector Store Migration

## Decision

Elefante now has an opt-in, dependency-free SQLite vector-store backend. It is
the recommended escape path for GAP-029, but it is **not** the default and it
does not read, modify, or migrate existing ChromaDB data.

The current default remains ChromaDB until the user explicitly authorizes a
backup-first migration. This preserves current installations and prevents an
unreviewed storage conversion from silently changing retrieval behavior.

## Why SQLite

- Embedded and local-only: no vector-server process or network client.
- Uses Python's standard SQLite runtime and NumPy already required by Elefante.
- Stores the complete versioned `Memory` JSON contract plus a float32 embedding
  in one file, preserving metadata that ChromaDB's primitive-only metadata
  format flattens.
- Exact cosine search is deterministic and dependency-free. It is appropriate
  for the initial developer-memory migration path; indexing is a later,
  benchmark-gated optimization rather than a precondition for correctness.

## Benchmark Evidence

`scripts/demo/benchmark_sqlite_vector_store.py` creates only a temporary,
deterministic SQLite store and exercises the public exact-search path. It never
opens or changes an existing ChromaDB store. On the current development CPU,
5,000 synthetic 768-dimensional memories, 20 warm searches, and `limit=10`
measured p50 **221.522 ms** and p95 **235.530 ms**. This is a baseline, not a
cross-platform SLO or a default-change decision. Run the same command on each
supported operating system and realistic corpus before selecting a threshold:

```bash
.venv/bin/python scripts/demo/benchmark_sqlite_vector_store.py \
  --records 5000 --queries 20 --dimension 768 --limit 10 --max-p95-ms 300
```

Kuzu is not the recommended replacement: its upstream repository is archived.
`sqlite-vec` is not selected for the first migration because its maintainers
describe it as pre-v1 with possible breaking changes.

## Current Safe Capability

Set this only for a fresh, isolated installation or an explicitly prepared
empty data directory:

```yaml
elefante:
  vector_store:
    type: sqlite
    persist_directory: ~/.elefante/data/vector
```

`ELEFANTE_VECTOR_STORE_TYPE=sqlite` is also supported. With
`ELEFANTE_DATA_DIR`, an unset SQLite directory resolves to `data/vector`; the
existing ChromaDB default remains `data/chroma`.

The SQLite file is named `<collection_name>.sqlite3`. It is never created by a
default ChromaDB installation.

The shared daemon and an explicit Elefante-mode shutdown both release the
SQLite handle before they relinquish their graph-store resources. The existing
checksum-manifested backup and dry-run-first restore commands include this file
as ordinary durable data; a regression test verifies that its contents and the
replaced copy are recoverable.

Read-only JSON/CSV export also uses the configured embedded backend, and the
privileged factory reset moves the default `data/vector` directory as well as
the default ChromaDB and Kuzu locations into its timestamped recovery area.
It also reads explicit vector and graph paths from the configured Elefante YAML
file, failing closed if a target would contain the recovery directory. Dashboard
snapshot generation reads the configured embedded backend, including SQLite,
and has a regression proof for both backend paths.

## Migration Gate

`scripts/lifecycle/migrate_chroma_to_sqlite.py` now implements the conversion
and parity gate without silently switching storage authority. Its default run
uses only temporary output. `--apply` requires a verified backup whose Chroma
files exactly match the source plus `--confirm-stopped STOPPED`; it reserves a
new SQLite directory without replacing any existing path, but leaves ChromaDB
and Elefante configuration unchanged.
The operator must validate the result before changing configuration.

The authorized migration sequence must:

1. Stop the daemon and every database-owning process.
2. Confirm shutdown completed, then create and verify an Elefante backup archive.
3. Run the default temporary dry-run and inspect its JSON parity report.
4. Re-run with `--apply`, the verified backup path, and the explicit stopped
   confirmation to write a new SQLite directory beside Chroma, never in place.
5. Validate record count, UUID set, reconstructed metadata JSON, embedding dimension,
   and deterministic search parity on a representative corpus.
6. Leave ChromaDB untouched until the user validates the new store.
7. Support an immediate configuration rollback to ChromaDB and preserve the
   backup archive.

## Acceptance Criteria Before Default Change

- Fresh SQLite CRUD, filters, pagination, search, provenance, update, delete,
  backup, restore, and restart contracts pass on macOS, Linux, and Windows.
- The migration dry-run and apply paths have isolated fixture round-trips with
  UUID/metadata/embedding/search-parity evidence and exact backup matching.
- Benchmark evidence establishes an acceptable retrieval latency envelope at
  realistic memory volumes; any index addition is separately versioned and
  benchmarked.
- `pip-audit` is clean after ChromaDB is removed from the runtime lock.
- Migration, rollback, backup, and recovery documentation are independently
  reviewed against the shipped command behavior.
