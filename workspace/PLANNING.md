---
status: living
last_updated: 2026-07-30
audience: developer-agents
authority: state + roadmap + features + aspect-plans for Elefante development
related:
  - agents/orchestrator.md  # constitution (rules)
  - workspace/ISSUES.md                  # BUG/GAP tracker
  - agents/manifests/ide-integration.yaml  # integration manifest
---

# PLANNING — Elefante Developer Workspace

> **Single living plan.** Vision · Active Release · Roadmap · Features · Optimization · Ops · Dev · UX · Meta-process.
>
> Read top-to-bottom for full context. Jump to a section by aspect when in doubt.
>
> **Update protocol:** every session that closes a P-decision, OB blocker, BUG/GAP row, or shifts a feature status updates the relevant subsection IN PLACE. **Do not create new dated state files. Do not create CURRENT_STATE.md, SNAPSHOT.md, or HANDOFF-YYYY-MM-DD.md** (forbidden patterns enforced by `tests/test_developer_routing.py::test_no_forbidden_filename_patterns_in_active_docs_or_agents`).

---

## §1 Vision

**Elefante is a Full Signal Injection layer for AI agents.**

Every AI agent runs on the same physics: a finite context window where every token either raises the probability of a correct answer or dilutes it. Most workflows lose by injecting noise — restated history, irrelevant retrievals, polite filler, stale assumptions. Elefante wins by injecting only the tokens with the highest decision-value at the moment of action.

**The product is one sentence:** *Elefante maximizes signal-per-token in the agent's context window.*

User-facing definition: *"Elefante is a persistent second brain for AI agents."*

### §1.1 The Four Laws (non-negotiable)

1. **Continuity** — A session is never new; it is a continuation.
2. **Compliance** — Search before writing. Ignorance is a choice, not a constraint.
3. **Grounding** — If it's not in the brain or the workspace, it's UNKNOWN.
4. **Full Signal Injection (Efficiency)** — Every token Elefante injects must measurably raise the probability of a correct answer. **Quality per token is the only metric.**

Laws 1–3 are mechanisms; Law 4 governs.

### §1.2 Non-Goals (anti-divagation anchor)

Elefante is **not**:

1. A generic AI platform (no model hosting, no agent runtime, no orchestration framework).
2. A chat product (never owns the conversation surface).
3. A SaaS memory store (local-first is a law, not a phase).
4. An observability product first (debugging dashboards are *outputs* of Full Signal Injection, never the thesis).
5. A feature-count race (competes on signal-per-token).
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

### §1.4 Trust Release gates — no beta or commercial claim before proof

| Gate | Required proof | Current state (2026-07-30) |
|------|----------------|-----------------------------|
| Privacy boundary | Dashboard and local APIs bind loopback by default; no wildcard CORS; documented proxy/auth responsibility | Guarded locally; dashboard and daemon boundary tests pass |
| Write authority | Retrieval surfaces cannot mutate memory/graph state; writes use explicit, observable tools | Guarded locally; GraphQuery mutation regressions pass |
| Data integrity | One-writer daemon, Source provenance, migration + rollback proof | Runtime and isolated recovery proofs pass. Legacy-store migrations remain stopped, backup-gated support operations and are not a fresh-install requirement. |
| Quality | Full suite collects cleanly; targeted regressions and frontend build are green in CI | Local v2.12 release-candidate proof is green: 267 fast tests passed (4 legacy-backend skips, 1 slow test deselected), the isolated slow two-bridge proof passed, the dashboard built, and the maintained release-critical Ruff gate passed. The exact candidate SHA must still receive green GitHub checks before publication. |
| Compatibility | Every advertised host has a tested install, reconnect, concurrent-use, upgrade, and uninstall path | In progress — Claude Code, Codex, Gemini CLI, OpenClaw, VS Code, Cursor, and Kiro bridge emission and safe uninstall are tested. An isolated native Codex CLI round trip proves configure, upgrade, user-replacement preservation, and installer-owned removal without touching real user configuration; a separate slow runtime proof runs two real bridge processes concurrently through one daemon with distinct Codex/Claude provenance. Agent Zero is a documented community path; actual host-driven reconnect and certification remain unproven. |
| Supply chain | Runtime dependency contract is exact; high-severity production dependency findings are resolved or release-blocked | The production lock no longer contains ChromaDB. The strict hash-locked audit reports no known vulnerabilities, closing stale GAP-029. Release archives now require a verified `SHA256SUMS` manifest. |

