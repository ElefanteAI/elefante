# Scripts naming convention

Goal: make each script name immediately communicate **purpose** and **scope**.

## Pattern

- `verb_object[_qualifier].py` (snake_case)
- Use clear verbs: `install`, `configure`, `verify`, `export`, `ingest`, `migrate`, `update`, `inspect`, `demo`, `debug`.
- Put experimental/one-off helpers under `scripts/debug/` or name them with a `debug_` prefix.

## Examples in this repo

- `configure_*` = write IDE/MCP client configs
- `verify_*` = run checks (health, protocol handshakes, repo hygiene)
- `export_*` / `ingest_*` / `migrate_*` = data workflows
- `disable_elefante_mode.py` = turn off Elefante Mode + show lock status

If you need a new script, prefer adding a new `verb_object` script rather than creating another near-duplicate with a vague name.

## Versioning scripts

| Script | Purpose | When to use |
|---|---|---|
| `version_counsel.py` | Smart advisor: analyses staged diff, classifies MAJOR/MINOR/PATCH, asks for confirmation before bumping | **Primary workflow** — run after `git add` |
| `bump_version.py X.Y.Z` | Atomically update version string across all 25 tracked files | Direct bump when version is already decided |
| `bump_version.py --check` | Verify all 25 files declare the same version (exit 1 on drift) | Run before every commit |

**Rules:** Version parts x, y, z must be natural numbers in `[0, 99]`. Both scripts enforce this. See `CONTRIBUTING.md` for the full versioning procedure.

## Debug scripts (`scripts/debug/`)

Diagnostic and rescue tools for broken state. Referenced from [`docs/pitfall-index.md`](../docs/pitfall-index.md).

| Script | Purpose | Safety |
|---|---|---|
| `dump_all_memories.py` | Raw ChromaDB memory dump to stdout | Read-only |
| `list_recent.py` | Show 10 most recent memories (via Orchestrator) | Read-only |
| `unlock_database.py` | Clear stuck transaction locks | Requires `--apply --confirm DELETE` |
| `remove_kuzu_lock.py` | Remove stale Kuzu write lock file | Requires `--apply --confirm DELETE` |
| `nuclear_reset_kuzu.py` | Backup and destroy corrupted Kuzu database | Requires `ELEFANTE_PRIVILEGED=1` |

## Privileged scripts (`scripts/privileged/`)

See [`scripts/privileged/README.md`](privileged/README.md) for privilege gating rules.

| Script | Purpose | Safety |
|---|---|---|
| `memory_surgeon.py` | Surgical memory removal with impact analysis | Dry-run by default |
| `memory_workbench.py` | Read-only memory connectivity inspector | Read-only |
