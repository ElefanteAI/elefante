# Requirements: V1.6.1 Cognitive Field Standardization

*Methodology: Kiro Spec-Driven Development (R>D>T = Requirements → Design → Tasks)*

## 1. Goal

Ensure `concepts`, `surfaces_when`, and `authority_score` are consistently persisted and reconstructed end-to-end so V4 concept-overlap scoring is reliable.

Additionally, migrate ALL existing memories to this standard so the entire knowledge base benefits from cognitive retrieval.

## 2. Non-Goals

- Do not rewrite memory `content`.
- Do not change scoring weights or ranking policy.
- Do not introduce new dedup/consolidation behavior.

## 3. Definitions

- **Cognitive fields**: `concepts: list[str]`, `surfaces_when: list[str]`, `authority_score: float`.
- **Canonicalization**: deterministic normalization of labels for matching (no content rewriting).
- **Back-compat parse**: ability to read legacy stored values such as JSON list strings, Python repr list strings, or comma-joined strings.

## 4. User Stories

- As a user, when I store a memory with cognitive fields, I want them to survive persistence and reload unchanged (typed), so retrieval stays stable.
- As the system, when I encounter legacy metadata formats, I want to parse them safely, so upgrades don’t silently degrade scoring.

## 5. Acceptance Criteria (EARS)

- WHEN a memory is stored with `concepts` and/or `surfaces_when` as `list[str]`, THE SYSTEM SHALL persist them in the vector store in a primitive-safe encoding and reconstruct them back into typed `list[str]`.
- WHEN a memory is stored with `authority_score` as a number, THE SYSTEM SHALL persist it and reconstruct it as a float clamped to [0.0, 1.0].
- WHEN stored metadata contains legacy formats (JSON list string, Python list repr string, or comma-joined string), THE SYSTEM SHALL reconstruct `concepts`/`surfaces_when` as `list[str]` with best-effort parsing (no exceptions propagated).
- WHEN query and memory refer to the same concept using different surface forms (case/spacing variants), THE SYSTEM SHALL produce a non-zero concept-overlap score after canonicalization.

## 6. Verification

- Unit test: concept overlap > 0 with canonicalized variants.
- Persistence test: vector-store roundtrip preserves typed cognitive fields.
- Migration script: all existing memories re-processed with canonicalized cognitive fields.

## 7. Approval Gate

Stop here.

Do not proceed to **Design** until the user explicitly approves these **Requirements**.