---

## §2 Active Release: v2.12.0 Memory Intelligence

### §2.1 Outcome

**Make persistent memory legible as a decision advantage, not a database inventory.**

The dashboard must answer one commercial product question in plain language:
what durable knowledge should shape the next agent answer, and why should a
developer trust it? The implementation remains inside the v2.11 trust boundary:
loopback-only, redacted snapshot-only, and read-only.

### §2.2 Included in the v2.12 release candidate

| Surface | Evidence |
|---------|----------|
| Product story | Briefing identifies a current durable memory and explains its evolution as assumption → evidence → decision → guard when graph relationships support it |
| Visual system | Exact repository emblem; carbon/tusk base with copper, brass, clay, and sage semantic states; no generic purple/cyan AI-gradient treatment |
| Data truth | Production `from`/`to` edges and legacy `source`/`target` fixtures normalize at the frontend boundary; backend label derives from configured store |
| Showcase | Deterministic 37-memory, 11-entity, 95-edge snapshot; every memory cites repository evidence; synthetic behavior is disclosed; user data is absent |
| Trust boundary | Dashboard remains loopback-only, redacted snapshot-only, read-only, and undeployed |
| Documentation | Snapshot reference, operator guide, script catalog, README, changelog, and this SDD/state record are synchronized |
| Installer | Host-aware selection, platform-specific launchers, and non-mutating dry-run behavior |

### §2.3 Remaining closure work

| Work | Current proof |
|------|---------------|
| Visual acceptance | The source-grounded dashboard showcase and canonical branding are complete; the website candidate supplies desktop/mobile dark/light, reduced-motion, and full Matrix-state browser evidence. Final live browser acceptance remains a post-deployment step. |
| Regression proof | Exact core candidate SHA `2c84a68` is green in PR #8 Quality (Python, dashboard, and production dependency audit). The manually dispatched exact-SHA cross-platform installer build is green on macOS, Windows, and Linux. Local proof remains 267 fast tests passed (4 legacy-backend skips), one isolated slow test passed, extracted archives and checksums passed, dashboard build/audits passed, and the strict hash-locked Python audit found no known vulnerabilities. |
| Durable handoff | PR #7 history is preserved in the no-rewrite merge on `release/v2.12.0`; [draft PR #8](https://github.com/ElefanteAI/elefante/pull/8) is the exact core review and release handoff. The dependent website handoff is [draft PR #2](https://github.com/ElefanteAI/ElefanteUI/pull/2). |
| Publication | NOT AUTHORIZED — no merge, tag, release publication, deployment, external Contact test, or live-store action. Core release must publish first; only then may the website manifest advance from v2.11.1. |

### §2.4 Approval gates

The user explicitly authorized implementation, documentation, commit, push,
and GitHub handoff for this dashboard cycle. The following remain outside that
authority:

1. Apply provenance or vector-store migrations to live user data.
2. Tag, publish a release, deploy, spend money, or contact third parties.

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
- **IMPLEMENTATION_COMPLETE:** YES LOCALLY — release-candidate content and local gates are complete; exact-SHA GitHub checks and the fresh browser screenshot remain release gates.
- **PUBLICATION_AUTHORIZED:** NO — no tag, GitHub release, or deployment.

---

## §3 Roadmap (multi-release)

### §3.1 v2.11.1 — Shipped baseline

The daemon, storage-free bridge, provenance, installer ownership, SQLite default,
and snapshot-only dashboard form the baseline described in `CHANGELOG.md`.
Unfinished trust obligations remain visible in §1.4 and `workspace/ISSUES.md`;
the dashboard work does not waive them.

### §3.2 v2.12.0 — Active release candidate

- Memory Intelligence Briefing and source-grounded showcase
- Decision Graph built from explicit memory relationships
- Exact canonical dashboard branding
- Host-aware installer selection
- Platform-specific launchers and non-mutating dry-run behavior
- SQLite-vector/Kuzu default architecture with a clean production lock

### §3.3 Upcoming (no release or date commitment)

- Expanded `elefante doctor` verification
- Automated integration-manifest drift checks
- Additional host certification and adapters
- Signed and notarized native packaging
- Proactive memory surfacing and conflict detection
- Usage intelligence
- Portable import and team synchronization

