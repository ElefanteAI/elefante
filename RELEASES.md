# Elefante Releases

This file is a high-level index of released versions.
For the full, detailed change history, see [CHANGELOG.md](CHANGELOG.md).

---

## Current Baseline

- **v1.6.0 (Production baseline)**
  - Compliance Gate enforcement (search-before-write)
  - `.github/copilot-instructions.md` for layered defense
  - Gated write operations: `elefanteMemoryAdd`, `elefanteGraphEntityCreate`, `elefanteGraphRelationshipCreate`, `elefanteGraphConnect`

---

## Previous Releases

- **v1.5.0** — V5 cognitive features (explanations, health, proactive surfacing)
- **v1.4.0** — V4 cognitive retrieval engine (6-signal composite scoring)
- **v1.3.0** — Embedding model upgrade to `thenlper/gte-base` (768-dim)
- **v1.1.0** — Transaction-scoped locking (multi-IDE safety)

---

## Verification (what “version” means)

- Runtime/package version is defined in `src/__init__.py`.
- Dashboard reports versions via `http://127.0.0.1:8000/api/stats`.
