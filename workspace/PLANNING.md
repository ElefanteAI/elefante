---
status: living
last_updated: 2026-08-26
audience: developer-agents
authority: state + roadmap + features + aspect-plans for Elefante development
related:
  - agents/orchestrator.md  # constitution (rules)
  - workspace/ISSUES.md                  # BUG/GAP tracker
  - agents/manifests/ide-integration.yaml  # integration manifest
---

# PLANNING — Elefante Developer Workspace

> **Single living plan.** Vision · Released Product · Roadmap · Features · Optimization · Ops · Dev · UX · Meta-process.
>
> Read top-to-bottom for full context. Jump to a section by aspect when in doubt.
>
> **Update protocol:** every session that closes a P-decision, OB blocker, BUG/GAP row, or shifts a feature status updates the relevant subsection IN PLACE. **Do not create new dated state files. Do not create CURRENT_STATE.md, SNAPSHOT.md, or HANDOFF-YYYY-MM-DD.md** (forbidden patterns enforced by `tests/test_developer_routing.py::test_no_forbidden_filename_patterns_in_active_docs_or_agents`).

---

## §1 Vision

**Elefante is a local memory authority that maximizes accepted task quality per
total token.**

Every AI agent runs on the same physics: a finite context window where every token either raises the probability of a correct answer or dilutes it. Most workflows lose by injecting noise — restated history, irrelevant retrievals, polite filler, stale assumptions. Elefante wins by injecting only the tokens with the highest decision-value at the moment of action.

**The product is one sentence:** *Elefante gives each task the smallest governed
set of durable context that measurably improves accepted value per total token.*

User-facing definition: *"Elefante is a persistent second brain for AI agents."*

### §1.1 The Four Laws (non-negotiable)

1. **Continuity** — Relevant durable context can carry across sessions; a new task is not forced to inherit unrelated history.
2. **Compliance** — Search before a memory write so existing knowledge is reused or amended instead of duplicated.
3. **Grounding** — Project-specific claims require current memory or workspace evidence; otherwise they are UNKNOWN.
4. **Task Intelligence** — Retrieved context must improve accepted task value
   per total token. A failed task has zero value, however cheaply it fails.

Laws 1–3 protect continuity and truth; Law 4 defines the product outcome.

### §1.2 Non-Goals (anti-divagation anchor)

Elefante is **not**:

1. A generic AI platform (no model hosting, no agent runtime, no orchestration framework).
2. A chat product (never owns the conversation surface).
3. A SaaS memory store (local-first is a law, not a phase).
4. An observability product first (debugging dashboards support Task Intelligence; they are not the thesis).
5. A feature-count race (task improvement must be measured, not inferred from feature count).
6. A prompting framework.

The released product boundary is summarized in
[`docs/explanation/vision.md`](../docs/explanation/vision.md). Development ideas
and status remain in this workspace.

### §1.3 Product contract — universal local memory authority

**Target customer:** an AI-native developer or technical founder who actively uses more than one agent host and needs continuity without surrendering private development context.

Elefante competes as the local memory authority beneath the tools users already choose — Claude, Codex, Gemini, Grok, Agent Zero, OpenClaw, IDE extensions, and future MCP-capable hosts. It must not become an editor plugin collection or a new agent runtime.

The non-negotiable product shape is:

1. One local owner for storage, migrations, locks, and provenance.
2. Native local HTTP for capable clients; a supported compatibility bridge for stdio-only clients.
3. An install/uninstall/upgrade contract per host, with an explicit compatibility tier: **certified**, **compatible**, or **community**.
4. No public-by-default data surface; local memory and graph data remain loopback-bound unless the user explicitly hardens a trusted deployment.

### §1.4 Product trust gates — claims require current proof

| Gate | Required proof | Current state (2026-08-26) |
|------|----------------|-----------------------------|
| Privacy boundary | Dashboard and local APIs bind loopback by default; no wildcard CORS; documented proxy/auth responsibility | Guarded locally; dashboard and daemon boundary tests pass |
| Write authority | Retrieval surfaces cannot mutate memory/graph state; writes use explicit, observable tools | Guarded locally; GraphQuery mutation regressions pass |
| Data integrity | One-writer daemon, Source provenance, migration + rollback proof | Runtime and isolated recovery proofs pass. Legacy-store migrations remain stopped, backup-gated support operations and are not a fresh-install requirement. |
| Quality | Full suite collects cleanly; targeted regressions and frontend build are green in CI | Published v2.12.3 merge proof is green: 327 tests passed, 5 skipped, and 1 slow test deselected; the isolated slow two-bridge proof and all customer-candidate/platform build lanes passed. |
| Compatibility | Every advertised host has a tested install, reconnect, concurrent-use, upgrade, and uninstall path | In progress — Claude Code, Codex, Gemini CLI, OpenClaw, VS Code, Cursor, and Kiro bridge emission and safe uninstall are tested. An isolated native Codex CLI round trip proves configure, upgrade, user-replacement preservation, and installer-owned removal without touching real user configuration; a separate slow runtime proof runs two real bridge processes concurrently through one daemon with distinct Codex/Claude provenance. Agent Zero is a documented community path; actual host-driven reconnect and certification remain unproven. |
| Supply chain | Runtime dependency contract is exact; high-severity production dependency findings are resolved or release-blocked | The production lock no longer contains ChromaDB. The strict hash-locked audit reports no known vulnerabilities, closing stale GAP-029. Release archives now require a verified `SHA256SUMS` manifest. |

---

## §2 Released Product: v2.12.3 Memory Intelligence

### §2.1 Outcome

**Make persistent memory legible as a decision advantage, not a database inventory.**

The dashboard must answer one product question in plain language:
what durable knowledge should shape the next agent answer, and why should a
developer trust it? The implementation remains inside the released local trust boundary:
loopback-only, redacted snapshot-only, and read-only.

### §2.2 Included in the v2.12 release

| Surface | Evidence |
|---------|----------|
| Product story | Briefing identifies a current durable memory and explains its evolution as assumption → evidence → decision → guard when graph relationships support it |
| Visual system | Exact repository emblem; carbon/tusk base with copper, brass, clay, and sage semantic states; no generic purple/cyan AI-gradient treatment |
| Data truth | Production `from`/`to` edges and legacy `source`/`target` fixtures normalize at the frontend boundary; backend label derives from configured store |
| Showcase | Deterministic 37-memory, 11-entity, 95-edge snapshot; every memory cites repository evidence; synthetic behavior is disclosed; user data is absent |
| Trust boundary | Dashboard remains loopback-only, redacted snapshot-only, read-only, and is not exposed as a public service |
| Documentation | Snapshot reference, operator guide, script catalog, README, changelog, and this SDD/state record are synchronized |
| Installer | Host-aware selection, platform-specific launchers, and non-mutating dry-run behavior |

### §2.3 Current release state

| Work | Current proof |
|------|---------------|
| Visual acceptance | The source-grounded dashboard showcase and canonical branding are complete. The website received desktop/mobile dark/light, reduced-motion, and Matrix-state browser evidence before production deployment. |
| Regression proof | v2.12.3 is the published release. PR #26 passed 327 automated tests with 5 skips and one isolated slow proof deselected; the slow proof, dashboard, dependency audit, clean-customer candidate, and macOS/Windows/Linux build lanes passed. |
| Durable handoff | GitHub release v2.12.3 points to merge commit `5a6bb1b`; all three customer installers were independently re-downloaded and verified against the published `SHA256SUMS`. |
| Publication | **PUBLISHED 2026-08-26 UTC** — v2.12.3 and its macOS, Windows, and Linux customer installers are public. The tag and checksums provide reproducible identity; the GitHub release object is mutable and must not be described as immutable. |

### §2.4 Approval gates

The v2.12.3 publication is complete. The following production operations remain
intentionally controlled:

1. Apply provenance or vector-store migrations to live user data.
2. Tag or publish another release, deploy changes, spend money, or
   contact third parties.

### §2.5 Scope guard

- No cloud memory service, model hosting, editor replacement, or agent runtime.
- No compatibility or security claim without automated or host-driven proof.
- No browser-triggered snapshot generation, live-store query, or public host bind.
- No fabricated five-signal per-query breakdown: the snapshot does not carry it.
- No user data in the maintained showcase and no visual alteration of the canonical logo shape.

Rejected alternatives remain closed without new evidence:

| ID | Rejected alternative | Reason |
|----|----------------------|--------|
| X1 | Three-tool facade | Lossy routing, duplicate maintenance, hidden Compliance Gate actions, and domain conflation |
| X2 | Lite/standard/full storage modes | Silent embedding/store divergence would corrupt retrieval comparability |
| X3 | User-tunable scoring profiles | Breaks reproducibility of the empirically guarded scoring contract |
| X4 | Agent-supplied write confidence | Semantics are undefined and invite fabricated precision |
| X5 | Strict/suggest/automatic write modes | Multiplies failure surfaces around a deliberately binary compliance gate |
| X6 | Hermes-specific profile | No evidence justifies client-specific memory semantics |

### §2.6 Resume verdict

- **RESUME_SAFE:** YES — active state is here; defects/capability gaps are in [`workspace/ISSUES.md`](../workspace/ISSUES.md); integration truth is in [`agents/manifests/ide-integration.yaml`](../agents/manifests/ide-integration.yaml).
- **PUBLISHED_PRODUCT:** v2.12.3 is live.
- **PUBLICATION_STATUS:** Published, tagged, and checksum-verified. The GitHub release object is not immutable.
- **LIVE_RUNTIME:** Installation or upgrade of a user's local runtime remains a separate operator action; repository publication does not mutate it.
- **UNRELEASED:** Task Intelligence, governed Recall hardening, and full build-provenance behavior remain development work; no future version or publication is assigned.
- **PUBLICATION_AUTHORITY:** no unused authorization. Any later tag, release, deployment, or runtime replacement requires fresh explicit approval.

---

## §3 Roadmap (multi-release)

### §3.1 v2.11.1 — Shipped baseline

The daemon, storage-free bridge, provenance, installer ownership, SQLite default,
and snapshot-only dashboard form the baseline described in `CHANGELOG.md`.
Unfinished trust obligations remain visible in §1.4 and `workspace/ISSUES.md`;
the dashboard work does not waive them.

### §3.2 v2.12.0 — Released

- Memory Intelligence Briefing and source-grounded showcase
- Decision Graph built from explicit memory relationships
- Exact canonical dashboard branding
- Host-aware installer selection
- Platform-specific launchers and non-mutating dry-run behavior
- SQLite-vector/Kuzu default architecture with a clean production lock

### §3.3 v2.12.2 — Released customer package

- Customer-only macOS, Windows, and Linux archives
- Separate hash-locked runtime dependency set; no test, lint, or build tooling
- Standard-library-only installer bootstrap until the client dependency lock is installed
- Explicit archive allowlist plus verifier that rejects developer material
- Fresh macOS install, health, daemon, MCP handshake, and uninstall proof
- Published checksums for independent artifact verification

### §3.4 v2.12.3 — Released patch

- Customer-repair adoption accepts only structurally verified older Elefante registrations and preserves foreign same-name servers
- Release and capability entrypoints synchronized with shipped behavior
- Release-candidate identity derived from the package manifest rather than a previous-version literal
- macOS, Windows, and Linux installers independently checksum-verified after publication

### §3.5 Priority order after v2.12.3

This order is customer-value weighted. Benchmark mechanics and randomization are
verification methods, not product priorities.

| Priority | Customer outcome | Current state | Exit gate |
|----------|------------------|---------------|-----------|
| **P0 — Improve one real memory-dependent task** | The governed memory bundle increases accepted task value per total token against the source-only path | A real fresh-session decision question now has a bounded local signal: the pre-existing canonical mission produced 3/3 accepted answers while the no-memory control returned `UNKNOWN` in 0/3. Model-free controls select only the mission on its paraphrase and abstain on the unrelated GitHub issue screen. On that same mission question, selective Recall and full-store injection both produced an accepted answer, but selective Recall used 14,912 total tokens versus 15,420 for all six records. This remains one task and not representative product proof. | Reproduce on a second independently arising task with a different pre-existing decision-changing memory, then use the maintained evaluator before any promotion claim. |
| **P1 — Generalize without losing trust** | Benefit repeats across independent task classes without privacy, authority, scope, contradiction, token, or latency failure | No one-task result establishes representative benefit | Repeat on an independent task, then use a fresh powered design only if both local signals survive |
| **P2 — Ship a recoverable customer capability** | Supported hosts receive the proven behavior with clear diagnostics and rollback | BUG-052 provenance is guarded in development. Exact candidate `b05d794` passed a fresh hosted-macOS install, health check, uninstall, portable checksum verification, and independent manifest/payload source-identity verification. Published v2.12.3 and the current local install do not include that unreleased development contract; later behavior remains unreleased. | Replace the legacy local runtime only under explicit install authority, then require separate merge/release authority. |

### §3.6 Upcoming (no release or date commitment)

- Expanded `elefante doctor` verification
- Automated integration-manifest drift checks
- Additional host certification and adapters
- Signed and notarized native packaging
- Proactive memory surfacing and conflict detection
- Usage intelligence
- Portable import and team synchronization

### §3.6 What does NOT justify v3.0.0

This plan stays on v2.x deliberately. v3.0.0 only justified by:

- A user-facing memory-contract break (`elefante-Memory` action arguments or result-shape rewrite). **Not planned.**
- A data-model change that cannot be migrated in place. **Not planned.**
- Removal of a supported transport without a documented compatibility path. **Not planned.**

---

## §4 Features

### §4.1 Backlog (status: idea — not yet investigated)

This section is the source of truth for unshipped ideas. No item below carries
a release or date promise.

- **A. Memory Intelligence** — deterministic health labels exist, but a validated health score does not; Potential Conflict Detection (designed, not built); Smart Update / Merge (concept only)
- **B. Proactive Retrieval** — Proactive Memory Surfacing (`surfaces_when` field exists; surfacing logic not built); Retrieval Explanation UI (backend done v2.1; frontend 0%)
- **C. Dashboard & Visualization** — Usage Intelligence aggregation remains unbuilt; the v2.12 Memory Intelligence briefing and visual-system redesign are implemented
- **D. Session Distiller Expansion** — Live Mode (designed, not built); Team Sync API (concept)
- **E. Multi-Modal & Platform** — Multi-Modal Memory (concept); additional host certification (see §3.3); Agent Zero remains a documented community path
- **F. Distribution Packaging** — Branded macOS DMG (build script done; CI wired; signing credentials pending); Branded Windows EXE (not built); Manual Fallback Path (shipped — `install.sh`/`install.bat`)

