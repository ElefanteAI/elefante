# Contributing to Elefante

Thank you for your interest in contributing to Elefante!

## Development Philosophy

> **Development follows the repository SDD protocol.** The maintained routing
> tests enforce documented contracts; eligible developer-mode operations also
> receive concise protocol guidance at runtime. The human-readable authority is
> [`agents/orchestrator.md`](agents/orchestrator.md).

**1. Cleanliness**: Leave the repo cleaner than you found it. No temp files, no dead code.
**2. Memory First**: New features must be memory-aware. Use `elefante-grounding` prompt principles.
**3. Behavioral Relevance**: We do not assign "importance" manually. Memory
scores are system-managed; creation starts at 100 and retrieval later combines
semantic, concept, co-activation, authority, and temporal signals.
**4. Token Efficiency**: Correctness comes first. Every injected token must
still earn its place because filler, redundant context, and irrelevant memory
can degrade the response.

**For AI agents developing Elefante:** Read [`agents/orchestrator.md`](agents/orchestrator.md) — the single operational authority. It points to [`workspace/ISSUES.md`](workspace/ISSUES.md) for the Known Issues tracker.

## Code Standards

- **Python 3.11, 3.12, or 3.13** (release CI currently uses 3.11)
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
  models/       # Current Pydantic data models
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
# Bump every authoritative version declaration (Windows)
.venv\Scripts\python.exe scripts\ci\bump_version.py 2.2.0

# Bump every authoritative version declaration (macOS/Linux)
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
- Do not add public "current published release" claims to
  `scripts/ci/bump_version.py`; package version can advance before publication.
  Update those public claims only after the tag and assets exist, then run the
  release-claim regression.

**Semantic versioning (x.y.z):**
- `x` — MAJOR: breaking changes requiring user action or migration
- `y` — MINOR: new features, backward compatible
- `z` — PATCH: bug fixes, documentation additions, small improvements

**When to bump:**
- Bug fix or doc-only change → patch (`z`)
- New MCP tool, new feature, new OS support → minor (`y`)
- Breaking schema change, DB migration required → major (`x`)
