# Elefante Releases

This file is a high-level, human-readable index of released versions.
For full detail, see [CHANGELOG.md](CHANGELOG.md).

---

## Current Baseline (recommended)

- **v1.6.0 (2025-12-28)**
  - Compliance Gate: enforced search-before-write for all write tools
  - Layered defense via `.github/copilot-instructions.md`

---

## Release Index

- **v1.5.0 (2025-12-28)**
  - V5 cognitive features: retrieval explanations, memory health, conflict detection, proactive surfacing

- **v1.4.0 (2025-12-27)**
  - V4 cognitive retrieval engine: 6-signal composite scoring (replaces raw vector similarity)

- **v1.3.0 (2025-12-27)**
  - Embedding model upgrade shipped: `thenlper/gte-base` (768-dim) and migration path for existing ChromaDB data

- **v1.2.0 (2025-12-27)**
  - Minor fixes and preparation work for schema/migration operations
  - Embedding model evaluation and test batteries across multiple candidates
  - Decision milestone: `thenlper/gte-base` (768-dim) identified as the best option to ship next

- **v1.1.0 (2025-12-26)**
  - Transaction-scoped locking for multi-IDE safety

- **v1.0.1 (2025-12-11)**
  - Protocol enforcement + initial multi-IDE safety mode controls

- **v1.0.0 (2025-12-05)**
  - First production baseline release

---

## Verification (what “version” means)

- Runtime/package version is defined in `src/__init__.py`.
- Dashboard reports versions via `http://127.0.0.1:8000/api/stats`.
