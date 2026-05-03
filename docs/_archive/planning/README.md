# Planning Documentation

> **Migration notice (2026-05-02):** Active release state, roadmap, feature lifecycle, optimization plans, ops plans, dev process plans, and UX plans are now consolidated in [`../../workspace/PLANNING.md`](../../workspace/PLANNING.md) — single living plan organized by aspect. PRD bodies in `spec-*.md` files below remain authoritative for individual feature designs and are cross-referenced from `PLANNING.md §4`. Future migration phase will fold PRD bodies into `PLANNING.md` and retire the per-feature files.

Future-facing intent and product-shaping specs. Operational learnings and reusable debugging rules live in [`../debug/best_practices.md`](../debug/best_practices.md) and the `ops-*-compendium.md` files. Implementation contracts for shipped features live in [`../technical/`](../technical/).

The intake gate for any new feature idea is [`spec-vision.md`](spec-vision.md) (its Ideas Backlog § A–§F is mirrored to `workspace/PLANNING.md §4.1`). If the idea survives the Four Laws and the Non-Goals, it gets a dedicated spec here AND a row in `workspace/PLANNING.md §4.2 In design`.

## Boundary

Planning docs are for future-facing intent. If the question is *what did we just learn from a failure?* — that belongs in [`../debug/best_practices.md`](../debug/best_practices.md) and the `ops-*-compendium.md` files. If the question is *what does the system contract do today?* — that belongs in [`../technical/`](../technical/). This directory is reserved for what is not yet shipped or what is being designed.

## Contents

| File | Purpose |
| ---- | ------- |
| [`spec-vision.md`](spec-vision.md) | What Elefante is, the Four Laws, the Non-Goals anchor, and the ideas backlog |
| [`spec-installer-procedure.md`](spec-installer-procedure.md) | Phase-1 installer product spec |
| [`spec-ide-integration-surface.md`](spec-ide-integration-surface.md) | Phase-2 installer: cross-IDE skill/rules/MCP distribution, singleton daemon, continuous doc-drift audit (PLANNING — docs in v2.10.0, implementation in v2.11 → v2.12) |
| [`spec-session-intelligence.md`](spec-session-intelligence.md) | Privacy-respecting session and invocation telemetry feature request (§6.7 closes GAP-025 via the Source/Origin schema co-owned with the IDE integration surface spec) |
| [`spec-retrieval-effectiveness.md`](spec-retrieval-effectiveness.md) | Per-memory retrieval provenance and helpfulness signal |
| [`spec-surface-split.md`](spec-surface-split.md) | Planned User / Developer / Agents folder split (PLANNING — not executed) |
| [`prd-documentation-strategy-protocol.md`](prd-documentation-strategy-protocol.md) | Strategy protocol for agent-maintained documentation (audience, loading model, authority, leakage scan); meta-process spec |
| [`integrations/agent-zero.md`](integrations/agent-zero.md) | Agent Zero integration target: Elefante as the persistent memory layer |

## Related

- [`../technical/`](../technical/) — how things work now
- [`../debug/`](../debug/) — what broke and the lesson
- [`../../agents/orchestrator.md`](../../agents/orchestrator.md) — operational authority for agents building Elefante
