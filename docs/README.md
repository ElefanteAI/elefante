# Elefante Documentation

> **v2.10.0** · Stable contracts only. Live development state lives in [`../workspace/`](../workspace/). Loadable agent protocols live in [`../agents/`](../agents/).

This folder follows [Diátaxis](https://diataxis.fr/). Every doc has exactly one type:

| Folder | Type | Question it answers | When to read |
|--------|------|---------------------|--------------|
| [`reference/`](reference/) | **SPEC** — what the system IS | "What is the contract?" | Looking up a frozen contract |
| [`how-to/`](how-to/) | **OPS** — what to DO | "How do I accomplish X?" | Performing a task |
| [`explanation/`](explanation/) | **CONCEPT** — WHY | "Why does this exist?" | Understanding design |
| [`_archive/`](_archive/) | audit trail | "What was here before 2026-05-02?" | Migration provenance only |

---

## Reference (`reference/`) — what the system IS

| Doc | Contract |
|-----|----------|
| [`architecture.md`](reference/architecture.md) | System design, triple-layer brain, retrieval workflow |
| [`tools.md`](reference/tools.md) | MCP tool reference (16 tools, 2 prompts) — full schemas. v2.10.0: Memory consolidated (5→1, action-discriminated). |
| [`scoring.md`](reference/scoring.md) | 5-signal cognitive scoring (vector / concept / co-activation / authority / temporal) |
| [`ingestion.md`](reference/ingestion.md) | 5-step pipeline (Extract → Classify → Integrity → Write → Reinforce) |
| [`memory-schema.md`](reference/memory-schema.md) | V4 cognitive fields + V5 knowledge topology |
| [`memory-identity.md`](reference/memory-identity.md) | `namespace` + `canonical_key` first-class fields (DRAFT) |
| [`dashboard-snapshot.md`](reference/dashboard-snapshot.md) | Dashboard JSON schema |
| [`self-protocol.md`](reference/self-protocol.md) | Whole-system MCP self-protocol verification contract |
| [`token-intelligence.md`](reference/token-intelligence.md) | Token-budget layer (TOKEN_STATS, type budgets, density warnings) — shipped v2.5.0 |

Source-of-truth for every spec is `src/`; specs lag. When formula and spec disagree, source wins.

## How-to (`how-to/`) — what to DO

| Doc | Procedure |
|-----|-----------|
| [`install.md`](how-to/install.md) | Full install + Python version details |
| [`configure-ide.md`](how-to/configure-ide.md) | IDE MCP setup (VS Code, Cursor, Bob, Antigravity) |
| [`run-mcp-server.md`](how-to/run-mcp-server.md) | Manual server startup + handshake verification |
| [`view-dashboard.md`](how-to/view-dashboard.md) | Dashboard launch + verification |
| [`restart.md`](how-to/restart.md) | Graceful restart, lock cleanup, force-kill |
| [`rollback.md`](how-to/rollback.md) | Backup + restore |
| [`docker.md`](how-to/docker.md) | Docker deployment |
| [`kuzu-troubleshooting.md`](how-to/kuzu-troubleshooting.md) | Kuzu reserved words, locking, troubleshooting |
| [`agent-handoff.md`](how-to/agent-handoff.md) | Autonomous agent integration |
| [`close-a-feature.md`](how-to/close-a-feature.md) | Closure sequence (CLEAN → DOCS → VERSION → COMMIT) |

## Explanation (`explanation/`) — WHY

| Doc | Concept |
|-----|---------|
| [`vision.md`](explanation/vision.md) | Thesis, Four Laws, Non-Goals, ideas backlog |

---

## Where things are NOT

| You want… | Go to |
|-----------|-------|
| BUG/GAP tracker | [`../workspace/ISSUES.md`](../workspace/ISSUES.md) |
| Bug postmortems | [`../workspace/postmortems/`](../workspace/postmortems/) |
| Cross-bug lessons | [`../workspace/lessons.md`](../workspace/lessons.md) |
| Active release plan | [`../workspace/PLANNING.md`](../workspace/PLANNING.md) |
| Architecture decisions (ADRs) | [`../workspace/decisions/`](../workspace/decisions/) |
| Draft proposals (pre-spec) | [`../workspace/proposals/`](../workspace/proposals/) |
| Loadable agent protocols | [`../agents/`](../agents/) |
| Single developer constitution | [`../agents/orchestrator.md`](../agents/orchestrator.md) |
| Universal agent entry | [`../AGENTS.md`](../AGENTS.md) |
| End-user agent constitution | [`../.github/copilot-instructions.md`](../.github/copilot-instructions.md) |
| IDE integration manifest | [`../agents/manifests/ide-integration.yaml`](../agents/manifests/ide-integration.yaml) |
| Release history | [`../CHANGELOG.md`](../CHANGELOG.md) |

---

## Boundaries (Diátaxis-pure)

- **`reference/` is for what the system IS.** No how-to steps, no rationale paragraphs.
- **`how-to/` is for procedures.** Goal-oriented. Numbered steps. No conceptual deep-dives.
- **`explanation/` is for WHY.** Design rationale, philosophy, thesis. No commands, no schemas.
- **State (BUG/GAP, ADRs, proposals, postmortems) lives in `workspace/`, not here.** This folder holds frozen contracts only.

A file in the wrong folder is a structural bug. The forbidden-pattern guard (`tests/test_developer_routing.py`) catches some drift; type purity is enforced by code review.

## Restructure (2026-05-02)

This `docs/` was rebuilt from the ground up on 2026-05-02. The pre-restructure tree (which mixed audience / type / lifecycle / surface axes in eight subfolders) is preserved in [`_archive/`](_archive/) for audit. See [`../CHANGELOG.md`](../CHANGELOG.md) `[2.10.0]` `### Changed` for the full migration record.