### §4.2 In design (status: draft PRD)

Each row links to the full PRD. **Authority:** the linked file is the source of truth for the PRD body; this table indexes by status.

| Feature | PRD | Status |
|---------|-----|--------|
| Host integration surface (daemon, adapters, ownership schema) | [`workspace/proposals/ide-integration-surface.md`](../workspace/proposals/ide-integration-surface.md) | Shared runtime and verified detected-host coverage implemented; additional adapters and certification upcoming |
| Session intelligence (local token-financial usage signals) | [`workspace/proposals/session-intelligence.md`](../workspace/proposals/session-intelligence.md) | DRAFT — owner-directed token-financial companion thesis curated; Phase 0 purpose, consent, evidence, retention, deletion, and Signal Card contract must be accepted before implementation. It reuses semantic Memory for durable user meaning and Task Intelligence for outcome evidence; no duplicate usefulness system or public claim. |
| Task Intelligence (eligible task → failed-stage diagnosis → one causal repair → behavioral outcome) | [`workspace/proposals/retrieval-effectiveness.md`](../workspace/proposals/retrieval-effectiveness.md) | RECALL-FIRST DEVELOPMENT COMPLETE / CUSTOMER ACCEPTANCE PENDING — R0 through R4 and R6 development closure pass; R4 required no selector change. R5 was correctly not entered because no pre-existing decision-changing memory was supplied, so representative lift remains unproven. Installed v2.12.3 still lists 16 tools and no Recall despite its legacy doctor reporting ready. Replacement install, one clean Codex normal-question event, merge/version formation, promotion, and publication remain separately gated. |
| Memory identity | [`workspace/proposals/memory-identity.md`](../workspace/proposals/memory-identity.md) | DEFERRED DESIGN REFERENCE — no schema implementation unless Task Intelligence evidence first proves a state/scope failure and local benefit from resolution |

### §4.3 Released design record

#### Memory Intelligence dashboard SDD — accepted implementation

**Question:** How does the local dashboard sell Elefante's developer advantage
without generic AI styling, stale product claims, fabricated telemetry, or a
second path into private stores?

**Proof:** The repository establishes the product as a local Full Signal
Injection layer using five retrieval signals, an embedded SQLite default plus
Kuzu graph, a one-writer loopback daemon, source provenance, and a redacted
snapshot-only dashboard. Prior UI review found a generic gradient palette, an
inventory-first Overview, a deformed substitute elephant, stale Chroma-first
demo content, and frontend graph consumers that expected `source` / `target`
while production exports `from` / `to`.

**Result — visual contract:**

1. Preserve the Matrix-inspired binary atmosphere but subordinate it to content.
2. Use the canonical Elefante emblem exactly; no generative redraw, skew,
   silhouette substitution, or anatomical interpretation.
3. Base palette: carbon `#070604`, tusk `#eee4d3`, copper `#c8894d`;
   state accents: brass `#dfbb72`, clay `#c96f5d`, sage `#718d74`.
4. Prefer square, hairline, editorial panels and compact system typography over
   rounded gradient cards, glow effects, or ornamental icon grids.

**Result — information architecture:**

1. **Briefing:** lead with “The decisions shaping your next answer.” Select a
   durable current decision by type, lifecycle, live score, and access history.
2. If edges prove an evolution, show old assumption → evidence → decision →
   enforced guard. Otherwise label the cards honestly as current/related
   memories; never invent causality.
3. Show memory type, access count, normalized link count, lifecycle state, and
   repository/source grounding beside the thread.
4. **Memories:** retain snapshot-local search, sorting, details, and related
   navigation under the same visual system.
5. **Connections:** retain topics and score distribution. Replace the synthetic
   topic-ring graph with a Decision Graph derived only from real memory-to-memory
   edges. It presents readable assumption → evidence → decision → guard trails,
   names every relationship, and keeps semantic bridges visually secondary.
   Colors communicate memory role and lifecycle, not unsupported model
   performance.

**Result — data and trust contract:**

1. The browser reads only `dashboard_snapshot.json`; Reload re-reads it and
   cannot regenerate or mutate memory.
2. Edge endpoint aliases normalize once at the frontend type boundary.
3. Serialized `source` reflects the configured embedded backend.
4. The maintained showcase is deterministic and contains 37 repository-grounded
   memories, 11 topic/source entities, and 95 links. Its access history is
   synthetic, disclosed, and never represented as customer telemetry.
5. Per-query vector/concept/co-activation/authority/temporal values are not
   shown until the snapshot contract actually carries them.
6. Showcase graph relationships are explicit, source-grounded decision,
   safeguard, governance, provenance, and semantic links. Arbitrary sequential
   memory links and invented inter-topic topology are forbidden.

**Acceptance:** production build; snapshot validator; focused serializer,
boundary, edge, and showcase regressions; all three views rendered at a desktop
viewport; Decision Graph trails and relationship labels visually inspected;
exact emblem visually inspected; full Python/routing/emoji/diff checks green.

**Next:** keep dashboard claims tied to released behavior. Task Intelligence
remains development-only until a valid multi-task evaluation demonstrates
outcome lift; website production state must be verified separately before any
public claim is changed.

### §4.4 Shipped (status: shipped — link to reference)

| Feature | Shipped in | Reference |
|---------|------------|-----------|
| Token Intelligence Layer (per-call TOKEN_STATS, type budgets, density warnings) | v2.5.0 | [`docs/reference/token-intelligence.md`](../docs/reference/token-intelligence.md) |
| 5-signal scoring (vector / concept / co-activation / authority / temporal) | v2.7.0 (post BUG-016/017/018) | [`docs/reference/scoring.md`](../docs/reference/scoring.md) |
| 16 MCP tools + 2 prompts | v2.10.0+ | [`docs/reference/tools.md`](../docs/reference/tools.md) |
| Compliance Gate (search before write) | v2.0.0+ | [`docs/reference/architecture.md`](../docs/reference/architecture.md) §Compliance Gate |
| Memory Intelligence dashboard with live-computed scores | v2.12.0 | [`docs/reference/dashboard-snapshot.md`](../docs/reference/dashboard-snapshot.md) |
| Customer-global installer and runtime-only platform archives | v2.12.2; current in v2.12.3 | [`docs/how-to/install.md`](../docs/how-to/install.md) |
| Transaction-scoped Kuzu locking | v1.1.0 | [`docs/reference/architecture.md`](../docs/reference/architecture.md) write path and trust boundary |

### §4.5 Rejected (status: rejected — do not re-litigate)

The active scope guard is §2.5. Historical rejected alternatives remain in the
v2.10.0 journal and changelog; reopen only with new user or retrieval evidence.

---

## §5 Optimization

### §5.1 Active blockers

- Task Intelligence has evaluation infrastructure but no demonstrated increase
  in accepted task value per total token across a representative multi-task
  corpus.
- No second independent causal lift is proven. A real release-candidate
  validation task arose naturally, but Task Intelligence correctly abstained:
  both pre-existing records were too generic to change that task. After the
  source-provenance defect was verified, one managed task-local invariant was
  captured for future work; it cannot be reused retroactively as lift evidence.
- Default Task Brief injection remains blocked until the evaluation proves benefit without unacceptable token cost or regressions.
- Governance and Task Intelligence lifecycle behavior are implemented only in
  unreleased development. The published v2.12.3 client remains unchanged.
- BUG-052 is fixed again in development. Exact candidate `b05d794` has agreeing
  archive, payload, installed runtime, and `doctor` provenance plus a portable
  checksum; the current installed runtime remains legacy because this machine
  was not silently upgraded.

### §5.2 Performance / efficiency improvements