### §3.4 What does NOT justify v3.0.0

This plan stays on v2.x deliberately. v3.0.0 only justified by:

- A user-facing memory-contract break (MemoryAdd / MemorySearch argument or result-shape rewrite). **Not planned.**
- A data-model change that cannot be migrated in place. **Not planned.**
- Removal of a transport with no deprecation window. v2.11's transport change ships with `--legacy-stdio` for one release — standard semver-minor.

---

## §4 Features

### §4.1 Backlog (status: idea — not yet investigated)

This section is the source of truth for unshipped ideas. No item below carries
a release or date promise.

- **A. Memory Intelligence** — Memory Health Score (designed, not built); Potential Conflict Detection (designed, not built); Smart Update / Merge (concept only)
- **B. Proactive Retrieval** — Proactive Memory Surfacing (`surfaces_when` field exists; surfacing logic not built); Retrieval Explanation UI (backend done v2.1; frontend 0%)
- **C. Dashboard & Visualization** — Usage Intelligence aggregation remains unbuilt; the v2.12 Memory Intelligence briefing and visual-system redesign are implemented
- **D. Session Distiller Expansion** — Live Mode (designed, not built); Team Sync API (concept)
- **E. Multi-Modal & Platform** — Multi-Modal Memory (concept); additional host certification (see §3.3); Agent Zero remains a documented community path
- **F. Distribution Packaging** — Branded macOS DMG (build script done; CI wired; signing credentials pending); Branded Windows EXE (not built); Manual Fallback Path (shipped — `install.sh`/`install.bat`)

### §4.2 In design (status: draft PRD)

Each row links to the full PRD. **Authority:** the linked file is the source of truth for the PRD body; this table indexes by status.

| Feature | PRD | Status |
|---------|-----|--------|
| Phase 1 installer (downloadable bundle, stable install root) | [`workspace/proposals/installer-procedure.md`](../workspace/proposals/installer-procedure.md) | Foundation implemented; release closure pending |
| IDE integration surface (16 IDEs, daemon, Source schema) | [`workspace/proposals/ide-integration-surface.md`](../workspace/proposals/ide-integration-surface.md) | Runtime/adapters implemented; additional certification upcoming |
| Session intelligence (privacy-respecting telemetry) | [`workspace/proposals/session-intelligence.md`](../workspace/proposals/session-intelligence.md) | DRAFT |
| Retrieval effectiveness (per-memory provenance + helpfulness) | [`workspace/proposals/retrieval-effectiveness.md`](../workspace/proposals/retrieval-effectiveness.md) | DRAFT (sketch only) |
| Memory identity | [`workspace/proposals/memory-identity.md`](../workspace/proposals/memory-identity.md) | DRAFT |

### §4.3 Active (status: shipping)

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

**Next:** keep both draft PRs unmerged until the owner has reconciled the
Vercel deployment source, prepared the Contact mail/CAPTCHA configuration, and
explicitly authorized the core release. Publish the core tag and installers
first; verify downloaded assets; then advance, merge, and deploy the exact
green website candidate.

### §4.4 Shipped (status: shipped — link to reference)

| Feature | Shipped in | Reference |
|---------|------------|-----------|
| Token Intelligence Layer (per-call TOKEN_STATS, type budgets, density warnings) | v2.5.0 | [`docs/reference/token-intelligence.md`](../docs/reference/token-intelligence.md) |
| 5-signal scoring (vector / concept / co-activation / authority / temporal) | v2.7.0 (post BUG-016/017/018) | [`docs/reference/scoring.md`](../docs/reference/scoring.md) |
| 16 MCP tools + 2 prompts | v2.10.0+ | [`docs/reference/tools.md`](../docs/reference/tools.md) |
| Compliance Gate (search before write) | v2.0.0+ | [`docs/reference/architecture.md`](../docs/reference/architecture.md) §Compliance Gate |
| Memory Intelligence dashboard with live-computed scores | v2.12.0 candidate | [`docs/reference/dashboard-snapshot.md`](../docs/reference/dashboard-snapshot.md) |
| Transaction-scoped Kuzu locking | v1.1.0 | [`docs/reference/architecture.md`](../docs/reference/architecture.md) §Transaction-Scoped Locking |

### §4.5 Rejected (status: rejected — do not re-litigate)

