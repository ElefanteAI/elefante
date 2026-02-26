# Contributing to Elefante

Thank you for your interest in contributing to Elefante!

## Development Philosophy

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
  models/       # Pydantic models (v2.1.3 schema)
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
- ALWAYS run `bump_version.py X.Y.Z` to update all 25 files atomically.
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