| Area | Status | Reference |
|------|--------|-----------|
| Token-budget enforcement per memory type | SHIPPED v2.5.0 | [`docs/reference/token-intelligence.md`](../docs/reference/token-intelligence.md) |
| Co-activation persistence across restarts | Historical v2.7.0 foundation; current explicit-use boundary is unreleased development (BUG-046) | [`workspace/postmortems/ai-behavior.md`](postmortems/ai-behavior.md#issue-15) |
| Smoothed vector baseline (composite-score floor) | SHIPPED v2.7.0 | [`docs/reference/scoring.md`](../docs/reference/scoring.md) |
| Intent-gated specification override | SHIPPED v2.7.0 (BUG-017 fix) | [`workspace/postmortems/memory.md`](../workspace/postmortems/memory.md#issue-12) Issue #12 |
| Legacy Chroma query-with-filter workaround | SHIPPED v2.9.0 (BUG-022 fix; legacy backend only) | [`workspace/postmortems/memory.md`](../workspace/postmortems/memory.md#issue-14) Issue #14 |

### §5.3 Planned optimization work

- Run the exact sealed real-memory calibration pair only after deterministic
  preflight is green and with explicit cumulative token caps.
- Add independently reviewed real-memory tasks from different task classes;
  never reuse the consumed preliminary holdout for promotion.
- Measure black-box acceptance, retries, corrections, total input-plus-output
  token cost, latency, privacy, and failure stage independently; compare the
  combined accepted-value-per-total-token result only within frozen paired
  tasks.
- Keep the 17th development tool and pilot delivery default-off until a fresh
  representative holdout demonstrates net task improvement.

---

## §6 Ops Plans

### §6.1 Active operational concerns

| Concern | Status | Owner |
|---------|--------|-------|
| Live provenance backfill | Dry-run proven; apply intentionally not run | Explicit user authorization |
| Existing legacy Chroma-store transition | Isolated migration proof passes; no live legacy store was opened or changed | Explicit user authorization |
| Release formation | v2.12.3 is published; later development is Unreleased | Version audit, cohesive commits, fresh release authorization |

### §6.2 Operational improvements upcoming

- `elefante doctor` extended scope for full self-protocol coverage
- Host-driven certification runs for each advertised compatible adapter

### §6.3 Operational reference (already shipped)

- Backup: `scripts/lifecycle/backup_elefante_data.py`
- Restore: `scripts/lifecycle/restore_elefante_data.py`
- Restart: `scripts/lifecycle/restart_elefante.py`
- Factory reset (developer/privileged operation; not included in customer archives): `scripts/lifecycle/reset_factory.py`

Reference: [`docs/how-to/`](../docs/how-to/).

### §6.4 Hermes integration — historical evidence only

Hermes was tested as an MCP consumer on 2026-05-02, before Elefante's current
daemon, customer-global installer, and consolidated 16-tool surface. Those
commands, paths, provider settings, temporary verifiers, and runtime results are
historical evidence in §10 and Git history—not current setup guidance.

Current Hermes installation, provider configuration, compatibility, and runtime
health are **UNKNOWN** until reverified. Do not advertise or configure Hermes
from the 2026 snapshot. Current host claims come only from
`agents/manifests/ide-integration.yaml`; current MCP inventory comes from
`scripts/ci/list_mcp_tools.py`.

---

## §7 Dev Process Plans

### §7.1 Constitution + Documentation Skill (current)

- [`agents/orchestrator.md`](../agents/orchestrator.md) — single canonical developer constitution. Loop, Five Gates, Memory Janitor Mandate, Documentation Skill (Closed Surface Map, Forbidden Patterns, Pre-write checklist, New-File Test, Failure Conditions, Lifecycle), Embedding Rule, Modes, Compendium Trigger Map, DEVELOPER/RESEARCH Routing, Closure Sequence, Where Things Live, Specialist Handoffs, Critical Thinking, Changelog Contract, Never list. ~270 LOC. Merged from the deleted full constitution + previous loadable orchestrator on 2026-05-02 (Phase B of agentic restructure).
- [`agents/*.md`](../agents/) — 10 specialist protocols + glossary.

### §7.2 Active enforcement

- [`tests/test_developer_routing.py`](../tests/test_developer_routing.py) — BUG-007 routing drift, active-link, release-version, and BUG-026 forbidden-filename guards. Exact pass counts belong to the current verification run, not this plan.

### §7.3 Planned dev process improvements

- Active guard expansion: pre-edit hook requiring `BUG-NNN | new` classification declaration before any Edit/Write call ([`workspace/postmortems/ai-behavior.md`](../workspace/postmortems/ai-behavior.md) Issue #12 Candidate 2)
- Maintained verifier scanning recent transcripts for missing classifications ([`workspace/postmortems/ai-behavior.md`](../workspace/postmortems/ai-behavior.md) Issue #12 Candidate 3)
- Source-derivation tests: assert tool counts, schema field names, etc. derive from source not docs

---

## §8 UX Plans

### §8.1 Currently tracked UX concerns

- DMG installer customer surface — FIXED v2.9.0 (BUG-020); guarded by widget-tree check + manual screenshot
- Installer failure recovery routing — FIXED (BUG-019 / BUG-020 closure); persisted summary/status/log files surfaced in installer GUI
- Dashboard blank-on-first-launch — FIXED v2.8.x (BUG-003); readiness wait + forced restart on refresh + frontend retry/backoff

### §8.2 UX backlog

- Health indicators on graph nodes (idea)
- Rich tooltips on signal hubs (idea)
- Live mode for session distiller (idea)

### §8.3 Open UX decisions

- Add user documentation only when a released workflow needs it; keep developer
  plans and evidence out of `docs/`.

---

## §9 Meta-process

### §9.1 Documentation strategy

Source-of-truth: [`agents/orchestrator.md`](../agents/orchestrator.md) § Documentation Skill.

Closed Surface Map (where each event lives) — see Documentation Skill section in orchestrator. Summary:

| Event | Canonical home |
|-------|----------------|
| Vision | this file §1 |
| Active release state | this file §2 |
| Roadmap | this file §3 |
| Feature backlog/in-design/shipped | this file §4 |
| Optimization | this file §5 |
| Ops plans | this file §6 |
| Dev process plans | this file §7 |
| UX plans | this file §8 |
| Meta-process | this file §9 (and orchestrator Documentation Skill for the canonical rules) |
| Bug or GAP | [`workspace/ISSUES.md`](../workspace/ISSUES.md) |
| Bug post-mortem | `workspace/postmortems/<domain>.md` |
| Reusable lesson | [`workspace/lessons.md`](../workspace/lessons.md) |
| Architecture decision (ADR) | `workspace/decisions/ADR-NNNN-*.md` (when migrated) |
| Shipped contract reference | `docs/reference/<name>.md` |
| Operational procedure | `docs/how-to/<name>.md` |
| Agent executable protocol | [`agents/*.md`](../agents/) |
| IDE integration | [`agents/manifests/ide-integration.yaml`](../agents/manifests/ide-integration.yaml) |

### §9.2 BUG-026 status (passive-protocol failure mode, recurring)

**Current state:** MITIGATED (guarded) — 3x recurrences observed in single session 2026-05-02; active filename-pattern guard ships in `tests/test_developer_routing.py`; broader-surface active guard pending (Loop Step 1 skip, Gate 3 timing, side writes).

Detail: [`workspace/ISSUES.md`](../workspace/ISSUES.md) BUG-026 row + [`workspace/postmortems/ai-behavior.md`](../workspace/postmortems/ai-behavior.md) Issue #12.

### §9.3 Open meta-process decisions

- Whether to author broader BUG-026 active guard (candidates 2/3 in Issue #12 Solution)
- Whether to migrate `workspace/lessons.md` distilled rules into ADRs in `workspace/decisions/`
- Whether to fully consolidate `workspace/proposals/<name>.md` PRDs into this file's §4 (currently cross-referenced; bodies still in source files)

---

## §10 Journal — agentic development trace

**Documentation is a journal of agentic development. AI drafts, human curates. Hermes engages Elefante to surface memories that help us. We document, we measure, we apply learning.**

This section is the chronological record of curation events, decisions, and absorbed proposals. Not snapshot state (that lives §1–§9 above) — the development *trace*: what angle we worked, what changed, what we measured.

| Date | Event | Driver | Measurement |
|------|-------|--------|-------------|
| 2026-08-26 | **The surgical bridge recycle completed and stopped at the Codex host boundary.** One graceful `TERM` removed only stdio bridge PID `24229`, the eight-hour-old child of Codex app-server PID `22073`; the healthy daemon PID `55811`, durable data, installed runtime, host configuration, repositories, and remote surfaces were untouched. Codex did not spawn a replacement bridge, and the single post-change Recall event returned `Transport closed`. | The repaired candidate is healthy through its own doctor and a new direct bridge, but this task reproduced HTTP 404 through the bridge session created before installation. The bounded experiment tested whether recycling only the owned child could realize the documented client restart without quitting Codex; the negative result shows that process termination is not a supported substitute for the host's MCP Restart action. | Preflight at `2026-08-26T17:34:15-04:00` preserved installed v2.12.3 candidate source `8b7cc5b`, public `origin/main` `14fda301`, PR #25 open/draft/DIRTY at `d9aefb1e`, original dirty-tree fingerprint `cd285fad...8df`, and website source/live `d4e1f321` at v2.12.3. Post-attempt doctor still reports 17 tools, read-only `status=supplied`, and `customer_ready=true`; daemon health remains green. `codex mcp --help` exposes no restart command, and no managed app-server control socket exists. The only supported next action is Codex Settings → MCP servers → Elefante → Restart, followed by one normal-question Recall event. No second process attempt, outcome trial, lift claim, memory mutation, daemon/app restart, configuration rewrite, push, PR update, merge, release, or deployment occurred. |
| 2026-08-26 | **The provenance-bound Recall candidate was installed locally; runtime proof is green and Codex reattachment remains open.** The installer stopped the owned daemon, preserved a fresh checksum-verified data backup and the complete prior runtime, installed the exact clean candidate at the stable customer path, refreshed the installer-owned hosts, and restarted the loopback daemon. The candidate fixes the false-ready doctor by making live Recall capability part of customer readiness. | The owner rejected HTTP-404 Recall as an acceptable stopping state. The smallest trustworthy repair was the already verified customer archive, not a hand-patched installed file. | Installed identity: v2.12.3, candidate, clean source `8b7cc5ba43b33b8c62cc80412359227ad8d2e9d9`. Doctor and an independent direct bridge report 17 tools, read-only Recall annotations, `status=supplied`, and `customer_ready=true`. Backup: `/Users/jay/.elefante/backups/elefante_data_backup_20260826_210611.zip`, SHA-256 `18f44bb0822677cd06501e06f95f09470378f73def98ad37d90041cd90bf8826`; prior runtime: `/Users/jay/.elefante/app/current.backup.20260826_170620`. Acceptance is not closed: this already-open Codex task still uses its pre-upgrade MCP session and returns HTTP 404; the fresh ephemeral Codex run initialized a new bridge but hung before any model/tool event and was terminated after the bound. Official client MCP Restart plus one normal-question proof remains required. No memory deletion, restore, migration, push, PR update, merge, release, website change, or deployment occurred. |
| 2026-08-26 | **PR #25 development reconciled locally with v2.12.3 and formed as a provenance-bound candidate.** The now-DIRTY remote PR was not rewritten. Instead, current `origin/main` and the exact PR head were merged in an isolated worktree, the preserved 49-path development package was reconciled by source authority, duplicate/stale documentation claims were guarded, Session Intelligence was committed separately, and the governed Recall candidate was committed locally. | The owner authorized surgical implementation but required stop-on-drift, Recall-first value, token-financial discipline, documentation before development, and no acceptance claim without real proof. | Local commits: merge `46f5ef8`, Session Intelligence `8adc74f`, implementation `8b7cc5b`. Affected lane: 263 passed, one deselected. Full fast collection: 500 passed, four explicit legacy-backend skips, one slow deselection; the slow bridge test passed separately. Self-protocol: 48/48 in disposable HOME/data. Dashboard build and both npm audits pass with zero vulnerabilities; version, release, YAML, compilation, benchmark, and diff gates pass. The exact clean macOS candidate is `dist/elefante-installer-macOS-8b7cc5b.zip`, SHA-256 `2a8ca1cce8598d5dd4e72e4e3ba95455115a0eebffa42af9c06e5263a9da8041`; a second build was byte-identical. At that pre-install closure, installed acceptance remained negative because legacy doctor readiness disagreed with the real HTTP-404 Recall event. No eligible pre-existing memory existed, so no outcome trial or lift claim was fabricated. No push, PR update, installation, host change, durable-memory mutation, remote merge, release, or deployment occurred. |
| 2026-08-26 | **Elefante's role in the goal-directed agent loop made explicit.** Released-product explanation now locates Elefante at durable context retrieval during Perceive and verified outcome storage during Update while leaving goals, planning, tools, reflection, stopping, and consequential approvals with the agent. Financial advisory is documented as an architectural example rather than a shipped advisory capability. | Cross-repository positioning needed one precise boundary before the product and marketing surfaces could remain coherent. | README and vision use the same loop and exclusions; an active routing regression guards the product boundary and prohibits preserving hidden chain-of-thought as memory. No runtime, MCP surface, release artifact, dashboard, or user data changed. |
| 2026-08-26 | **The token-financial companion thesis was curated before implementation.** The existing Session Intelligence PRD now owns local usage facts and Signal Cards; governed semantic Memory owns durable user goals and constraints; Task Intelligence and `retrieval-effectiveness.md` remain the only authorities for accepted-value and causal outcome evidence. The draft adds an explicit user grooming loop, actual-versus-estimated evidence classes, typed provenance, versioned rate provenance, anti-overfit and anti-surveillance rules, a Canadian/EU privacy and consent gate, user access/deletion/export controls, and Phase 0 acceptance before real event persistence. | The owner identified the measured Recall response reductions as the shape of a larger local second-brain opportunity: understand a user's AI economics and return adoption or training signals, while explicitly asking not to overfit the three examples. | No runtime, event store, provider-usage ingest, website claim, release, or deployment changed. The exact Recall benchmark remains canonical in `retrieval-effectiveness.md §15.1`. A live search-before-write found no equivalent token-financial-companion memory; user-directed insight `bff45c38-0e60-4492-9c01-1b1bdacb1788` was stored and then amended in place after the grooming contract was finalized. A future grooming/location search retrieved it at rank 1 and confirmed both the loop and canonical path. At that documentation checkpoint, the installed v2.12.3 surface still had 16 tools and no Recall, so governed Recall delivery remained unverified. |
| 2026-08-25 | **v2.12.3 published and independently verified.** PR #26 merged to `main`; the protected release workflow created annotated tag `v2.12.3`, published the GitHub release, and attached the three customer installers plus `SHA256SUMS`. | Complete the owner-authorized surgical patch through the repository control plane and close the active release state with public evidence. | PR gates passed; the publication workflow passed; all three downloaded installers matched the published checksum manifest. Active release surfaces now identify v2.12.3 while historical v2.12.2 records remain unchanged. |
| 2026-08-25 | **v2.12.3 publication authorized on PR #26.** The audited release marker permits the main-branch workflow to create the exact annotated tag and dispatch the multi-platform release only after merge. | Owner explicitly authorized the surgical v2.12.3 patch publication; direct manual tagging would bypass the repository control plane. | Release-authorization, client-bundle, pipeline, routing, version-sync, and release-note tests pass locally. The marker has no effect before merge; all PR checks remain mandatory. |
| 2026-08-25 | **BUG-052 candidate-version recurrence fixed and guarded.** The client builder/verifier derive candidate identity from the manifest version; the standard-library builder exposes dependency-free version discovery; Quality and standalone client-candidate workflows carry that value through archive and installation checks. | PR #26 correctly bumped the package to v2.12.3, but candidate metadata and two CI lanes still encoded v2.12.2. The first repair then imported dependency-backed `src` before runner setup, recurring BUG-042. | Focused client-bundle and workflow regressions pass, dependency-free version discovery runs under `python -S`, and both edited workflows parse as valid YAML. GitHub rerun remained the publication gate. |
| 2026-08-25 | **v2.12.3 patch candidate prepared.** The candidate contains the guarded BUG-040 customer-repair hardening and BUG-007 release/capability truth corrections already accumulated after v2.12.2. Task Intelligence remains internal shadow evaluation infrastructure and is not promoted as a public capability. | Owner authorized the surgical resolution after the post-v2.12.2 audit: publish the verified fixes without expanding product scope. | The repository advisor classified the release as PATCH; `bump_version.py` updated the six version-bearing declarations to 2.12.3 and `--check` reported full agreement. The maintained Python suite and isolated slow bridge proof passed; release-note validation, scoped Ruff, diff hygiene, dashboard production build, and npm audit also passed. Publication later completed as v2.12.3. |
| 2026-08-25 | **BUG-007 release-contract truth-drift recurrence fixed and guarded.** Active entrypoints identify the published product; scoring documentation is derived from the shipped vitality and five-signal retrieval implementations; `surfaces_when` is explicitly stored non-ranking metadata; dashboard search is labeled snapshot-only; Distiller examples use the executable repository-root module path; the vulnerable transitive dashboard development dependency is updated. The superseded scoring page is preserved verbatim before distillation. | A whole-product audit found that passing tests froze stale release and capability claims instead of checking the actual published tag and execution paths. | 332 automated tests passed with one isolated slow proof deselected; the slow two-bridge proof passed separately; self-protocol passed 46/46; dashboard production build and full/production npm audits passed with zero vulnerabilities. Rendered localhost acceptance showed `3 snapshot results for "daemon"`, no semantic-search claim, and zero browser console errors. No user data, live runtime, GitHub release, remote branch, or deployment changed. |
| 2026-08-15 | **BUG-045 short-query recurrence repaired using Elefante's own Recall output.** The independently requested task `use Elefante to improve Elefante` caused live Recall to supply generic Developer Etiquette. Replaying that record through the current development selector showed that the repeated product name was its only distinct lexical match, yet the candidate became both a direct answer and an actionable constraint. The shared v2 selector now requires two distinct text matches for multi-term questions while preserving one-term factual answers and explicit governing or structural paths. | Project identity identifies the subject, not the task-specific evidence needed to answer or act. One high semantic score plus a repeated name could still bypass the earlier long-query BUG-045 guard and spend context on generic process text. | The regression failed first with `direct_answer=1.0`, one of three distinct query terms matched, and the memory selected. After the repair, all 34 Task Brief compiler tests and 14 Recall/runtime answer-context tests pass. The installed runtime, live memory store, version, branch history, merge state, release, and deployment were not changed. |
| 2026-08-14 | **Task acquisition became an active product loop instead of idle benchmark waiting.** A naturally arising exact-candidate validation task entered Task Intelligence before completion. The pilot omitted both generic pre-existing records and returned a 21-token abstention, so the task proceeded from repository and artifact evidence. After the durable-source defect was fixed and verified, one managed Elefante-scoped release invariant was captured, search-first, as memory `726655b2-4941-4602-a1ba-bdbb9ed66eae`; Recall supplied it for a matching future question. A model-free lifecycle check then delivered only that record, declared its use, and recorded a test-accepted outcome without changing ranking. | The prior wording incorrectly treated the lack of a benchmark task as a reason to stop working. Product work must continue; Elefante should abstain when memory is not discriminative, then retain only verified reusable task evidence for later independent use. | Initial trace `bc145b3c-87dd-48fe-a35a-71589483e113`: 0 delivered, 2 omitted, 21 estimated tokens. Delivery/outcome trace `61f1e713-5776-4bf1-a43b-3f9deecc7502`: 1/1 memory delivered and declared used, 217 estimated tokens, test-accepted outcome, zero ranking mutation. This proves the acquisition/delivery/ledger path, not causal lift: the memory was captured after the source task and the delivery check had no source-only control. |
| 2026-08-14 | **BUG-052 candidate provenance recurrence repaired before installation.** The first newly downloaded green macOS candidate embedded GitHub's temporary pull-request merge SHA instead of the durable reviewed branch SHA; its checksum also named `dist/...`, which failed after artifact download flattened the directory. Installation stopped before changing the live runtime. Both downloadable candidate workflows now check out the PR head SHA (or `github.sha` outside PRs), and the dedicated candidate emits a portable checksum manifest. | Runtime identity is useful only when the recorded commit is durable and reproducible. GitHub's default PR checkout made the archive internally consistent but not a trustworthy exact-head customer candidate. | A failing workflow regression reproduced the missing durable-source contract, then passed after the repair. Local gates: 20 release-pipeline, 114 installer/release-focused, and 36 routing tests; workflow YAML and whitespace pass. Exact head `b05d794` then passed all seven required GitHub checks. The downloaded artifact's checksum verifies, both identity files report full SHA `b05d794078c7121c6da009d7fe6e0ded322b721f`, the Finder launcher is executable, the local dry run is non-mutating, and the hosted macOS job completed a fresh install, health check, and uninstall. The legacy live runtime was not replaced; no merge, version, release, or deployment changed. |
| 2026-08-14 | **Selective Recall beat full-store injection on the same accepted mission answer, and a second future-task memory was captured without claiming lift.** One isolated Sol Max run received the one governed mission record; the paired arm received all six live records with lifecycle metadata. Two preliminary screens were discarded rather than repaired post hoc: one exposed the expected answer in its response choices, and one judge confused `controlled` with a no-memory `control`. | Full-store injection is a real competing policy, not a harmless superset: it spends tokens on test, stale, and contradictory records. The live inventory also proved that no second eligible decision memory existed, so more selector tuning could not create representative evidence. | Final frozen A/B: both arms returned the exact accepted criterion, selective Recall used 14,912 total tokens, and full-store injection used 15,420; selective saved 508 tokens (3.3% of the full arm) with no value loss. The read-only search found only the canonical mission eligible. The user's previously explicit evidence/critical-thinking/token-discipline protocol was then stored separately as protected ranked memory `6550d201-75a9-4de6-a7b4-bdb864836920`; fresh Recall supplied only it at score 0.976. Because capture followed the diagnostic, it is eligible only for a later independently arising task. Rollback is recoverable archive of that ID. No source behavior, installed runtime, version, merge, release, or deployment changed. |
| 2026-08-14 | **A real decision-continuity task produced the first bounded correctness signal, and its positive control corrected an overfit selector repair.** The negative screen found Recall injecting unrelated process constraints. The first lexical guard removed that noise but also rejected the user-locked canonical mission when the user paraphrased it. The final selector keeps the lexical guard for ordinary role labels and separately recognizes a semantically strong, user-locked, scoped directive on a decision question. Capture guidance now says to use ranked delivery when paraphrases should work and never choose literal-triggered policy merely to pass one verification question. | The live mission had existed before the new fresh-session question, ranked first, and contained the governing decision absent from the clean control. It was nevertheless blocked by literal-only capture metadata and then by the first overfit lexical repair. This was the earliest causal failure; more architecture was not required. | The user-owned mission record was changed reversibly from `triggered` to `ranked`. The development selector run against the real live store selects only `product-north-star` for the paraphrased decision and abstains on the unrelated issue-2 question. In a seeded three-pair Sol Max component screen, treatment passed 3/3 and control answered `UNKNOWN` 0/3; 452 additional total tokens changed accepted value from zero to three. Exact-tree gates pass: 473 fast tests with 4 skips and 1 slow deselection, the isolated slow bridge test, 48/48 self-protocol checks, scoped Ruff, and whitespace. This is a one-task local signal, not representative lift or release authority. Rollback for the live record is `injection_policy=triggered` with its existing triggers. |
| 2026-08-14 | **BUG-045 answer-selection recurrence repaired from a live real-task screen.** Recall was asked whether to implement the three actual open GitHub product issues. It supplied unrelated SDD/developer-etiquette constraints each time instead of abstaining. | One selected memory matched only 3 of 28 task terms (10.7%) and passed solely because it was classified as a constraint. This was a concrete harmful-context and token-cost blocker, not missing architecture. | The exact issue-2 false positive now abstains model-free and removes 167 irrelevant context tokens (188 → 21). The first diagnostic answer pair preserved acceptance but did not improve total-token value (14,770 repaired versus 14,761 noisy), so it was stopped and not relabelled as lift. |
| 2026-08-14 | **BUG-052 runtime provenance closed in development without mutating the live installation.** Customer archives now bind their publication metadata to an internal payload identity; bootstrap and delegated install reject disagreement before recording schema-v3 runtime identity; `doctor` compares the installed version, source commit, cleanliness, and release channel with the payload. Development bundles identify themselves as `development`. | The live runtime executed unreleased Recall code while reporting the same `2.12.2` semantic version as the published release. Version-only evidence could not distinguish stable, candidate, or developer code and therefore could not support a trustworthy task-outcome or release claim. | Focused installer/release tests cover legacy and malformed identity, archive/payload drift, delegated-install drift, upgrade, repair, known-good reinstall, and exact-SHA workflow assertions. No live install, memory data, version, merge, release, or deployment changed. |
| 2026-08-14 | **GAP-055 aligned Task Intelligence with accepted task value per total token.** The paired report now counts input plus output tokens, reports accepted outcomes per million total tokens, gives rejected work zero value, blocks acceptance regression, and admits token intelligence as an effectiveness path only when the task-clustered 95% lower bound is positive. Fair comparison uses complete pairs while observed spend includes every completed run. The user-directed canonical objective was amended in place in memory `0b27fa62-d459-4029-a390-391305ab555d`; a fresh Recall supplied the corrected objective. | The prior evaluator separated correctness/retries from an input-only cost ceiling. It omitted output cost and could neither express the governing objective nor distinguish accepted work made cheaper from cheap failure. The first replay also hid an unpaired early-stop treatment from pair totals. | Four new tests plus strengthened early-stop accounting pass. Exact-tree proof: 90 Task Intelligence tests and 36 routing tests pass; the 32-task manifest reports zero errors and remains diagnostic-only; the full fast suite passes 462 tests with 4 skips and 1 slow deselection; the isolated slow two-client gate passes. Task 032 remains `STOP`, and its five completed runs now report the exact 1,501,308 observed input-plus-output tokens. Scoped Ruff and whitespace checks pass. Historical outcomes were not relabelled, no model run occurred, and no merge, version, release, or deployment changed. |
| 2026-08-13 | **GAP-054 explicit durable capture and delivery gate passed model-free.** The reversible global Codex block and customer guidance now distinguish explicit user-directed capture from ordinary conversation, require exact scope and literal triggers, and verify one likely future question after a write. | Recall cannot improve a later task when the host never captures the decision; a successful write also does not prove governance will deliver it. | Initial full-question Recall returned `no_match` against five unsuitable records. Canonical mission memory `0b27fa62-d459-4029-a390-391305ab555d` was stored. Raw retrieval ranked it first, but Recall initially selected an unrelated specification because the mission used prose as exact scope. Correcting scope to `elefante` made Recall supply only the mission. The 178-test affected set, 458-test fast suite (4 skips, 1 slow deselected), isolated slow two-client proof, scoped Ruff, compilation, and whitespace checks pass. No model run, ranking change, task-lift claim, merge, release, or deployment occurred. |
| 2026-08-13 | **Task 032 completed with a local `STOP`; GAP-053 opened.** The evaluator now preserves fixture source governance, separates reviewed evaluation metadata, compares identical source-only and memory Briefs, binds the real Recall MCP surface in its black-box judge, and automatically prevents redundant model calls after treatment 0/3 makes the decision irreversible. | The initial preflight exposed evaluator-created trigger/lock metadata. After that repair, the intended memory selected and delivered correctly, but all measured patches still missed the same task-local API behavior. | Base failed and known good passed. Memory treatment: 0/3 accepted with intended memory delivered 3/3. Source-only control: 0/2. A third control attempt was terminated before a measurable outcome; exact partial usage is `UNKNOWN`, and a subsequent automatic replay started zero model calls. All five completed patches passed routing, instruction-preservation, and uninstall assertions, then failed because `tools/list` lacked `elefante-Recall`. Recorded completed outcomes used 1,417,856 input tokens, 1,112,064 cached, 305,792 uncached, and 83,452 output. No product code, live memory, version, merge, release, or deployment changed. |
| 2026-08-13 | **Task Intelligence reduced to one evidence-led implementation experiment.** The North Star remains better accepted task outcomes from the smallest safe durable-memory bundle. The next task is selected and diagnosed model-free before code; the first failed causal stage chooses one repair; Memory Identity and scoped state resolution are conditional rather than presumed; the model ceiling is three frozen pairs with explicit local go/stop/inconclusive rules. | The prior PRD still assigned architecture before evidence. Preserved results show retrieval, selection, and delivery can complete while acceptance fails and agent use remains unknown, so state identity is not yet an established root cause. | Documentation-only. The canonical PRD fell from 735 lines to a bounded experiment; no source behavior, schema, live store, installed runtime, benchmark outcome, version, merge, release, or deployment changed. Immediate gate: select one new eligible memory-dependent task and identify its first failed stage without a model run. |
| 2026-08-09 | **BUG-050 closed the last known Task Intelligence runtime-infrastructure bypass.** Normal search context, the context prompt, explicit Task Briefs, and opt-in tool-response delivery now deep-copy and current-source-check candidates before the same governed compiler runs. | Current-tree adversarial audit reproduced a digest-stale locked memory that the explicit Task Brief blocked but other delivery paths injected. | Independent replay passed all four delivery paths and confirmed no store mutation. Final exact-tree proof: 435 fast tests passed (4 skipped, 1 slow deselected), the isolated slow proof passed, the live MCP lifecycle passed 47/47, eight canaries remained base-fail/fix-pass, model-free sealed preflight remained deterministic at 1,252/1,500 tokens with zero model calls, all three client archives and checksums verified, dashboard build/audit passed, and promotion correctly stayed blocked. Causal effectiveness remains a separate open gate. |
| 2026-08-09 | **BUG-049 closed evaluator truth-loss paths and produced one valid real-memory functional signal.** V2 source selection now preserves diverse ownership files, declared context chunks, and later validation evidence under the hard budget; test artifacts are safeguards. Failed workspaces are retained by default, schema-v3 filenames bind the complete task contract, and preflight names selected sources. | The first real-memory pair failed without causal clarity. A later treatment changed the correct public surface but one hidden `~/.bob` judge convention—not disclosed by the frozen source or task—turned it into a false failure. | Final model-free Brief: deterministic, 1,252/1,500 tokens, exact durable memory plus host registry, doctor, manifest, and safeguard. Eight canaries still base-fail/known-fix-pass. The preserved treatment patch passes the corrected judge without another model call. This is one-task diagnostic evidence; 23 historical tasks remain invalid, no paired multi-task lift exists, V1 and all runtime flags remain off, and release promotion stays blocked. |
| 2026-08-08 | **BUG-047/048 production Task Intelligence loop implemented behind two rollback switches.** User/workflow authority is enforced at write, maintenance, and delete boundaries; archive is the default forgetting operation. A default-off 17th development MCP tool now prepares bounded context and records session-bound delivery, declared use, metadata-only outcome, inspection, and retraction without changing ranking. | The prior compiler/evaluator stopped at retrieval and could not prove which governed memory reached which task or outcome. Governance metadata also had no effective authority boundary. | Focused governance/ledger tests pass. The isolated live MCP self-protocol passes 47/47 with the opt-in surface and leaves the user's store untouched. Normal v2.12.2 discovery remains 16 tools; neither feature enablement nor pilot delivery is released or automatic. |
| 2026-08-08 | **First sealed real-memory golden-path preflight is deterministic and model-free.** A reviewed export of durable memory `f3482775-83b7-47b5-9cbb-d54da9d8bc73` is digest-bound to one independent doctor CLI black-box task. The store itself remains unchanged. | Earlier trials used generated snapshot context and invalid implementation-shaped judges; neither proved that a real durable memory could travel through the governed selector to a valid task. | Base ref fails and known-good ref passes. The exact durable memory is selected first; repeated Briefs are identical; rendered context is 968/1500 tokens; leakage scan is clean; `model_runs=0`. This proves the pipe, not causal lift. One capped paired calibration remains the next evidence gate. |
| 2026-08-08 | **BUG-045 selection gate hardened in development.** The existing `elefante-context` prompt and normal `elefante-Memory(action="search")` response now share one bounded answer selector. Broad retrieval remains available, while answer delivery excludes inactive, conflicting, secret-bearing, and inapplicable system-test memories; requires a question-specific action anchor plus independent semantic, concept, or graph corroboration; caps the complete rendered prompt at three memories and 450 tokens; avoids read reinforcement; exposes selection reasons; and abstains when nothing qualifies. | The first fix separated candidate discovery from answer delivery but still admitted one weak signal. The documented Task Intelligence contract requires corroboration before context is injected. The hard-cap regression then caught prompt labels pushing a long rendered prompt over budget. | 5 focused selector tests, all 22 fast MCP daemon tests, all 33 developer-routing tests, and all 46 isolated end-to-end checks pass; scoped lint and whitespace pass. This is unreleased development behavior, not measured product lift, automatic interception of every host question, or a website claim. |
| 2026-08-08 | **BUG-046 exposure/use boundary corrected in development.** Normal search and automatic context delivery are now read-only with respect to access history and co-activation. Legacy session IDs created by pre-fix retrieval exposure are discarded. The trace-bound `record_use` path writes a reversible declared-use event to a separate ledger and does not change access, co-activation, or ranking. | Retrieval frequency was being treated as memory usefulness, contaminating lifecycle ranking and any Task Intelligence evaluation. Search, delivery, declared use, and task outcome must remain separate signals. | Exposure/use, ledger, and MCP daemon regressions pass; no release, public performance claim, or automatic host interception is authorized. The use event is observational evidence, not causal task lift. |
| 2026-08-06 | **BUG-007 documentation drift recurrence was audited and guarded across the repository.** Active user docs, developer state, agent protocols, proposals, examples, and embedded MCP descriptions were reconciled with source and the published v2.12.2 assets. SQLite/Kuzu is the default; legacy Chroma migration is support-only; current MCP inventory is 16 tools and 2 prompts; context injection is conditional; scoring, vitality, lifecycle, and Task Intelligence limits are now stated without invented guarantees. Broken links, stale customer-candidate state, duplicate BUG-040 tracking, and obsolete commands were corrected. Historical journal evidence remains preserved and explicitly non-current. | Repeated stale documentation had become an operational defect: instructions could send developers to deleted files, tell customers the wrong release/storage model, and make unimplemented retrieval or forgetting behavior sound shipped. | Active-link audit reports zero unresolved links. Documentation/release/installer/reset/dashboard focus: 161 passed. Full fast suite: 373 passed, 4 legacy-backend skips, 1 slow test deselected. Dashboard production build passed and production audit found 0 vulnerabilities. Version sync, 16-tool/2-prompt inventory, Python compilation, YAML parsing, and whitespace checks passed. The full suite also exposed and fixed a manual-test import-path collision that shadowed the installed MCP package. |
| 2026-08-06 | **Memory governance was separated from Task Intelligence and documented as the continuation contract.** User-enforced retention and injection are no longer conflated with managed decay or ranked retrieval. Direct user operation is also separated from workflow-mediated operation: both share the local store, but user-directed actions retain user authority while an IDE/agent workflow receives only policy-bounded automation and explicit operation traces. The SDD now defines permanent, managed, and ephemeral retention; always, triggered, and ranked injection; reversible active/dormant/archived lifecycle; explicit user locks; and the rule that Task Intelligence optimizes task context only after governance is applied. A source audit records current scoring, reinforcement, filtering, provenance, and documentation gaps so the next developer does not normalize them as intended behaviour. | The owner clarified that Elefante stores memories under mixed authority: users can require retention or delivery, while healthy managed forgetting is necessary to prevent irrelevant history from overwhelming current work. The person explicitly using Elefante is not equivalent to an automated workflow using Elefante on that person's behalf. | Documentation-only. No schema, runtime, live store, MCP surface, benchmark outcome, release, or website claim changed. Nineteen focused scoring tests pass but do not cover governance, operating-mode authority, or usefulness. Next: freeze the two remaining policy decisions, write governance, invocation-mode, and read-only-retrieval contract tests, then implement the smallest reversible schema/retrieval change before further model evaluation. |
| 2026-08-06 | **Task Intelligence evaluation is guarded; controlled calibration still shows no repeatable correctness lift.** Seven CLI/API/filesystem fixtures each fail at the exact base ref and pass at the exact known-good ref. The evaluator isolates agent configuration, skips treatment-only Brief construction during baseline screening, aborts non-measurable runs, enforces exact token caps, blocks invalid judges by default, records stage-level metadata from judge through acceptance, preserves unmeasured values as unknown, and requires complete stage traces for promotion. | A valid judge, relevant retrieval, and delivered memory are necessary but individually insufficient. The earlier 0/3 to 2/3 restore signal came from one task and exceeded the latency ceiling. Two newer tasks tied at 3/3 and a harder pair failed in both conditions despite lower treatment cost. | Self-test: 7/7 canaries base-fail/known-fix-pass. Retrieval diagnostic: 16/18. Null graph: 3/3 in both conditions, input -18.5%, duration -15.7%. Restore paths: 3/3 in both, input -26.0%, duration -0.8%. Reset containment: 0/1 in both, input -40.1%, duration -31.9%. Seven tasks are contract-valid; 23 remain ineligible. Correctness promotion fails closed; V1 stays default; no public surface or claim is authorized. Next: do not spend more model tokens until a real pre-existing memory and independent black-box task form a valid causal golden path. |
| 2026-08-05 | **Task Intelligence preliminary holdout failed the promotion gate.** PR #21 merged the deterministic shadow compiler and capped paired evaluator into `main` at `fa04f2b`; exact-commit Quality, dependency audit, dashboard, clean macOS candidate, and macOS/Windows/Linux package checks are green. One paired repetition then ran across all 12 frozen holdout tasks. The remaining two repetitions were stopped because there was no correctness signal. The used holdout is now diagnostic and cannot serve as fresh promotion evidence after tuning. | The product promise is measurable task improvement, so a tied result must stop promotion even when context cost falls. Inspection showed broad, generic documentation often displaced precise task-local implementation evidence. | Baseline: 1/12 passed. Task Brief: 1/12 passed. Lift: 0.0 points; paired 95% interval `[0, 0]`; total input -16.3%; uncached input +2.9%; duration -1.9%; 24 runs, 7,946,987 total input tokens, 6,882,048 cached, 1,064,939 uncached, and 83,921 output. Cost gate passed; effectiveness and promotion gates failed. No public MCP surface, automatic injection, website claim, or client pilot was added. Next: redesign task-local source retrieval on calibration, then freeze a new answer-isolated holdout. |
| 2026-08-06 | **Task Intelligence v2 closed retrieval defects and exposed a deeper benchmark-validity failure.** The opt-in shadow profile now uses pre-fix source evidence with lineage, file diversity, independent action relevance, conflict exclusion, abstention, and an identical critical-reasoning protocol in both conditions. The maintained retrieval diagnostic reaches a historical repair file in the top ten for 18/18 calibration tasks. | A paired host-routing pilot still failed both conditions. Audit proved its hidden test requires undisclosed exact module and symbol names; all 30 tasks contain varying degrees of internal-shape coupling. Retrieval hit-rate therefore cannot establish task intelligence. | The historical manifest is explicitly diagnostic-only; promotion now fails closed without behavioral acceptance and rollback contracts. Pilot: control 448,324 input tokens/92,263 ms; treatment 244,365/64,077 ms; correctness 0/1 in both. No more model or holdout runs until black-box benchmark repair. V1 remains the default and exact rollback. |
| 2026-08-05 | **Task Intelligence Phase 0 and shadow Phase 1 completed.** The 18-task no-Brief calibration baseline is frozen at 6/18 passes with `gpt-5.6-terra`, low reasoning, and the exact local Codex CLI/prompt profile. A deterministic internal Task Brief compiler now filters lifecycle, trust, scope, and score; surfaces conflicts; preserves provenance; enforces 450/750/300 stage budgets, eight evidence items, and one graph hop; and disables read-side memory reinforcement. The paired holdout runner uses local-only GTE embeddings from pre-fix evidence, seeded order, hard token caps, metadata-only outcomes, and an automated clustered-confidence promotion report. | The product objective is measurable task improvement, so implementation must be judged against acceptance tests rather than retrieval volume or persuasive examples. | Calibration: 6/18 passed; 4,971,429 input tokens, 4,329,216 cached, 642,213 uncached, and 54,096 output. A real shadow Brief selected 8 provenance-bearing items in 771 estimated tokens with zero mutations. Twenty focused evaluator/compiler/report tests and the standalone benchmark verifier pass. Phase 2 holdout remains untouched until this evaluator is committed and green; there is no public MCP surface, automatic injection, release claim, or website change. |
| 2026-08-05 | **BUG-040 live-upgrade recurrence repaired and guarded.** The public v2.12.2 package installed one stable runtime but could not adopt genuine pre-manifest Elefante registrations, leaving Codex and VS Code bound to a deleted checkout. Customer scope now adopts only entries structurally identified by an Elefante MCP module, preserves foreign same-name servers, and retains rollback. The installer handshake now tests the actual stdio bridge and daemon instead of cold-starting a separate direct server. | Owner required global memory across every IDE and customer-first end-to-end proof on the real machine. | Live repair completed with installer state `COMPLETED`; `doctor --json` reported v2.12.2 customer scope, `customer_ready: true`, and Codex, VS Code/Copilot, and Antigravity all verified; daemon health and real bridge handshake passed. Focused regression suite is the merge gate. |
| 2026-08-05 | **Task Intelligence Phase 0 benchmark fixtures frozen.** Thirty real historical coding tasks now cover installation/distribution, dashboard data integrity, and runtime safety/trust. Every task pins a pre-fix commit, fix commit, one executable pytest node, observable success, and pre-fix context paths. The verifier enforces an 18/12 calibration/holdout split by fix-commit group, a 1,500-token three-stage Brief budget, answer-leakage checks, and metadata-only local outcome records. | The approved SDD requires measurable task improvement, not retrieval activity, before any automatic injection or claim. | Three benchmark contract regressions and the standalone verifier pass locally. Phase 0 remains open: no-Brief model baseline, exact model/tool configuration, and compute budget are not yet recorded. No runtime or public MCP surface changed. |
| 2026-08-05 | **v2.12.2 client candidate passed the real customer gate.** A fresh hosted Mac extracted the customer ZIP with `ditto`, ran the exact Finder launcher without dry-run, created the isolated runtime, initialized storage, started the user daemon, passed product health and an MCP handshake, reported customer-global readiness, then unregistered and removed the runtime cleanly. The gate exposed and guarded two product defects before release: dependency-backed imports before bootstrap and developer-only SDD requirements in client health. CI cleanup now accepts the uninstaller's valid removal of an empty manifest, and maintained actions no longer emit the observed obsolete-runtime or invalid-input warnings. | Owner required a clean, reliable client product and proof based on the actual first-customer journey rather than repository tests alone. | PR #17 exact SHA `d5f8a99`: fresh macOS install green; 294 fast tests plus isolated slow proof green; dashboard build and Python/npm dependency audits green; macOS, Windows, and Linux customer packages built and smoke-tested. No tag, public release, website change, or live user installation occurred. |
| 2026-08-05 | **BUG-041 runtime-only customer artifact integrated with BUG-040.** Release Client Candidate 1.0 is the validation lane for the upcoming v2.12.2 patch, not a second public version. It adds a separate hash-locked runtime dependency contract, strict customer payload allowlist, independent cross-platform archive verifier, and client installer profile on top of the global per-user runtime and all-detected-host coverage contract. The tagged-release workflow now consumes this customer builder on macOS, Windows, and Linux instead of the repository-like developer bundle. | The public installer exposed development material and an earlier client branch conflicted with current main/global-install work. | Fresh integration branch from current `origin/main`; no merge, tag, release, website change, deployment, or live-install mutation. Exact artifact evidence is recorded only after the integrated candidate completes QA. |
| 2026-08-05 | **BUG-040 customer-global installation contract implemented.** Release bundles explicitly install one stable per-user runtime; customer installs configure every detected compatible host against one data root and daemon; manifest schema records runtime identity and verifies exact registrations; uncovered hosts fail closed; `doctor` separates customer readiness from basic runtime health; developer checkouts cannot replace customer runtime. The macOS installer no longer presents host coverage as optional checkboxes. | Owner identified that a one-IDE or checkout-bound install defeats cross-tool memory continuity and made this the priority defect. | Focused installer, manifest, doctor, bundle, and native-installer regression gates are the release guard. Publication and migration of the current developer installation remain separate operator steps after the exact release candidate passes full CI. |
| 2026-08-05 | **Task Intelligence Pipeline SDD approved for benchmark design; implementation not started.** The existing retrieval-effectiveness proposal now defines a deterministic, token-bounded Task Brief; source-grounded selection and conflict handling; metadata-only local outcome records; a randomized paired benchmark; explicit promotion thresholds; shadow mode; rollback; and a prohibition on public performance claims before maintained evidence exists. The design reuses the current five-signal retriever, retrieval explanations, memory provenance/lifecycle fields, Kuzu relationships, and task graph instead of inventing a second memory engine. | Owner clarified that Elefante must improve effective intelligence per task by ingesting only information that measurably changes task outcomes, and requested spec-driven development. | Source contracts reviewed in retrieval.py, orchestrator.py, and memory.py. Existing access count and co-activation were explicitly rejected as causal proof. No runtime, MCP surface, release, or product claim changed. Next gate: identify at least 30 reproducible tasks and freeze acceptance criteria before implementation. |
| 2026-08-04 | **Elefante Release Client Candidate 1.0 implemented as a separate customer lane.** Started from authoritative `origin/main` at `e5b192a` (v2.12.0 plus the installer-download repair). Added a hash-locked runtime-only dependency contract, a strict macOS client archive builder, an independent archive verifier, and a `client` installer profile. The customer payload now contains only product runtime, prebuilt dashboard assets, selected install/health/backup/restore/uninstall operations, and no repository workspace, tests, migration or developer-only utilities, internal instructions, or lint/test tooling. A branch-only macOS workflow uploads a validation artifact and checksum only; it cannot publish a GitHub Release or change the website. Active product docs now state v2.12.0 is released, while RCC 1.0 is explicitly not public. | First-customer macOS install exposed a repository snapshot and development dependencies as the shipped product. Owner required a clean release-client boundary without stopping normal development. | Built and independently verified `elefante-release-client-candidate-1.0-macOS.zip` (SHA-256 `834a5926f84c12ec4cb84ec08d7197d712a7391129e2144e9e6a365a247df6f8`); extracted launcher dry-run selected `--release-profile client` and left its target absent. Client lock recompiled byte-for-byte; strict audit found no known vulnerabilities; dashboard build and high-severity npm audit gate passed. 50 release/client/routing regressions and 4 focused installer-profile regressions passed; version sync and whitespace checks passed. No push, tag, GitHub Release, website change, deployment, or live installation occurred. |
| 2026-08-01 | **Remote-source reconciliation and release handoff completed.** GitHub, not a stale local checkout, was treated as source authority: core `main` is v2.11.1 (`d370b4d`), core candidate `2c84a68` is draft PR #8, website `main` is `94c32b8`, and website candidate `7a93681` is draft PR #2. The live Vercel response is an older divergent source, not proof that either candidate is deployed. The website candidate records the source-authority rule, production routes, Contact boundary, release manifest, canonical asset digests, visual/accessibility coverage, and non-production release order. An initial website CI failure exposed two portability defects: a logo verifier incorrectly depended on Git history absent from a shallow runner, and strict screenshot pixels differed under macOS/Linux font rasterization. The verifier now uses fixed canonical SHA-256 values and the visual assertion keeps a narrow platform tolerance; the replacement GitHub workflow is green. | Owner required current GitHub and live-site truth after development across multiple machines, plus a durable handoff for another agent. | Core PR #8: Quality green (Python, dashboard, production dependency audit) and exact-SHA macOS/Windows/Linux installer build green. Website PR #2: validation green and all 27 Chromium checks green. Both candidate worktrees matched their pushed remote heads and were clean. No merge, tag, GitHub Release, Vercel deployment, Vercel credential login, or Contact submission occurred. |
| 2026-07-30 | **v2.12.0 release candidate integrated without rewriting PR #7 history.** Current v2.11.1 fixes were retained while the Memory Intelligence dashboard, Decision Graph, canonical branding, deterministic disclosed showcase, host-aware installers, platform launchers, and non-mutating dry run were merged. Customer documentation was separated from proposals, migration/support history, defects, and release operations; the public changelog was rewritten in customer language; active stale version promises were regression-guarded; the configured SQLite-vector/Kuzu initializer replaced a retired Chroma path; strict production dependency evidence closed stale GAP-029; and deterministic `SHA256SUMS` became a release asset contract. The release advisor was run after the changelog was complete and its automated 3.0.0 proposal was explicitly overridden by the owner-approved minor release, then every declaration was advanced together to 2.12.0. No live memory store, legacy migration, tag, release, or deployment was changed. | Owner-approved v2.12.0 fix-and-release plan, with core publication required before website publication | Local proof: 267 fast tests passed (4 legacy-backend skips, 1 isolated slow test deselected); the isolated slow two-bridge test passed; dashboard build and both npm audit gates passed with zero known vulnerabilities; strict hash-locked Python audit found no known vulnerabilities; the lock reproduced byte-for-byte; macOS, Windows, and Linux archives passed extracted-root, launcher, permission/byte, non-mutating dry-run, and generated-checksum verification; release-note validation, version sync, routing, package, scoped Ruff, workflow YAML, and whitespace checks passed. The first exact-SHA Quality run then exposed an over-escaped inline version regex that local component checks did not execute; the workflow now imports the canonical `src.__version__` directly and a release-pipeline regression locks that command. Replacement exact-SHA checks remain required before publication. |
| 2026-05-01/02 | v2.10.0 contract release scoped (A1–A10 accepted, X1–X6 rejected, P1–P6 pending) | Architect design session | Decisions ledgered §2.3–§2.6 |
| 2026-05-02 | BUG-026 filed (passive-protocol failure mode in direct-repo agent); 3 same-session recurrences | DOC_SYNC violation analysis | Active filename guard `test_no_forbidden_filename_patterns_*` lands; 18/18 tests green |
| 2026-05-02 | Documentation Skill authored (Closed Surface Map, Forbidden Patterns, Pre-write checklist, New-File test) — passive guard for BUG-026 | Constitution merge | Skill cites `workspace/ISSUES.md` BUG-026 + Issue #12 narrative |
| 2026-05-02 | Phase B constitution merge — `docs/elefante-orchestrator-agent.md` (298 LOC) + `agents/orchestrator.md` (150 LOC dispatcher) → `agents/orchestrator.md` (270 LOC single canonical) | Three competing authority sources collapse to one | ~25 references cascaded; 18/18 green |
| 2026-05-02 | Hermes wired as MCP client (`~/.hermes/config.yaml mcp_servers.elefante`) | First non-IDE Elefante consumer | `hermes mcp test elefante` returns 20 tools; `mcp==1.27.0` installed in Hermes uv venv |
| 2026-05-02 | Architectural restructure — `docs/` rebuilt on Diátaxis (`reference/`, `how-to/`, `explanation/`); state moved to `workspace/`; manifests to `agents/manifests/`; pre-restructure tree preserved in `docs/_archive/` | "Files moved, folders didn't" diagnostic | 41 files relocated, 0 lost; 18/18 green |
| 2026-05-02 | Postmortem distillation pass — 4 of 5 postmortems compressed to T/R/W/P/A atomic chunks | Elefante-as-memory lens | `installation` 1401→130 (91% cut); `ai-behavior` 1044→110 (89%); `database` 572→77 (87%); `dashboard` 729→86 (88%); full narratives preserved in `workspace/postmortems/_archive/` |
| 2026-05-02 | Curation pass 1 violations recorded — `surface-split.md` (583 LOC) + `documentation-strategy-protocol.md` (450 LOC) deleted without preservation; only absorption maps now exist | "WE DONT CUT INFORMATION IT GETS DOCUMENTED" directive | Originals unrecoverable (never committed); absorption stubs at `workspace/proposals/_archive/` document where each section's content survives |
| 2026-05-02 | Postmortem distillation pass 3 — `memory.md` 1255 → 145 LOC (88% cut); original archived FIRST per BUG-027 lesson | "Information must be documented, not cut" rule applied | All 5 postmortem originals now preserved verbatim in `_archive/`; 18/18 guards green |
| 2026-05-02 | **Layer 3 engaged for the first time** — Claude-Code-as-MCP-client called `elefante-MemoryAdd` × 9 + `elefante-DirectiveAdd` × 3 directly via stdio JSON-RPC on `src.mcp.server`. 6 lessons stored unique, 3 fused with existing memories, 3 directives added (count 13→16). Verification queries surface added memories at score 0.61–0.81 on distinctive phrasing. | "WHY HAVE YOU STOPPED? WHAT IS YOUR MAIN OBJECTIVE?" challenge — exposed that the recursive memory loop had been idle for ~10 hours of session producer-side work | The recursive Hermes/Elefante loop is consumer-agnostic — any MCP-capable agent closes it. Hermes still pending model config for LLM-driven engagement. |
| 2026-05-02 | **Unified Workflow Lifecycle authored** — agents/orchestrator.md gets the canonical 11-step Lifecycle (steps 0→10) replacing scattered overlapping protocols (The Loop / Five Gates / Memory Janitor / Documentation Skill / Closure Sequence — now framed as detailed implementations of steps 5+8). AGENTS.md mirrors the Lifecycle table at top. Lifecycle stored as Elefante memory id=f1fb77f5 (retrievable at score 0.755) + installed as directive (DirectiveList count 16→19). | "WORKFLOW LIFECYCLE NOT CLEAR. AGENTS GET CONFUSED. CONTEXT AND CLEAR PROTOCOL IS CRUCIAL" challenge | Agent now follows steps 0→10 linearly. Every cycle ends with INGEST + JOURNAL + COMMIT. |
| 2026-05-02 | **Honest accounting on Hermes status** — corrected projection language. Hermes is wired (Layer 1+2 ✓) but NOT running as LLM agent: `hermes status` shows Model:(not set), all 12 API keys ✗, .env ✗. Layer 3 closed only via Claude-Code-as-MCP-client this session, NOT via Hermes itself. | "NEVER SIMULATE. ALWAYS FACT DRIVEN" challenge | Distinguish wire-alive (Layers 1+2) from agent-alive (Layer 3 from Hermes side). Hermes = dormant consumer until provider config lands. |
| 2026-05-02 | **Tickets opened — BUG-027 (file-edit destructive op without preservation, parent class BUG-006) + GAP-028 (Hermes LLM provider configuration, user wants DeepSeek for certain tasks).** Both rows added to `workspace/ISSUES.md`. ISSUES.md path-cascade also fixed (stale `ops-*-compendium.md` → `postmortems/<domain>.md`). GAP-028 ingested as Elefante memory id=5179e3c8; BUG-027 ingested but fused with existing similar memory (Compliance Gate dedupe — working as designed). Decision matrix for DeepSeek paths (OpenRouter / direct API / hybrid) authored in `workspace/PLANNING.md §6.4.1`. | "MAKE SURE TO OPEN A TICKET TO CHOOSE HERMES OPTIONS. I WANT TO CONNECT IT WITH DEESEEK FOR CERTAIN TASKS" | User-side action required to close GAP-028 (set API key + `hermes login` + `hermes model`). Architect updated recommendation: native DeepSeek path (Hermes recognizes `DEEPSEEK_API_KEY` directly). |
| 2026-05-02 | **GAP-028 CLOSED.** User pasted DeepSeek API key into `~/.hermes/.env` (rotation pending — key was exposed in chat). Verifier `/tmp/elefante-gap-028-verify.py` reported Layer 0+1+2+3 PASS. First Layer-3 round-trip ran on `deepseek-v4-pro`; subsequently swapped to `deepseek-v4-flash` per user preference (smaller/faster) and re-verified — both surfaced memory id `f1fb77f5` with verbatim content match against the Workflow Lifecycle memory ingested earlier this session. Hermes (running v4-flash) synthesized: "The directive containing this lifecycle is also repeated inline in every Elefante tool response as a permanently injected directive" — proving BOTH the memory body AND the auto-injected directive surface (BUG-006 fix working). | "Close GAP-028 first" + user pasted key + "deepseek should be not with pro version. keep it on the smaller model." | **The recursive Hermes <-> Elefante memory loop closed for the first time from the Hermes side, not just Claude Code.** Real Layer-3 engagement on `deepseek-v4-flash`. Loop is now a measurable consumer surface. |
| 2026-05-02 | **Documentation-as-journal pattern validated** (this turn). Session produced ~14k LOC of doc work + 6+ ingested memories + 3 directives + 1 Layer-3 Hermes engagement. The 11-step Lifecycle closed multiple times during the session, each ending with a JOURNAL row. Observed: journal made decisions retrievable across the conversation (e.g. Hermes purpose pulled from §6.4 + §10 + memory `f5e15250`); exposed simulation when projection slipped in ("Hermes will load…" without Hermes having run); recorded failure modes (BUG-026 3x recurrences, BUG-027 1033-LOC loss) that would otherwise repeat in next session; proved Elefante's engine works on its own development trace via memory `f1fb77f5` round-trip through DeepSeek. | "learning, how we use the documentation as journal" — user reflective challenge | The journal is **the mechanism by which work compounds across sessions**. Without it, every cycle is a draft. With it, every cycle is a deposit. Discipline cost: every cycle ends with INGEST + JOURNAL + COMMIT. Returns: session continuity, simulation detection, recurrence prevention, dogfood proof. |
| 2026-05-02 | **Memory tool consolidation atomic swap COMPLETE.** Tool count 20 → 16. 5 legacy memory tools (`MemoryAdd` / `MemorySearch` / `MemoryUpdate` / `MemoryDelete` / `MemoryConsolidate`) deleted in same atomic change that introduced `elefante-Memory` with discriminated `action` param. Hermes audit (deepseek-v4-flash) before surgery caught 7 prep items including a silent Compliance Gate regression that I'd have shipped solo — I revised the plan based on the audit (gate stays internally name-keyed via handler-side calls; only error messages updated). Files touched: `src/mcp/server.py` (tool def + dispatcher + 5 system updates), `scripts/verify/verify_e2e_tests.py` (EXPECTED_TOOLS + 13 call sites + grounding check), `tests/test_memory_persistence.py` (2 call sites), `scripts/setup/configure_antigravity.py` + `configure_vscode_bob.py` (IDE allowlists), `README.md` + `docs/README.md` + `docs/reference/tools.md` (counts). Hermes confirms post-swap: 16 tools visible, `elefante-Memory` first listed, full discriminated description retrievable. 18/18 guards green throughout. | "i need to consolidate the tools." + "do it now end-to-end multi-step" + Hermes audit findings | **First successful tool surface consolidation in Elefante history. Lesson learned earlier same day (alongside-deployment is theater) prevented this from being another reverted attempt.** Hermes-as-auditor pattern paid for itself again — would have shipped a Compliance Gate regression solo. |
| 2026-05-02 | **Tool consolidation PRD authored + Phase-1 implementation reverted same day** (workspace/proposals/tool-consolidation.md, revised ~165 LOC). Original proposal: v2.11.0 alongside-deployment of `Memory` consolidated tool + 5 legacy memory tools, v3.0.0 deletes legacy. Phase 1 implemented `elefante-Memory` (5→1) alongside legacy → tool count went 20 → 21. **User caught the error: alongside-deployment is theater, not migration. Cognitive load went UP, not down.** Reverted: server.py back to 20 tools, README/docs/tools.md restored, tests green. Proposal updated to **atomic-swap migration plan** (no overlap window — v3.0.0 deletes legacy and introduces consolidated in same commit). Lesson ingested as Elefante memory + directive (high-priority) so future migration proposals must specify atomic swap, not alongside-deployment. | "why bother to make this step for one tool? aint that stupid??? please think about this? elefante why am i doing this error? learn." | **Genuine self-improvement cycle.** AI implemented; user caught the error in real time; AI reverted + documented + ingested lesson. This is the AI-driven-but-human-curated pattern working: human catches blind spots AI doesn't notice, AI deposits the learning into Elefante so the next agent inherits it. P7 reframed: approve atomic-swap plan only, do not bundle alongside-deployment. |
| 2026-05-02 | **Hermes audit pass — independence-by-different-LLM proved its keep on first run.** User asked Hermes (deepseek-v4-flash) to audit this session's docs. DeepSeek delivered 7 specific findings with file:line evidence: (HIGH×3) ISSUES.md titled "Debug Documentation Index" instead of BUG/GAP tracker; BUG-027/GAP-028 rows had no clear canonical home; memory `5179e3c8` (GAP-028) was stale OPEN status; (MED×2) memory `faeecf42` claimed Hermes never ran; §10.2 BUG count said 26 vs actual 27+3; (LOW×2) docs/debug/ referenced but doesn't exist; §10.2 unmeasurable compliance metric needed reframe. **All 7 actioned this turn:** ISSUES.md retitled "ISSUES — BUG/GAP Tracker" + Layout/postmortem sections rewritten + stale Structure/File Inventory blocks removed; stale memories `5179e3c8` + `faeecf42` marked `deprecated: True` via `elefante-MemoryUpdate` (excluded from normal search); new corrected memories ingested as id `3ed88442` (GAP-028 CLOSED) + id `e0e66320` (Layer 3 state current); §10.2 BUG count updated to 27+3 GAPs; compliance metric reframed as DEFERRED-by-plan, not unmeasured. | "let's ask hermes, self improvements" challenge — user delegated audit to a different LLM to expose Claude Code's blind spots | **Hermes-as-auditor earned its independence value on the first real task** — caught 7 inconsistencies I missed self-reviewing. Pattern proved: different LLM, different blind spots. The cost (one `hermes -z` call) is much smaller than the recurrence cost of shipping the gaps unfixed. 18/18 guards still green. |
| 2026-07-26 | **Memory Intelligence dashboard SDD implemented and handed off on GitHub.** Replaced inventory-first Overview with an evidence-aware Briefing; preserved the exact emblem with a clipped hover whisper over its original network; applied the carbon/tusk/copper/brass/clay/sage system across Memories and Connections; normalized `from`/`to` plus legacy endpoint aliases; fixed configured-backend provenance; added a deterministic source-grounded showcase; preserved the previous operator guide verbatim before retiring stale procedures; removed the unused vulnerable router dependency; advanced the contract to v2.12.0. After the initial handoff, the user caught BUG-034: the corner asset was itself a truncated export. It was replaced with the complete canonical elephant-and-network crop, the hover mask was restricted to the network, and the exact asset is now regression-locked. PR CI then exposed BUG-035: lock freshness compiled without the existing lock and floated unrelated transitive releases. The workflow now seeds the checked-in lock before recompilation. The next run passed that gate and exposed BUG-036: a stale test required a historical Chroma directory even though SQLite is the default. The test now proves the active SQLite vector path, absent retired Chroma path, and lazy Kuzu path under a fresh isolated home. | User rejected the generic AI visual language, deformed substitute logo, stale product screenshot/content, and abstract concept cards; then explicitly approved implementation, complete documentation, GitHub handoff, and stopping at that point. User subsequently rejected the broken corner mark visible in the launched site and authorized fixing all failed PR checks. | Showcase validates at 37 memories / 11 entities / 95 edges. Browser acceptance covers Briefing, Memories, Topics, and Graph at 1600×1000 and caught two runtime-only defects (React selector loop and topic-color fallback). The corrected live header shows the complete network, trunk, body, legs, and tail with zero browser errors. Dashboard build passes; npm audit reports 0 vulnerabilities; 28 dashboard tests and 20 routing guards pass after BUG-034. After BUG-035, the corrected lock workflow reproduces byte-for-byte and the 99-package hash-locked install is unchanged. BUG-036 adds clean-home and test-order proof; 258 standard tests and the isolated slow two-bridge test pass locally. Replacement GitHub [run 30220714470](https://github.com/ElefanteAI/elefante/actions/runs/30220714470) is green: dashboard passed in 18 seconds and Python passed in 2 minutes 52 seconds. The dashboard-boundary, final-composition brand, deterministic-lock, and fresh-home filesystem lessons were deposited and retrieved. Active stale six-signal SDD search returned no mutable match. Implementation and closure commits are pushed on `codex/dashboard-memory-intelligence`; draft PR [#7](https://github.com/ElefanteAI/elefante/pull/7) is the exact resume point. No tag, deployment, or publication. |
| 2026-07-26 | **Connections graph became an evidence-backed Decision Graph.** Replaced the synthetic topic ring and arbitrary sequential showcase links with explicit source-grounded reasoning trails. The graph now makes assumptions, evidence, current decisions, safeguards, source grounding, and relationship direction inspectable before opening the complete memory. | User identified that the graph was buried and provided no insight, then asked for more memorable demo memories and a stronger selling outcome. | The unchanged 37-memory / 11-entity / 95-link showcase now yields 8 grounded trails, 2 visible superseded assumptions, 10 safeguard relationships, and 4 explicit semantic bridges. Live 1280px browser acceptance covered full four-stage runtime and trust-boundary trails, responsive fit, trail switching, and inbound/outbound relationship grammar. Production build passes; all 29 dashboard tests and 20 routing guards pass; npm audit reports 0 vulnerabilities. The isolated showcase snapshot validates without opening or mutating a durable store. No tag, deployment, merge, or publication. |
| 2026-07-29 | **Installer download contract rebuilt from the stakeholder’s first click.** The published v2.11.1 macOS ZIP expanded into a technical folder with no obvious action; all three bundles exposed cross-platform wrappers, and byte inspection found the Windows bootstrap path corrupted by a hidden `0x08` backspace. Bundle generation now emits platform-specific customer launchers, a visible first-run guide, stable executable metadata, clean Windows bytes, exact entrypoint manifests, and an AppKit host selector that preselects detected agents and forwards only the chosen adapters. During destination proof, BUG-038 exposed that `--dry-run` still moved the live installation before its branch; the original v2.9.2 payload was restored and dry-run now exits before any placement. | User required the marketing download journey to be seamless, host-agnostic, and one-click from the preferred agent choice, then authorized the online remediation path. | Eight focused bundle tests plus the host-selection installer suites pass. The native AppKit window was visually inspected with VS Code, Claude Code, Codex, and Antigravity detected and preselected. Fresh v2.11.1 macOS, Windows, and Linux archives contain only the intended root launchers; Windows contains no unexpected control bytes; isolated dry-run leaves its target absent. All three assets were replaced on GitHub and re-downloaded SHA-256 digests match the validated local archives. |

### §10.1 Lessons logged this session

- **2026-08-26 Agent-loop claim audit and release-truth refresh:** tested the
  supplied Goal → Perceive → Plan → Act → Observe → Update → Repeat claims
  against the public v2.12.3 source/tag, current public `main`, installed
  customer runtime, and live website. The evidence supports MCP tool use,
  durable memory, graph/context/task/ETL/directive lifecycle, compliance
  gating, and restart persistence; it does not support Elefante owning an
  autonomous reasoning loop, reflection, stopping, financial-advisory tools,
  provider billing, or hidden chain-of-thought. The active developer source
  exposes an unreleased 18-tool/2-prompt surface; its isolated self-protocol
  passed 48/48, the current relevance/ledger/report suites passed 57, and the
  documentation/token/MCP suites passed 121 with one intentional deselection.
  All three v2.12.3 release ZIPs passed `SHA256SUMS`; the live website identity,
  release-manifest verifier, and production verifier passed. The immutable tag
  still contains stale version headings, while current `main` and local docs
  now separate public, installed, and unreleased development claims. No remote,
  production, durable-memory, or installed-runtime mutation was made by this
  documentation audit.
- **2026-07-26 Dashboard truth is a boundary, not a skin:** a useful memory dashboard explains how knowledge evolved and why the current decision endures. Normalize transport aliases once at the UI boundary, derive labels from configured runtime truth, disclose synthetic demo behavior, and never render retrieval signals the snapshot does not carry. The real browser pass is mandatory: TypeScript compilation did not catch the React selector loop, source inspection did not reveal the gray topic fallback, and canonical source provenance did not reveal that the exported header asset was clipped. Brand assets must be inspected in the final composition at shipping size.
- **2026-07-26 A useful memory graph visualizes reasoning, not topology:** topic rings, generated hubs, and arbitrary “related” sequences may look organized while communicating nothing. A graph becomes commercially legible when explicit edges preserve what was believed, what challenged it, which decision replaced it, what now guards it, and where that claim is grounded. Relationship direction must be phrased from the selected memory's point of view, and the complete trail must fit at the acceptance viewport.
- **2026-07-29 A release archive is a customer interface:** verify the extracted root, decoded launcher bytes, executable metadata, and the actual primary entrypoint. File-presence assertions missed both a broken Windows path and a confusing cross-platform folder.
- **2026-07-29 Dry run is a transaction boundary:** branch before payload placement, backups, service changes, or any other durable side effect, then assert the target remains absent or unchanged.
- **2026-07-22 Daemon foundation:** added `src.mcp.daemon`, a loopback-only Streamable HTTP host for one Elefante MCP server instance at `/mcp`. It is the required transport boundary for the future stdio bridge and prevents each HTTP-capable client from opening its own database-owning process. Proof: Starlette lifespan health check and targeted regression suite passed. It does not close GAP-025 until provenance, migration, bridge, and concurrent-client proof land.
- **2026-07-22 Stdio bridge:** added `src.mcp.stdio_bridge`, which forwards newline-delimited MCP JSON-RPC to the loopback daemon and rejects non-loopback targets. The bridge owns no stores. GAP-025 remains open until provenance, migration, and concurrent-client proof land.
- **2026-07-22 Trust Release foundation:** universal-agent contract and release gates documented; dashboard moved to loopback-by-default with explicit CORS and loopback Docker publication; GraphQuery made read-only at the MCP boundary; automated suite collection repaired; GitHub quality workflow added. Proof: `pytest tests -q` 160 passed and dashboard `npm run build` passed. Remaining release blockers: singleton daemon/provenance migration, exact runtime dependency contract, and production dependency audit remediation.
- **2026-07-22 GAP-025 implementation:** daemon writes now serialize across in-process MCP sessions; every stored memory round-trips a source tuple and gains a deduplicated `(:Entity)-[:WRITTEN_BY]->(:Source)` link. Fresh-store proof: 25 focused tests pass. Live migration dry-run reports 0 missing metadata tuples and 28 graph links pending explicit apply.
- **2026-07-22 Distribution foundation:** added a dry-run-first user-scope daemon service manager for launchd and systemd-user. It writes only Elefante's service definition on explicit apply; Windows registration and host adapter emission remain release work.
- **2026-07-22 First bridge adapters:** VS Code and Antigravity configuration now launch `src.mcp.stdio_bridge` with loopback daemon provenance settings, not a database-owning server. Verified by installer tests; these hosts remain compatible, not certified, until their full install/reconnect/uninstall paths are exercised.
- **2026-07-22 Install manifest:** emitted VS Code, Antigravity, and daemon-service files are atomically recorded in `~/.elefante/install-manifest.json`. The manifest deliberately tracks only Elefante-owned outputs; safe manifest-driven uninstall is the next distribution step.
- **2026-07-22 Safe uninstall:** central and daemon-service uninstall paths remove only manifest-recorded files whose hash still matches emission. Later user edits are reported and preserved.
- **2026-07-22 Distribution hardening:** expanded the user-scope daemon service to Windows Task Scheduler and changed the install manifest from whole-JSON-file ownership to exact Elefante JSON-entry ownership. Proof: installer/setup tests pass, including preservation of unrelated MCP servers and modified service definitions. `pytest tests -q` passes 183 tests (one slow test deselected); the two-bridge concurrent provenance proof passes in 32.29 seconds. Dashboard `npm ci`, production build, and full `npm audit` pass with zero findings after locked Lodash, React Router, Vite, React plugin, PostCSS, and Picomatch remediation. The remaining GAP-025 data action is intentionally unperformed: legacy graph-link migration dry-run reported 28 links pending explicit user-authorized `--apply`.
- **2026-07-22 Cursor/Kiro compatibility adapters:** added detect-then-emit global bridge configuration for existing Cursor and Kiro user directories. Both preserve unrelated MCP servers, emit distinct `source.tool` values, and unregister only the Elefante entry through the install manifest. Vendor configuration contracts were refreshed against Cursor MCP and Kiro MCP references; the matrix records these hosts as compatible, not certified. Proof: adapter plus uninstall round-trip regression passes.
- **2026-07-22 Claude Code/Codex compatibility adapters:** added native-CLI registration for the two primary coding-agent hosts. The adapter never replaces an existing `elefante` registration; after a successful add, it fingerprints the host's own MCP configuration and removes only a matching registration on uninstall. Installer-owned registration refresh now rolls back on failure; user-managed registrations remain untouched. Codex uses its official JSON inspection output, canonicalized before hashing because object order is nondeterministic. Proof: mocked registration, preservation, refresh, rollback, and fingerprint-checked removal tests pass; Codex registration, inspection, refresh, and removal also pass against the installed CLI in an isolated `CODEX_HOME`. No host is certified until its full external lifecycle is automated.
- **2026-07-22 Daemon endpoint hardening:** the daemon now rejects non-integer and out-of-range ports, while bridges accept only a credential-free `http://127.0.0.1[:port]/mcp/` endpoint with no URL query or fragment. This closes ambiguous local endpoint parsing before any network connection is attempted. Proof: eight focused daemon tests and the 181-test fast suite pass.
- **2026-07-22 Service observability:** `daemon_service.py status` now reports exact service-file ownership, the read-only platform runtime state, and the loopback daemon health result without starting, stopping, or editing anything. The first local invocation correctly reported no installed service rather than implying readiness. Proof: 19 installer-focused tests, 187 fast tests, and the two-bridge daemon proof pass.
- **2026-07-22 Safe daemon-service refresh:** rerunning the service installer now preserves untracked or modified service definitions without executing service-manager commands, returns a visible nonzero conflict result, and refreshes only manifest-owned definitions. Linux refreshes with `try-restart`; launchd tolerates a stale or absent job before bootstrap. Proof: 27 installer-focused tests and the 191-test fast suite pass.
- **2026-07-22 Read-only doctor:** added `scripts/lifecycle/doctor.py` as the single readiness report for developers and agents. It covers repository runtime, service/health, installer ownership, and declared integration tiers without probing or modifying host configuration. The command emits JSON for agents, exits nonzero when not ready, and reported the actual current machine as not-ready because no daemon service is installed—an honest result. Proof: 30 installer-focused tests and the 194-test fast suite pass.
- **2026-07-22 Installer daemon health gate:** the installer now requires the exact loopback daemon health payload within 15 seconds after service installation and before it writes MCP client configuration. A launched-but-broken service therefore fails closed rather than leaving users with dead host registrations. Proof: 33 installer-focused tests and the 197-test fast suite pass.
- **2026-07-22 Provenance input hardening:** transport headers and stdio environment values are now treated as untrusted before persistence. The daemon rejects control characters, bounds tool IDs to 128 characters, instance/session IDs to 256, and workspace paths to 1024, and uses explicit safe fallbacks rather than storing malformed values. Proof: focused daemon and persistence suites pass; the 199-test fast suite, bytecode compilation, diff-whitespace check, and leaked-daemon process check pass.
- **2026-07-22 Recoverable backup/restore:** upgraded the existing file-level recovery path rather than creating a parallel system. Backups now contain checksummed manifests and exclude nested recovery archives; restore defaults to a read-only preflight, rejects zip-slip, symlink, duplicate-member, and integrity failures, stages extraction before replacement, and preserves replaced data unless an explicitly confirmed discard is requested. JSON/CSV export is now plainly labeled analysis-only, not a recovery format. Proof: 6 new recovery-safety tests plus the 205-test fast suite pass; `git diff --check` and process-leak checks pass. Portable JSON import remains explicitly deferred.
- **2026-07-22 Dashboard trust boundary:** removed live ChromaDB access and browser-triggered snapshot generation from the dashboard. Graph, search, and statistics now read the redacted snapshot only; search is explicitly lexical, and the browser reload control cannot mutate data. Absolute local data paths are no longer returned. Live regeneration remains MCP/CLI-only. Proof: 2 new runtime boundary tests, the 207-test fast suite, production dashboard build, `git diff --check`, and process-leak checks pass.
- **2026-07-22 Bridge input discipline:** the stdio bridge now bounds a JSON-RPC message to 1 MiB before parsing or forwarding it, rejects non-object payloads, and resets request state per line so a malformed request cannot emit an error against the previous request ID. Proof: focused bridge runtime tests and the 209-test fast suite pass; `git diff --check` passes.
- **2026-07-22 Direct HTTP input discipline:** the Streamable HTTP daemon now applies the same 1 MiB request-body limit before its MCP session manager receives a request. It checks declared lengths and streamed chunks, while replaying valid bodies exactly once to the official transport. Proof: runtime boundary regression covers valid replay plus declared and chunked rejections; the 210-test fast suite passes.
- **2026-07-22 Container exposure discipline:** the standalone dashboard image no longer overrides the loopback bind default. Compose retains an internal `0.0.0.0` bind only so its host-loopback-published port can reach the container; direct network exposure is no longer offered as a copy-paste configuration path. Proof: dashboard contract tests pass and `docker compose config` was attempted, but Docker is unavailable in this workspace; the 211-test fast suite passes.
- **2026-07-22 Python lock discipline:** every declared direct Python dependency is exactly pinned, and a generated universal `requirements.lock` carries transitive package hashes. Docker, the installer, release bundles, and CI install with `--require-hashes`; CI also verifies the lock against the `uv` generation command. The installer refuses to resolve dependencies if the lock is absent. Proof: `uv pip sync --dry-run --require-hashes` accepts the lock, `pip check` reports no broken requirements, and the 213-test fast suite passes.
- **2026-07-22 MCP security update:** upgraded the direct MCP Python SDK from v1.23.1 to v1.28.1 after the first lockfile advisory scan reported three MCP advisories. The hash-locked sync, focused transport suite, two-client concurrent daemon proof, and 213-test fast suite pass. The post-update audit reports 18 remaining advisories across five non-MCP packages; they are GAP-029 release-blocking work, not waived findings.
- **2026-07-22 Dependency remediation:** upgraded Black to v26.3.1, the compatible pytest pair to pytest v9.0.3 / pytest-asyncio v1.4.0, FastAPI/Starlette, and the local embedding stack to SentenceTransformers v5.6.0 / Transformers v5.14.1. The configured `thenlper/gte-base` embedding runtime loads and emits finite 768-dimensional vectors; the full 215-test fast suite and `pip check` pass under the new lock. The audit now reports one ChromaDB advisory with no published fix; it remains GAP-029 release-blocking work.
- **2026-07-22 SQLite vector-store exit path:** added a dependency-free SQLite backend as a fresh-store opt-in, preserving full Memory JSON and float32 embeddings with deterministic exact-cosine search. CRUD, provenance round-trip, filters, pagination, update, delete, factory selection, startup environment selection, and Chroma-free runtime behavior are covered by runtime tests. It is intentionally not the default and does not inspect or alter existing ChromaDB data; migration requires explicit authorization, a verified backup, dry-run, parity evidence, and rollback. Proof: `pytest tests -q` 219 passed, 1 deselected.
- **2026-07-22 Agent-host reach:** Gemini CLI now receives a preserving, exact-entry-owned `mcpServers.elefante` bridge only when both its binary and existing user directory are detected; it never mistakes an Antigravity directory for Gemini CLI. OpenClaw is no longer incorrectly excluded: its native MCP registry now gets the same fingerprinted, safely removable bridge lifecycle as the other CLI hosts. Agent Zero remains community-tier with container-boundary guidance; Grok is correctly described as a provider selected inside an MCP-capable host, not a host integration. Proof: 37 installer tests, 18 documentation-routing tests, and the 221-test full suite pass. Gemini and OpenClaw CLIs are not installed in this workspace, so no external-host certification is claimed.
- **2026-07-22 Integration observability:** `doctor` now separates integrations declared compatible by the repository from host surfaces actually configured by this Elefante installation. It reports only normalized surface names from the ownership manifest—never host commands, configuration paths, or values—and includes community-tier declarations. Proof: 38 focused installer/doctor tests and the 222-test full suite pass (one slow test deselected).
- **2026-07-22 JSON host-ownership hardening:** all active JSON configuration adapters now preserve an existing user-managed `elefante` entry, malformed JSON, and externally modified files. Reconfiguration refreshes only an unchanged exact-entry manifest record, and writes atomically. This closes the overwrite gap between JSON configuration hosts and the fingerprinted native-CLI adapters. Proof: 43 focused installer tests and the 227-test full suite pass (one slow test deselected).
- **2026-07-22 Enforced release dependency gate:** tagged GitHub releases now require a pinned `pip-audit` action to scan the universal hash-locked requirements before publication. It intentionally fails while the outstanding ChromaDB advisory remains, preventing a release workflow from contradicting GAP-029. Pull-request quality remains runnable for remediation work. Proof: release-workflow contract regression and YAML parse pass; the current lock audit reports exactly `chromadb 1.3.5` / `PYSEC-2026-311` and exits nonzero; the 228-test full suite passes (one slow test deselected). Live tag execution is intentionally not triggered.
- **2026-07-22 SQLite latency baseline:** added a deterministic, temporary-store benchmark that exercises the public exact-cosine search path without opening any existing Elefante or ChromaDB data. At 5,000 synthetic 768-dimensional memories, 20 queries, and `limit=10`, the local CPU measured p50 221.522 ms and p95 235.530 ms. This is evidence for a future threshold, not a portability or default-change claim. Proof: disposable benchmark regression and the 229-test full suite pass (one slow test deselected).
- **2026-07-22 SQLite lifecycle and recovery proof:** controlled shutdown now flows from the daemon and Elefante mode through the orchestrator, closing both synchronous and asynchronous stores, including the opt-in SQLite handle. Backup/restore now has an explicit SQLite database round-trip proof that verifies both restored and preserved-current copies. Proof: 27 focused lifecycle/recovery tests, `pip check`, `git diff --check`, and the 232-test full suite pass (one slow test deselected). Existing-data migration remains deliberately unperformed and authorization-gated.
- **2026-07-22 Direct-transport lifecycle and installer hygiene:** direct `python -m src.mcp.server` execution now releases its orchestrator in a `finally` block, matching the daemon lifecycle. Antigravity configuration no longer creates an untracked full-file `.json.bak`; its atomic manifest-owned update preserves user entries without accumulating redundant artifacts. Proof: 59 focused daemon/installer tests, `pip check`, compilation, diff-whitespace validation, and the 234-test full suite pass (one slow test deselected).
- **2026-07-22 Live-contract and surface-truth repair:** the source-derived MCP inventory is 16 tools and 2 prompts; active startup, self-protocol, test, vision, demo, and agent-routing surfaces now state that contract and use the consolidated `elefante-Memory(action=...)` syntax. A real self-protocol run exposed stale `docs/debug` routing in both successful and error responses; the server now routes to `workspace/ISSUES.md` and linked postmortems. Proof: source inventory reports 16/2, the real isolated MCP harness passes 46/46 checks, and the full 235-test suite passes (one slow test deselected).
- **2026-07-22 Release-bundle repair:** the Docker tarball generator referenced deleted `docs/technical` files and omitted `requirements.lock`, despite Docker requiring a hash-checked install. It now packages the current Docker/Agent Zero guides plus the lock, supports a temporary output directory for clean CI proof, and is covered by archive-content regression coverage. Active runbooks no longer route users to retired `docs/debug` paths. Proof: isolated bundle test passes without creating repository artifacts, `pip check` and diff-whitespace checks pass, and the full 236-test suite passes (one slow test deselected).
- **2026-07-22 Native Codex lifecycle hardening:** an isolated real `CODEX_HOME` CLI round trip now proves initial registration, upgrade after relocation, preservation of a later user-owned registration during manifest-driven uninstall, restoration of the installer-owned registration, and normal installer-owned removal. The slow runtime proof also passes with two real bridge processes sharing one daemon while preserving distinct Codex/Claude provenance. This strengthens native registry and transport evidence without touching a user configuration or claiming actual in-host agent reconnect/certification. Proof: focused lifecycle test, explicit slow daemon/bridge test, and the full 236-test suite pass (one slow test deselected); `pip check` and diff-whitespace validation pass.
- **2026-07-22 Distribution-contract repair:** `setup.py` was advertising obsolete permissive dependency ranges and packaged only child modules, which could make a built wheel fail the documented `python -m src.mcp...` import contract. It now reads exact runtime/development pins from `requirements.txt` and includes the `src` namespace. A temporary-wheel regression builds without dependencies, checks metadata against the canonical runtime list, installs into an isolated target, and imports `src.mcp.stdio_bridge` from the installed artifact. README and installation guidance now state MCP v1.28.1, SQLite's fresh-store role, the detected compatible host surface, and the daemon-plus-stdio-bridge path rather than a database-owning IDE subprocess. Proof: focused package/documentation tests and the full 238-test suite pass (one slow test deselected).
- **2026-07-23 SQLite operator-surface repair:** JSON/CSV export used a direct ChromaDB client despite the configured SQLite backend, and factory reset ignored the default SQLite `data/vector` directory. Export now reads either configured embedded store, while reset moves both default vector locations and Kuzu into its timestamped recovery area and respects `ELEFANTE_DATA_DIR`. It now also resolves explicit vector and graph paths from the active Elefante YAML configuration, rejecting a target that would contain the recovery directory. The dashboard snapshot pipeline now reads either configured store too, and aligns its Chroma client settings with the live vector-store owner to avoid client conflicts. SQLite export, reset, and snapshot plus Chroma snapshot compatibility have real isolated round-trip tests. Proof: 87 focused storage/reset/snapshot/routing/installer tests, `pip check`, diff-whitespace validation, and the full 243-test suite pass (one slow test deselected).
- **2026-07-23 GAP-029 migration gate:** added a dry-run-first ChromaDB-to-SQLite lifecycle command that converts only an isolated stable snapshot, verifies UUID/reconstructed-memory/float32-embedding parity and representative top-10 search overlap, and cleans up both database handles and temporary output. Apply requires `--confirm-stopped STOPPED` plus an exact checksum-manifested backup match, reserves a new destination without replacement, and leaves ChromaDB and configuration untouched. No live data was opened or migrated. Proof: 37 focused migration/backup/routing tests, 247-test full suite (one slow test deselected), dashboard production build, `ruff`, compilation, and diff-whitespace checks pass. Locked audit still reports only `chromadb 1.3.5 / PYSEC-2026-311`, so GAP-029 remains release-blocking pending explicit real-store migration/default-change authorization and a clean lock.
- **2026-07-23 Release-truth and routing reconciliation:** the living plan now tracks the active v2.11.0 Trust Release instead of shipped v2.10 decision scaffolding; current release identifiers are synchronized at 2.10.0 without rewriting historical/version-specific documents. Active workspace routes now target `docs/`, `workspace/`, and `agents/`; the v3 proposal uses the source-derived 16 → 6 baseline; BUG-007 guards cover the affected proposal and lesson surfaces. No live data, host configuration, git index, or remote state changed. Proof: 29 focused routing/release tests and the full 249-test suite pass (one slow proof deselected and separately passed); the isolated self-protocol passes 46/46, dashboard build/audit reports zero findings, version sync and diff checks pass. Current-machine doctor remains honestly not-ready because no daemon service is installed; only Codex is available for host-driven certification.
- **2026-07-23 Production-grade SQLite vector default & verification suite repair:** Resolved SQLiteVectorStore backend path resolution in `src/utils/config.py` so that `persist_directory` defaults to `data/vector` when `data_dir` is unspecified, eliminating 0-record retrieval bugs. Removed import side-effect directory creations (`CHROMA_DIR.mkdir()`). Updated contract tests in `test_install_setup.py` and `test_mcp_daemon.py` to match the SQLite vector store default. Updated `verify_scoring_sandbox.py` to seed the active configured vector store handle (`get_vector_store()`), resolving all 23 snapshot and scoring sandbox assertions. Fixed U+2194 arrow formatting in `PLANNING.md` for `verify_emoji_policy.py`. Proof: All 252 pytest unit/integration tests pass 100% green; all 6 verification scripts (`verify_health.py`, `verify_dashboard_snapshot.py`, `verify_emoji_policy.py`, `verify_mcp_handshake.py`, `verify_scoring_sandbox.py`, `verify_e2e_tests.py`) pass cleanly; self-protocol harness passes 46/46 isolated checks.

- **Never delete an uncommitted file.** Commit first, then delete with a record. Git history becomes the archive. The `### Removed` CHANGELOG line is not satisfaction of the Memory Janitor mandate if the underlying content is unrecoverable.
- **Curation must measure both sides.** Token-cut percentage alone is not a metric — must also measure retrieval quality after the cut. Current curation work is measurement-blind on the consumer side; awaits Hermes ingestion data.
- **Distillation is preservation, not loss — IF and only IF the original is archived.** The active surface gains atomic chunks for fast retrieval; the archive keeps full narrative for historical context. Both serve different journal purposes.
- **Three competing constitutions = 4-way authority confusion.** Single canonical `agents/orchestrator.md` is the only stable resolution. Loadable file IS the constitution; the constitution IS the dispatcher. No separation needed.

### §10.2 Metrics — what we measure (and what we don't yet)

| Metric | Current value | Source | Status |
|--------|---------------|--------|--------|
| Published product | **v2.12.3** with checksummed macOS, Windows, and Linux assets | GitHub release verification recorded in §2.3 and this audit | Verified 2026-08-26 |
| BUG/GAP count tracked | **50 BUG records through BUG-052 + 7 GAPs** | `workspace/ISSUES.md` | Tracked |
| BUG recurrence rate (pre-distillation) | known per-row in `ISSUES.md` | `workspace/ISSUES.md` Recurrence column | Tracked |
| BUG recurrence rate after current guards | `UNKNOWN` — needs sustained traffic across sessions | future `ISSUES.md` recurrence updates | Not measured |
| Documentation guard | 36 tests pass | `tests/test_developer_routing.py` | Verified 2026-08-13 |
| Full fast regression suite | 458 passed, 4 legacy-backend skips, 1 slow test deselected; isolated slow proof passed | §10 GAP-054 journal entry | Verified 2026-08-13 |
| Task Intelligence evaluation corpus | 9 reviewed black-box canaries; 23 historical tasks ineligible; tasks 031 and 032 are consumed sealed-memory diagnostics | `workspace/proposals/retrieval-effectiveness.md` | Infrastructure verified; promotion blocked |
| Task Intelligence outcome lift | Task 032 stopped at treatment 0/3 and control 0/2; no valid representative multi-task lift exists | `workspace/proposals/retrieval-effectiveness.md` | Not demonstrated; promotion blocked |
| Token cost per `elefante-Memory(action="search")` | `TOKEN_STATS` is available per response; aggregate product effect is not measured | `src/mcp/server.py` | Partial |
| Token-financial companion | Phase 0 product, purpose, evidence, privacy, and user-control contract is drafted; no persistent usage ledger, provider-usage ingest, dollar-cost authority, or enterprise training surface exists | `workspace/proposals/session-intelligence.md` | Draft; not implemented or released |
| Website production state | Live commit `d4e1f321e646d04d19df7b5ec9e9942951eca83e`, product version 2.12.3; production and online release-manifest verifiers pass | §2.3 and current production proof | Verified 2026-08-26 |

Unknown and partial rows are explicit evidence gaps, not inferred success.

### §10.3 The Elefante workflow (canonical)

```
                                  ┌──────────────────────┐
                                  │ Human (architect)    │
                                  │  • directs angles    │
                                  │  • curates output    │
                                  │  • measures fitness  │
                                  └──────────┬───────────┘
                                             │
                                  ┌──────────▼───────────┐
                                  │ AI agent (scribe)    │
                                  │  • drafts            │
                                  │  • distills          │
                                  │  • applies guards    │
                                  └──────────┬───────────┘
                                             │ writes/cuts
                                             ▼
       ┌───────────────────────────────────────────────────────────────────┐
       │ docs/  +  workspace/  +  agents/                                  │
       │  (active surface — Diátaxis-pure, atomic chunks)                  │
       │                                                                   │
       │      _archive/  (preserved historical narrative)                  │
       └───────────────────────────────────────────────────────────────────┘
                                             │ ingests
                                             ▼
                                  ┌──────────────────────┐
                                  │ Hermes (MCP client)  │
                                  │  • engages Elefante  │
                                  │  • retrieves chunks  │
                                  │  • applies learning  │
                                  └──────────┬───────────┘
                                             │ data
                                             ▼
                                  ┌──────────────────────┐
                                  │ Elefante (memory)    │
                                  │  • scores            │
                                  │  • surfaces          │
                                  │  • decays            │
                                  └──────────┬───────────┘
                                             │ retrieval signal
                                             └──────► back to Human
```

**The loop closes when Hermes-driven retrieval data informs the next curation pass.** Until that loop is active, every cut is a hypothesis. The journal records each pass so future agents can audit which hypotheses paid off.

---