The active scope guard is §2.5. Historical rejected alternatives remain in the
v2.10.0 journal and changelog; reopen only with new user or retrieval evidence.

---

## §5 Optimization

### §5.1 Active blockers

See the release blockers in §2.3.

### §5.2 Performance / efficiency improvements

| Area | Status | Reference |
|------|--------|-----------|
| Token-budget enforcement per memory type | SHIPPED v2.5.0 | `docs/reference/architecture.md` §Token Intelligence |
| Co-activation persistence across restarts | SHIPPED v2.7.0 (BUG-018 fix) | `workspace/postmortems/memory.md` Issue #13 |
| Smoothed vector baseline (composite_score floor) | SHIPPED v2.7.0 | `docs/reference/architecture.md` §Cognitive Multi-Signal Scoring |
| Intent-gated specification override | SHIPPED v2.7.0 (BUG-017 fix) | `workspace/postmortems/memory.md` Issue #12 |
| ChromaDB query-with-where workaround | SHIPPED v2.9.0 (BUG-022 fix) | `workspace/postmortems/memory.md` Issue #14 |

### §5.3 Planned optimization work

(None during the Trust Release; correctness and release gates take priority.)

---

## §6 Ops Plans

### §6.1 Active operational concerns

| Concern | Status | Owner |
|---------|--------|-------|
| Live provenance backfill | Dry-run proven; apply intentionally not run | Explicit user authorization |
| Existing legacy Chroma-store transition | Isolated migration proof passes; no live legacy store was opened or changed | Explicit user authorization |
| Release formation | Test-green uncommitted candidate | Version audit, cohesive commits, release authorization |

### §6.2 Operational improvements upcoming

- `elefante doctor` extended scope for full self-protocol coverage
- Host-driven certification runs for each advertised compatible adapter

### §6.3 Operational reference (already shipped)

- Backup: `scripts/lifecycle/backup_elefante_data.py`
- Restore: `scripts/lifecycle/restore_elefante_data.py`
- Restart: `scripts/lifecycle/restart_elefante.py`
- Factory reset: `scripts/lifecycle/reset_factory.py`

Reference: [`docs/how-to/`](../docs/how-to/).

### §6.4 Hermes integration (live 2026-05-02)

**Status:** Wired. The historical Hermes verification predated the 16-tool atomic surface consolidation; current inventory is source-derived by `scripts/ci/list_mcp_tools.py`.

**Wiring (user-side, persistent in `~/.hermes/config.yaml`):**

```yaml
mcp_servers:
  elefante:
    command: /Volumes/OWC2TB/2026-M5/AI Projects/elefante/.venv/bin/python
    args: [-m, src.mcp.server]
    env:
      PYTHONPATH: /Volumes/OWC2TB/2026-M5/AI Projects/elefante
    enabled: true
```

**Why this shape:** stdio transport (no daemon yet — that ships v2.11.0 per §3.2). `PYTHONPATH` env satisfies `python -m src.mcp.server` from any CWD; no wrapper script needed (Documentation Skill: existing entry point sufficient).

**Prerequisite installed:** `mcp` SDK pinned in Hermes's uv-managed venv (`uv pip install --python <hermes-venv>/bin/python mcp` → `mcp==1.27.0`). Hermes treats `mcp` as optional; without it, `hermes mcp test` raises `StdioServerParameters not defined`.

**Known limitation (closes with v2.11.0):** stdio-per-client means every Hermes session spawns its own Elefante subprocess and competes with any IDE-attached instance for the Kuzu single-writer lock. This is **GAP-025** — closure is the v2.11.0 daemon work. Until then, run Hermes and IDE Elefante sessions sequentially, not concurrently.

**Closes the loop:** Hermes is now Elefante's first non-IDE consumer. Every Hermes session reads/writes through the live MCP surface, exercising the Closed Surface Map under real load — the measurement that makes the v2.10.0 → v2.11.0 restructure decisions empirical, not imagined.

**Verification command:** `cd hermes-agent && .venv/bin/hermes mcp test elefante` — must show all 20 `elefante-*` tools.

#### §6.4.1 GAP-028 — Hermes LLM provider configuration (OPEN, user decision)

**Tracked in:** [`workspace/ISSUES.md`](../workspace/ISSUES.md) GAP-028 row.

