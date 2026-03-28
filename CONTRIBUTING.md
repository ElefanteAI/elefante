# Contributing to Elefante

Thank you for your interest in contributing to Elefante!

## Development Philosophy

> **SDD enforcement is now native inside Elefante (v2.2.1).** Six SDD gate directives are injected into every tool response unconditionally. Gate 4 (simulator) is mechanically enforced via `.git/hooks/pre-commit`. Human-readable reference: [`docs/technical/sdd-development-protocol.md`](docs/technical/sdd-development-protocol.md).

**1. Cleanliness**: Leave the repo cleaner than you found it. No temp files, no dead code.
**2. Memory First**: New features must be memory-aware. Use `elefante-grounding` prompt principles.
**3. Behavioral Relevance**: We do not assign "importance" to memories manually. Scores (0-100) are computed by the system based on usage.

## Code Standards

- **Python 3.11+**
- **Type Hints**: Required for all new code.
- **Naming**:
  - Tools: `elefante-PascalCase` (e.g., `elefante-MemoryAdd`)
  - Internal functions: `snake_case`
  - Classes: `PascalCase`

## Project Structure

```
src/
  mcp/          # MCP Server & Tools
  core/         # Logic (Orchestrator, Vector/Graph stores, ETL, Retrieval)
  models/       # Pydantic models (v2.2.2 schema)
  modules/      # Session Distiller
  dashboard/    # React/Vite app
  utils/        # Config, curation, logging
scripts/        # Maintenance
docs/           # Documentation
tests/          # Pytest suite
```

## Pull Request Etiquette

1. **Title**: Structured (feat:, fix:, docs:, chore:).
2. **Context**: Explain *why*, not just what.
3. **Tests**: Must pass locally.
4. **Docs**: Update `docs/technical/usage.md` if you change tool signatures.

## Versioning

**Single source of truth**: `src/__init__.py` → propagated by script.

### Recommended workflow — smart advisor

After staging your changes, run `version_counsel.py`. It analyses the diff,
classifies the change level, and **asks before doing anything**:

```bash
# 1. Stage your work
git add <files>

# 2. Ask the advisor (Windows)
.venv\Scripts\python.exe scripts\version_counsel.py

# 2. Ask the advisor (macOS/Linux)
.venv/bin/python scripts/version_counsel.py
```

The advisor will print:

```
  I believe this development, if you want to save it,
  it should be v2.2.0  (bump y  (MINOR)),
  because: new Elefante MCP tool added (src/mcp/tools/foo.py).

  ┌──────┬──────────┬──────────────────────────────────────────────┐
  │ Part │ Meaning  │ When to bump                                 │
  ├──────┼──────────┼──────────────────────────────────────────────┤
  │  x   │ MAJOR    │ Breaking change — existing installs break    │
  │  y   │ MINOR    │ New feature, backward-compatible             │
  │  z   │ PATCH    │ Bug fix, docs, internal cleanup              │
  └──────┴──────────┴──────────────────────────────────────────────┘

  Bump to v2.2.0?  [y / N / enter override e.g. 2.3.0]:
```

Confirm `y`, press `N` to cancel, or type a manual version to override.
On confirmation it calls `bump_version.py` automatically.

### Manual bump (if you already know the version)

```bash
# Bump version in all 25 files at once (Windows)
.venv\Scripts\python.exe scripts\bump_version.py 2.2.0

# Bump version (macOS/Linux)
.venv/bin/python scripts/bump_version.py 2.2.0

# Verify no file has drifted (exit code 1 = drift detected)
.venv\Scripts\python.exe scripts\bump_version.py --check
```

**Rules — MANDATORY:**
- NEVER edit version strings by hand in individual files.
- ALWAYS use `version_counsel.py` (interactive) or `bump_version.py X.Y.Z` (direct) — never manual file edits.
- Run `--check` before committing to catch drift.
- CHANGELOG.md and RELEASES.md entries must be written manually (they are historical logs, not current-version declarations).
- If a new doc file has a version marker, ADD IT to `scripts/bump_version.py` TARGETS before the next version bump.

**Semantic versioning (x.y.z):**
- `x` — MAJOR: breaking changes requiring user action or migration
- `y` — MINOR: new features, backward compatible
- `z` — PATCH: bug fixes, documentation additions, small improvements

**When to bump:**
- Bug fix or doc-only change → patch (`z`)
- New MCP tool, new feature, new OS support → minor (`y`)
- Breaking schema change, DB migration required → major (`x`)
