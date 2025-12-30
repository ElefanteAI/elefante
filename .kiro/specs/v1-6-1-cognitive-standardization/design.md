# Design: V1.6.1 Cognitive Field Standardization

*Methodology: Kiro Spec-Driven Development (R>D>T = Requirements → Design → Tasks)*

## 1. Overview

Problem: V4 concept-overlap scoring depends on `MemoryMetadata.concepts` and `MemoryMetadata.surfaces_when`. Historically these fields were sometimes only present in `custom_metadata` and/or stored as stringified lists, causing reconstruction to drop typing and concept overlap to collapse to 0.

Design goal: standardize *indexing metadata* (not content) so cognitive fields are reliably available as typed fields on read.

## 2. Write Path (Vector Store)

Chroma metadata values must be primitives. Therefore:

- `concepts: list[str]` → persisted as JSON string via `json.dumps(list)`.
- `surfaces_when: list[str]` → persisted as JSON string via `json.dumps(list)`.
- `authority_score: float` → persisted as float.

Precedence rules:
- Prefer first-class typed fields (`memory.metadata.concepts`, `memory.metadata.surfaces_when`, `memory.metadata.authority_score`).
- Fall back to `custom_metadata` if typed fields are empty.
- Do not let generic custom-metadata flattening overwrite these top-level keys.

## 3. Read Path (Reconstruction)

Reconstruction MUST populate typed fields:

- Parse `concepts` and `surfaces_when` from:
  1) top-level metadata keys, else
  2) `custom_metadata`.

Back-compat parsing strategy (`parse_string_list`):
- If value is a list, cast each item to string.
- If value is a string:
  - Try JSON list parse when it looks like `[...]`.
  - Fallback to Python `ast.literal_eval` when it looks like `[...]`.
  - Fallback to comma-split when it contains commas.
  - Else treat as a single-item list.
- Never raise; return `[]` on failure.

`authority_score`:
- Parse to float from top-level or `custom_metadata`.
- Clamp to [0.0, 1.0].

Canonicalization on read:
- Apply deterministic canonicalization for stable matching (does not rewrite memory content).

## 4. Testing Strategy

- Persistence roundtrip test using an isolated Chroma directory and a fresh VectorStore instance.
- Unit test validating non-zero concept overlap after canonicalization.

## 5. Migration Strategy

Migration script (`scripts/migrate_cognitive_fields_v161.py`):
- Reads ALL memories from ChromaDB
- For each memory:
  - Parses `concepts` and `surfaces_when` using back-compat logic
  - Canonicalizes labels
  - Re-encodes as JSON strings
  - Clamps `authority_score` to [0.0, 1.0]
  - Marks `processing_status=processed` and `migration_v161=<timestamp>`
- Updates metadata in place
- Supports `--dry-run` for preview

## 6. Approval Gate

Stop here.

Do not proceed to **Tasks** until the user explicitly approves this **Design**.