**Current state (factual, from `hermes status`):**
- `Model: (not set)` · `Provider: Auto` · `.env file: ✗ not found`
- Native API keys checked: OpenRouter ✗ · OpenAI ✗ · NVIDIA ✗ · Z.AI/GLM ✗ · Kimi ✗ · StepFun ✗ · MiniMax ✗ · MiniMax-CN ✗ · Firecrawl ✗ · Tavily ✗ · Browser Use ✗ · Browserbase ✗
- Until at least one is set, `hermes -z "..."` cannot invoke an LLM agent loop. Hermes is wired to Elefante (Layers 1+2) but cannot **engage** Elefante (Layer 3 from the Hermes side).

**User intent (2026-05-02):** route certain tasks through DeepSeek.

**Decision matrix — DeepSeek access paths:**

| Path | How | Pros | Cons |
|------|-----|------|------|
| **A. Direct DeepSeek (Hermes-native, RECOMMENDED)** | Set `DEEPSEEK_API_KEY` in `~/.hermes/.env`; pick model: `deepseek-v4-pro` / `deepseek-v4-flash` / `deepseek-r1` / `deepseek-chat`. Hermes recognizes `DEEPSEEK_API_KEY` + `DEEPSEEK_BASE_URL` natively (verified in `hermes_cli/config.py` `OPTIONAL_ENV_VARS`). | Lowest latency; direct billing; native provider routing in Hermes; no middleman | Single-provider; pair with fallback if outage resilience matters |
| **B. OpenRouter (multi-provider through one key)** | Set `OPENROUTER_API_KEY` in `~/.hermes/.env`; pick model: `deepseek/deepseek-chat` or `deepseek/deepseek-r1`. | One key, many models; built-in fallbacks; aggregate billing | Extra network hop; OpenRouter pricing markup |
| **C. Hybrid — DeepSeek primary + OpenRouter fallback** | Both keys set; `~/.hermes/config.yaml` `fallback_providers:` lists OpenRouter | Best resilience; covers rate limits and DeepSeek outages | Two API keys to manage |

**Task-routing options (which DeepSeek model for what):**

| Task type | DeepSeek model | Why |
|-----------|----------------|-----|
| Long-context code reasoning | `deepseek-chat` (V3) | 128K context, strong on code |
| Deep reasoning / planning | `deepseek-reasoner` (R1) | Reasoning trace; better at multi-step decomposition |
| Cheap routine completion | `deepseek-chat` (V3) | Lowest $/M tokens in DeepSeek line |

**Hermes task-routing mechanism (existing):** `~/.hermes/config.yaml` supports `fallback_providers:` for failover. Per-task model selection requires either (a) per-toolset model override (Hermes feature — verify in Hermes docs) or (b) explicit `--model` flag on each `hermes -z "…"` call. Pick A or C above; pin task→model mapping in CLI helper if needed.

**User-side action to close GAP-028 (one paste, one verifier run):**

State as of 2026-05-02 (already done by agent — no action needed):
- `~/.hermes/.env` created (chmod 600) with `DEEPSEEK_API_KEY=` line ready for paste
- `~/.hermes/config.yaml` set to `model: deepseek-v4-flash` (smaller / faster; user preference 2026-05-02)
- `hermes status` confirms `Model: deepseek-v4-flash`, `Provider: DeepSeek`, `.env file exists`
- Verifier script at `/tmp/elefante-gap-028-verify.py` (Layer 0+1+2+3 round-trip test)

What you do — single edit + single verify:

```bash
# 1. Paste your DeepSeek API key into the existing line in ~/.hermes/.env
#    Get key from: https://platform.deepseek.com/api_keys
$EDITOR ~/.hermes/.env       # set DEEPSEEK_API_KEY=sk-... after the existing `=`

# 2. (Optional) Swap model in ~/.hermes/config.yaml line 1:
#    deepseek-v4-flash     (default — fastest, smallest, lower cost)
#    deepseek-v4-pro       (best reasoning, higher cost)
#    deepseek-r1 / deepseek-reasoner   (reasoning trace)
#    deepseek-chat / deepseek-v3       (general)

# 3. Verify the loop closes end-to-end
cd "/Volumes/OWC2TB/2026-M5/AI Projects/hermes-agent"
.venv/bin/python /tmp/elefante-gap-028-verify.py
# Expected: Layer 0 PASS, Layer 1+2 PASS, Layer 3 PASS, "=== GAP-028: CLOSED ==="
```

