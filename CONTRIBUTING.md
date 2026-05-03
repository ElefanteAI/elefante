# Contributing to Elefante

Thank you for your interest in contributing to Elefante!

## Development Philosophy

> **SDD enforcement is now native inside Elefante (v2.2.1).** Six SDD gate directives are injected into every tool response unconditionally. Gate 4 (simulator) is mechanically enforced via `.git/hooks/pre-commit`. Human-readable reference: [`agents/orchestrator.md`](agents/orchestrator.md).

**1. Cleanliness**: Leave the repo cleaner than you found it. No temp files, no dead code.
**2. Memory First**: New features must be memory-aware. Use `elefante-grounding` prompt principles.
**3. Behavioral Relevance**: We do not assign "importance" to memories manually. Scores (0-100) are computed by the system based on usage.
**4. Token Efficiency**: Every token Elefante injects must earn its place. Wasted tokens — filler, redundant context, irrelevant memories — degrade the response. Quality per token is the metric.

**For AI agents developing Elefante:** Read [`agents/orchestrator.md`](agents/orchestrator.md) — the single operational authority. It points to [`workspace/ISSUES.md`](workspace/ISSUES.md) for the Known Issues tracker.

## Code Standards

- **Python 3.11+**
- **Type Hints**: Required for all new code.
- **Naming**:
  - Tools: `elefante-PascalCase` (e.g., `elefante-Memory(action="add")`)
  - Internal functions: `snake_case`
  - Classes: `PascalCase`

## Project Structure

```
src/
  mcp/          # MCP Server & Tools
  core/         # Logic (Orchestrator, Vector/Graph stores, ETL, Retrieval)
  models/       # Pydantic models (v2.10.0 schema)
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
4. **Docs**: Update `docs/reference/tools.md` if you change tool signatures.

## Versioning

**Single source of truth**: `src/__init__.py` → propagated by script.

### Recommended workflow — smart advisor

After staging your changes, run `scripts/ci/advise_version_bump.py`. It analyses the diff,
classifies the change level, and recommends the version you should document in `CHANGELOG.md` before cutting the release:

```bash
# 1. Stage your work
git add <files>

# 2. Ask the advisor (Windows)
.venv\Scripts\python.exe scripts\ci\advise_version_bump.py

# 2. Ask the advisor (macOS/Linux)
.venv/bin/python scripts/ci/advise_version_bump.py
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
If the matching `CHANGELOG.md` entry already exists, the advisor can hand off to `bump_version.py` automatically. If not, it stops after printing the exact next steps so the changelog stays the release gate.

### Manual bump (if you already know the version)

```bash
# Bump version in all 25 files at once (Windows)
.venv\Scripts\python.exe scripts\ci\bump_version.py 2.2.0

# Bump version (macOS/Linux)
.venv/bin/python scripts/ci/bump_version.py 2.2.0

# Verify no file has drifted (exit code 1 = drift detected)
.venv\Scripts\python.exe scripts\ci\bump_version.py --check
```

If the local repo version was advanced too far before anything was published, use an explicit rebaseline instead of manual edits:

```bash
# Unpublished release correction only
.venv/bin/python scripts/ci/bump_version.py 2.8.0 --allow-rebaseline
```

**Rules — MANDATORY:**
- NEVER edit version strings by hand in individual files.
- ALWAYS use `scripts/ci/advise_version_bump.py` (interactive) or `scripts/ci/bump_version.py X.Y.Z` (direct) — never manual file edits.
- If correcting an unpublished local overshoot, use `scripts/ci/bump_version.py X.Y.Z --allow-rebaseline` instead of editing files by hand.
- Run `--check` before committing to catch drift.
- CHANGELOG.md entries must be written manually (it is a historical log, not a current-version declaration).
- NEVER push a `v*` tag without a matching `CHANGELOG.md` entry.
- GitHub release bodies are rendered from the matching CHANGELOG entry by `scripts/ci/render_release_notes.py`. If the changelog entry is weak, the release page will be weak.
- If a new doc file has a version marker, ADD IT to `scripts/ci/bump_version.py` TARGETS before the next version bump.

**Semantic versioning (x.y.z):**
- `x` — MAJOR: breaking changes requiring user action or migration
- `y` — MINOR: new features, backward compatible
- `z` — PATCH: bug fixes, documentation additions, small improvements

**When to bump:**
- Bug fix or doc-only change → patch (`z`)
- New MCP tool, new feature, new OS support → minor (`y`)
- Breaking schema change, DB migration required → major (`x`)
