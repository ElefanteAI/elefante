# Tasks: V1.6.1 Cognitive Field Standardization

*Methodology: Kiro Spec-Driven Development (R>D>T = Requirements → Design → Tasks)*

## Task 1 — Persist cognitive fields as primitives

- Ensure vector-store write path stores:
  - `concepts` / `surfaces_when` as JSON strings
  - `authority_score` as float
- Ensure custom-metadata flattening never overwrites these top-level keys.

## Task 2 — Reconstruct typed cognitive fields

- Implement best-effort back-compat parsing for:
  - JSON list strings: `[...]`
  - Python list repr strings: `[...]`
  - comma-joined strings
- Populate `MemoryMetadata.concepts` / `surfaces_when` / `authority_score`.
- Clamp `authority_score` to [0.0, 1.0].

## Task 3 — Add regression tests

- Persistence: cognitive fields survive Chroma roundtrip.
  - Covered by: `tests/test_memory_persistence.py::TestMemoryPersistence::test_cognitive_fields_roundtrip_in_vector_store`
- Retrieval signal: canonicalized variants yield overlap > 0.
  - Covered by: `tests/test_v4_concept_overlap.py`

## Task 4 — Migrate existing memories

- Run migration script to apply cognitive field standardization to ALL existing memories:
  ```bash
  .venv/bin/python scripts/migrate_cognitive_fields_v161.py --dry-run  # preview
  .venv/bin/python scripts/migrate_cognitive_fields_v161.py            # apply
  ```
- Script location: `scripts/migrate_cognitive_fields_v161.py`

## Task 5 — Verification

- Run:
  - `pytest -q tests/test_memory_persistence.py`
  - `pytest -q tests/test_v4_concept_overlap.py`
- Verify migration summary shows all memories processed

## Approval Gate

Stop here.

Do not begin **Implementation** until the user explicitly approves this **Task Plan**.