**Acceptance for GAP-028 closure:** Verifier reports Layer 3 PASS — Hermes called `elefante-MemorySearch` and surfaced memory id `f1fb77f5` (the Workflow Lifecycle memory). At that point the recursive Hermes <-> Elefante loop is closed for the first time **from the Hermes side**, not just Claude Code.

**Architect recommendation:** **Path A (Direct DeepSeek)** for first close — Hermes natively supports `DEEPSEEK_API_KEY`, lowest latency, no OpenRouter detour. Add Path C (hybrid) later only if outage resilience becomes a real concern.

---

## §7 Dev Process Plans

### §7.1 Constitution + Documentation Skill (current)

- [`agents/orchestrator.md`](../agents/orchestrator.md) — single canonical developer constitution. Loop, Five Gates, Memory Janitor Mandate, Documentation Skill (Closed Surface Map, Forbidden Patterns, Pre-write checklist, New-File Test, Failure Conditions, Lifecycle), Embedding Rule, Modes, Compendium Trigger Map, DEVELOPER/RESEARCH Routing, Closure Sequence, Where Things Live, Specialist Handoffs, Critical Thinking, Changelog Contract, Never list. ~270 LOC. Merged from the deleted full constitution + previous loadable orchestrator on 2026-05-02 (Phase B of agentic restructure).
- [`agents/*.md`](../agents/) — 10 specialist protocols + glossary.

### §7.2 Active enforcement

- [`tests/test_developer_routing.py`](../tests/test_developer_routing.py) — 18 tests passing; BUG-007 routing drift guards + BUG-026 forbidden-filename-pattern guard.

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

### §8.2 UX backlog (no canonical home until §4.1 backlog absorbs)

- Health indicators on graph nodes (idea)
- Rich tooltips on signal hubs (idea)
- Live mode for session distiller (idea)

### §8.3 Open UX decisions

- Whether `docs/user/` should grow proactively or wait for v2.11+ (currently 35 LOC — almost empty)

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
| Active doc LOC (post-curation) | 9,841 | `find ... -name "*.md" \| xargs wc -l` | Tracked |
| Archived doc LOC (preservation) | 3,815 | `wc -l workspace/*/_archive/*.md` | Tracked |
| Postmortem LOC reduction | 5,024 → 1,681 (66%) | per-file before/after | Tracked |
| BUG count tracked | **32 (BUG-001 → BUG-032) + 4 GAPs** | `workspace/ISSUES.md` | Tracked |
| BUG recurrence rate (pre-distillation) | known per-row in `ISSUES.md` | `workspace/ISSUES.md` Recurrence column | Tracked |
| BUG recurrence rate (post-distillation) | unknown — needs sustained agent traffic across sessions | will derive from `ISSUES.md` Recurrence column after v2.10.x lands real workload | **NOT MEASURED YET** |
| Hermes Elefante-tool retrieval count | **GAP-028 CLOSED 2026-05-02.** Direct ingestion (Claude-Code-as-MCP-client): 9 lessons submitted, 6+ stored unique, 3 fused via Compliance Gate dedupe; 19 directives total in store. Hermes-as-LLM-agent (deepseek-v4-flash) Layer-3 round-trip surfaced lifecycle memory `f1fb77f5` with verbatim content match + auto-injected directive on every MCP response. **Recursive Hermes <-> Elefante loop alive on the Hermes side.** | `/tmp/elefante-gap-028-verify.py` (Layer 0/1+2/3 PASS); `/tmp/elefante-self-ingest*.py` for direct ingestion | **MEASURED** |
| Active guard test count | 20 passing | `pytest tests/test_developer_routing.py` | Tracked |
| Token cost per `MemorySearch` (signal_ratio) | TOKEN_STATS injected per response | `src/mcp/server.py` | Available; not aggregated yet |
| Documentation Skill compliance % (BUG-026 derivative) | Filename-pattern guard active (`test_no_forbidden_filename_patterns_*`); broader-surface compliance metric not designed yet — deferred to v2.11+ pre-edit hook architecture per BUG-027 | filename guard runs in CI | **DEFERRED (by plan, not unmeasured)** |

The "not measured yet" rows are this session's open obligations to the journal. Until Hermes runs and agent traffic flows through the distilled memories, the curation's downstream effect is hypothesis, not measurement.

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
