---
status: living
last_updated: 2026-05-02
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

Source-of-truth: [`docs/explanation/vision.md`](../docs/explanation/vision.md) §Non-Goals.

---

## §2 Active Release: v2.10.0

### §2.1 Theme

**v2.10.0 = Contract release. Theme: "Elefante becomes agent-legible."**

Not smaller. Not simpler internally. **More legible externally.** Five legibility moves accepted; nothing shipped that changes how Elefante stores or scores memory. Architectural safety move (singleton daemon + Source schema, GAP-025 closure) explicitly held for v2.11.0.

### §2.2 Three release tracks

| Version | Theme | Risk |
|---------|-------|------|
| **v2.10.0** | Contract release — agent-legibility surface | Low. Doc/spec + (P-gated) one minimal CLI piece. **Nothing in v2.10.0 is unconditionally committed until P1–P6 close** (§2.6). No runtime change to MCP tool surface, scoring, or storage. |
| **v2.10.x** | Small runtime improvements implementing the v2.10.0 contract | Medium. `elefante-Remember` and explanation-object emission land here. |
| **v2.11.0** | Daemon + Source schema + GAP-025 closure | High. Documented in §3 Roadmap. **Protected** from v2.10.0 scope creep. |

### §2.3 ACCEPTED into v2.10.0 (A-series)

| # | Decision |
|---|----------|
| A1 | v2.10.0 = contract release; theme "Elefante becomes agent-legible" |
| A2 | v2.10.0 stays additive; existing 20 MCP tools preserved |
| A3 | v2.10.x = small runtime improvements only |
| A4 | v2.11.0 = daemon + Source schema + GAP-025 closure; protected line |
| A5 | Add `elefante-Remember` curated write primitive (search evidence visibly returned) |
| A6 | Public retrieval explanation object (versioned `explanation_schema: 1`) |
| A7 | `elefante doctor` + `elefante status` CLI; **drop** `elefante mcp` |
| A8 | Skill index-card contract — metadata/path/score/graph links, **not** skill bodies |
| A9 | Hermes generalized as skill-bearing agent client; no special profile |
| A10 | Hold GAP-025 line; no facade enthusiasm distracts from daemon work |

### §2.4 IN DEVELOPMENT (D-series, P-gated)

> Each D-item is conditionally planned. Each is blocked by its corresponding P-item in §2.6. Until those decisions close, **no D-item is unconditionally committed**.

| # | Artifact | Lands in | Implementation? |
|---|----------|----------|-----------------|
| D1 | `elefante-Remember` spec entry tagged `STATUS: PLANNED — v2.10.x` | `docs/reference/tools.md` | No (spec only); **gated on P1=YES** |
| D2 | Public explanation object schema `explanation_schema: 1` | `docs/reference/tools.md` | No (spec only); **gated on P1=YES** |
| D3 | `_CONTEXT_SKIP_TOOLS` rule for `elefante-Remember` | `docs/reference/tools.md` | No (spec only) |
| D4 | Skill index-card contract + adapter enforcement clause | `workspace/proposals/ide-integration-surface.md` | No (contract only) |
| D5 | `ide-integration-matrix.yaml` v0 with fresh hashes | `agents/manifests/ide-integration.yaml` | **Done as scaffold 2026-05-02**; integration-inspector run pending; gated on P3 for hash refresh |
| D6 | `elefante doctor` + `elefante status` minimal CLI | `setup.py` console_scripts + new module | Minimal CLI runtime; **gated on P2=YES** |
| D7 | `CHANGELOG.md` v2.10.0 entry | `### Added` / `### Changed` / `### Removed` | In progress (each major change gets its `### Added` / `### Changed` / `### Removed` row at edit time) |
| D8 | Acceptance test for "agent-legible" theme | `verify_e2e_tests.py` | Smoke assertion only; **gated on P5=YES** |

### §2.5 PARKED (X-series, rejected — do not re-litigate without new evidence)

| # | Proposal | Why rejected |
|---|----------|--------------|
| X1 | 3-tool facade replacing 20 MCP tools | Lossy hidden routing; doubles maintenance; breaks Compliance Gate visibility; Tasks/ETL not memory primitives |
| X2 | lite/standard/full storage modes | v3.0.0 break (storage forbidden in v2.10.0); real cost is sentence-transformers; default-embedding swap silently corrupts retrieval |
| X3 | Scoring profiles (per-domain weights) | Reproducibility break; weights already empirically validated by BUG-016/017/018 |
| X4 | `confidence: 0.87` on writes | Undefined semantics; "Never (1) Guess a formula" |
| X5 | strict/suggest/automatic write modes | Three failure surfaces; no real simplification; gate is binary by design |
| X6 | Hermes-specific profile | Insufficient evidence; generic skill-bearing-client treatment is sufficient |

Re-open thresholds: see [`workspace/PLANNING.md §2.5`](../workspace/PLANNING.md §2.5). **Do not re-litigate without new evidence.**

### §2.6 PENDING (P-series — open, awaiting user answer)

| # | Question | Architect recommendation | Blocks |
|---|----------|---------------------------|--------|
| P1 | Spec-without-code OK? Ship `STATUS: PLANNED` tag in v2.10.0; implementation in v2.10.x. | YES | D1, D2 |
| P2 | Drop `elefante mcp` from CLI; keep only `doctor` + `status`. | YES | D6 |
| P3 | Run integration-inspector once before v2.10.0 cuts to refresh `ide-integration-matrix.yaml` hashes. | YES | D5 hash refresh |
| P4 | ~30 uncommitted pre-v2.10.0 files: ship as `chore: archive purge` ahead, or fold into v2.10.0? | AHEAD (one concern per commit per `dev-etiquette §4`) | Commit order |
| P5 | Acceptance test = "explanation field present in `verify_e2e_tests`"? | YES | D8 |
| P6 | Commit sequence: `chore: archive purge` → surface split → spec amendments → matrix → CLI → version bump? | YES | Cut-time |
| P7 | Approve [`workspace/proposals/tool-consolidation.md`](../workspace/proposals/tool-consolidation.md) for v3.0.0 inclusion + v2.11.0 alongside-deployment? Surface 20 → 6 domain-grouped tools with action discriminator. Architecturally distinct from rejected X1 (explicit action param, per-domain tools, Tasks/ETL stay separate). Acceptance: ≥50% drop in tool-schema overhead per MCP response (measure via `TOKEN_STATS`); behavioral parity with v2.x; Hermes round-trip verified. | YES | v3.0.0 cut |

P1–P6 are open. **The architect's recommendations are not accepted defaults; user must answer.**

### §2.7 GAP-025 protection (explicit)

GAP-025 (multi-instance write origin tracking, [`workspace/postmortems/memory.md`](../workspace/postmortems/memory.md) Issue #15) closure is the **architectural safety move** for v2.11.0. It is **not** a v2.10.0 work item and **must not** be diluted by:

- Tool-surface cosmetics (rejected facade — see X1)
- Storage tier changes (rejected lite/standard/full — see X2)
- Scoring tunability work (rejected profiles — see X3)
- Write-mode multiplication (rejected strict/suggest/automatic — see X5)

The right v2.10.0 contract for any of these concerns is to **describe the right shape** in spec form and let v2.11.0 implement it on top of the daemon.

### §2.8 What v2.10.0 explicitly does NOT ship

- `elefante-Remember` runtime — deferred to v2.10.x
- Public explanation object emission (runtime path) — deferred to v2.10.x
- Singleton daemon — deferred to v2.11.0
- `(:Memory)-[:WRITTEN_BY]->(:Source)` schema migration — deferred to v2.11.0
- Six verified IDE adapters — deferred to v2.11.0
- `--legacy-stdio` escape hatch — deferred to v2.11.0
- integration-inspector CI cron — deferred to v2.12.0
- `elefante doctor` extended to full self-protocol scope — deferred to v2.12.0
- Phase 3 IDE surfaces (Cline, Roo, Kilo, Continue, Windsurf, Trae, Aider) — deferred to v2.12.0

### §2.9 Workspace blockers (OB-series, canonical here only)

P-decisions live in §2.6; BUG/GAP rows live in [`workspace/ISSUES.md`](../workspace/ISSUES.md); this table holds workspace state that is **not** captured elsewhere.

| ID | Blocker | Required decision/fix |
|----|---------|------------------------|
| OB4 | Archive purge `### Removed` records in `CHANGELOG.md` incomplete: 3 `### Removed` sections cover 3 named scripts + 8 named archive files + 4 merged scripts; `git status` shows ~20 deletions in `docs/archive/*` and ~3 in `scripts/*`. **At least 12 archive deletions lack records.** | Audit `git status -- docs/archive/ scripts/` against existing `### Removed` entries; backfill missing entries before any commit ships archive purge. |
| OB5 | Stale `Last verified:` dates in `workspace/ISSUES.md:145`, `workspace/postmortems/ai-behavior.md:1041`, `docs/how-to/run-mcp-server.md:469`, plus 4 untouched compendiums | Either re-run verifications and update, or accept staleness explicitly. Do not change "Last verified" without running verification. |

> **Closed (history retained one cycle):**
> - **OB1** (2026-05-02): `src/core/orchestrator.py` diff reviewed — single-line embedded-spec doc-reference update; routes to Bucket D
> - **OB3** (2026-05-02): `spec-memory-identity.md` indexed in `docs/technical/README.md`
> - **OB6** (2026-05-02): `docs/README.md` v2.10.0-tier entries added
> - **OB7** (2026-05-02): `docs/technical/README.md` Last Updated current
> - **OB8** (2026-05-02): `docs/technical/README.md` tool count `21` → `20`

### §2.10 Resume verdict

- **RESUME_SAFE:** YES — full state captured here in §2.3–§2.9, in [`workspace/ISSUES.md`](../workspace/ISSUES.md) for BUGs/GAPs, in [`agents/orchestrator.md`](../agents/orchestrator.md) for constitution+Documentation Skill, in [`agents/manifests/ide-integration.yaml`](../agents/manifests/ide-integration.yaml) for integrations.
- **PRODUCTION_READY:** NO — gated on P1–P6 closure (§2.6) + BUG-026 active guard candidate selection ([`workspace/postmortems/ai-behavior.md`](../workspace/postmortems/ai-behavior.md) Issue #12 Solution candidates 2 and 3) + OB4 + OB5.

---

## §3 Roadmap (multi-release)

### §3.1 v2.10.x — small runtime improvements

Implement what v2.10.0 contract spec'd:

- `elefante-Remember` runtime (D1)
- Public explanation object emission (D2, D3)
- (no breaking changes; all additive)

### §3.2 v2.11.0 — Daemon + Source schema + 6 adapters (closes GAP-025)

Per [`workspace/proposals/ide-integration-surface.md §15`](../workspace/proposals/ide-integration-surface.md):

| Step | Work |
|------|------|
| 1 | Author/refresh `agents/manifests/ide-integration.yaml` (scaffolded 2026-05-02; hash refresh pending) |
| 2 | Singleton daemon (launchd / systemd-user / Windows-equivalent) over streamable-http on `127.0.0.1:<port>` |
| 3 | `(:Memory)-[:WRITTEN_BY]->(:Source)` schema + idempotent migration |
| 4 | Claude Code adapter (lowest risk) |
| 5 | VS Code Copilot adapter (highest reach) |
| 6 | Cursor, Bob, Kiro adapters |
| 7 | Universal `AGENTS.md` root-file emission (covers Codex, Zed, Cline, Roo, Kilo via convergence point #3) — **partially done as of 2026-05-02 with the new repo-root `AGENTS.md`** |
| 8 | Detect→emit installer + uninstall manifest at `~/.elefante/install-manifest.json` |
| 9 | `--legacy-stdio` escape hatch (deprecated on land; removed v2.12) |

**Acceptance gates** (all required before v2.11.0 cuts):

- All `scripts/verify/*` green
- `test_memory_persistence.py` + `test_memory_guard.py` pass on fresh DB **and** on migrated legacy DB
- Two concurrent IDE instances produce distinct `source.instance_id` values with zero Kuzu lock contention
- Per-adapter `emit_skill` / `emit_rules` / `emit_mcp` dry-run diff reviewed against the live vendor doc at ship time
- CHANGELOG `### Removed` entries exist for every dropped path or command

### §3.3 v2.12.0 — inspector CI + Phase 3 surfaces

- integration-inspector CI cron (weekly drift audit)
- `elefante doctor` extended to full self-protocol
- Matrix versioning + pinning
- Phase 3 IDE surfaces (Cline, Roo, Kilo, Continue, Windsurf, Trae, Aider)
- `--legacy-stdio` flag removal

### §3.4 What does NOT justify v3.0.0

This plan stays on v2.x deliberately. v3.0.0 only justified by:

- A user-facing memory-contract break (MemoryAdd / MemorySearch argument or result-shape rewrite). **Not planned.**
- A data-model change that cannot be migrated in place. **Not planned.**
- Removal of a transport with no deprecation window. v2.11's transport change ships with `--legacy-stdio` for one release — standard semver-minor.

---

## §4 Features

### §4.1 Backlog (status: idea — not yet investigated)

Source-of-truth: [`docs/explanation/vision.md §A–§F`](../docs/explanation/vision.md) "Ideas Backlog". Categories:

- **A. Memory Intelligence** — Memory Health Score (designed, not built); Potential Conflict Detection (designed, not built); Smart Update / Merge (concept only)
- **B. Proactive Retrieval** — Proactive Memory Surfacing (`surfaces_when` field exists; surfacing logic not built); Retrieval Explanation UI (backend done v2.1; frontend 0%)
- **C. Dashboard & Visualization** — Usage Intelligence (backend 80%; snapshot pipeline +1 field; frontend 0%); Dashboard UX improvements (designed, not built)
- **D. Session Distiller Expansion** — Live Mode (designed, not built); Team Sync API (concept)
- **E. Multi-Modal & Platform** — Multi-Modal Memory (concept); Cross-IDE Support (MCP works universally; per-IDE setup varies — see §3.2 v2.11 plan); Agent Zero Integration (target documented; not built)
- **F. Distribution Packaging** — Branded macOS DMG (build script done; CI wired; signing credentials pending); Branded Windows EXE (not built); Manual Fallback Path (shipped — `install.sh`/`install.bat`)

### §4.2 In design (status: draft PRD)

Each row links to the full PRD. **Authority:** the linked file is the source of truth for the PRD body; this table indexes by status.

| Feature | PRD | Status | Target |
|---------|-----|--------|--------|
| Phase 1 installer (downloadable bundle, stable install root) | [`workspace/proposals/installer-procedure.md`](../workspace/proposals/installer-procedure.md) | DRAFT — Phase 1 only | Pre-v2.10.0 / v2.10.x |
| IDE integration surface (16 IDEs, daemon, Source schema) | [`workspace/proposals/ide-integration-surface.md`](../workspace/proposals/ide-integration-surface.md) | DRAFT (docs in v2.10.0; impl v2.11+) | v2.11.0 + v2.12.0 |
| Session intelligence (privacy-respecting telemetry) | [`workspace/proposals/session-intelligence.md`](../workspace/proposals/session-intelligence.md) | DRAFT | v2.11.0 (depends on Source schema) |
| Retrieval effectiveness (per-memory provenance + helpfulness) | [`workspace/proposals/retrieval-effectiveness.md`](../workspace/proposals/retrieval-effectiveness.md) | DRAFT (sketch only) | v2.11.x or v2.12.x |

### §4.3 Active (status: shipping)

Active development = the v2.10.0 contract scope itself (see §2). No other features are in active build at this moment.

### §4.4 Shipped (status: shipped — link to reference)

| Feature | Shipped in | Reference |
|---------|------------|-----------|
| Token Intelligence Layer (per-call TOKEN_STATS, type budgets, density warnings) | v2.5.0 | [`docs/reference/token-intelligence.md`](../docs/reference/token-intelligence.md) |
| 5-signal scoring (vector / concept / co-activation / authority / temporal) | v2.7.0 (post BUG-016/017/018) | [`docs/reference/scoring.md`](../docs/reference/scoring.md) |
| 20 MCP tools + 2 prompts | v2.0.0+ | [`docs/reference/tools.md`](../docs/reference/tools.md) |
| Compliance Gate (search before write) | v2.0.0+ | [`docs/reference/architecture.md`](../docs/reference/architecture.md) §Compliance Gate |
| Dashboard with live-computed scores | v2.4.0 (BUG-004 fix) | [`docs/reference/dashboard-snapshot.md`](../docs/reference/dashboard-snapshot.md) |
| Transaction-scoped Kuzu locking | v1.1.0 | [`docs/reference/architecture.md`](../docs/reference/architecture.md) §Transaction-Scoped Locking |

### §4.5 Rejected (status: rejected — do not re-litigate)

See §2.5 for the X-series. Each carries a re-open threshold per [`workspace/PLANNING.md §2.5`](../workspace/PLANNING.md §2.5).

---

## §5 Optimization

### §5.1 Active blockers (OB-series — canonical in §2.9)

See §2.9.

### §5.2 Performance / efficiency improvements

| Area | Status | Reference |
|------|--------|-----------|
| Token-budget enforcement per memory type | SHIPPED v2.5.0 | `docs/reference/architecture.md` §Token Intelligence |
| Co-activation persistence across restarts | SHIPPED v2.7.0 (BUG-018 fix) | `workspace/postmortems/memory.md` Issue #13 |
| Smoothed vector baseline (composite_score floor) | SHIPPED v2.7.0 | `docs/reference/architecture.md` §Cognitive Multi-Signal Scoring |
| Intent-gated specification override | SHIPPED v2.7.0 (BUG-017 fix) | `workspace/postmortems/memory.md` Issue #12 |
| ChromaDB query-with-where workaround | SHIPPED v2.9.0 (BUG-022 fix) | `workspace/postmortems/memory.md` Issue #14 |

### §5.3 Planned optimization work

(None scheduled before v2.11.0; daemon work is architectural correctness, not performance optimization. Performance work resumes after Source schema lands.)

---

## §6 Ops Plans

### §6.1 Active operational concerns

| Concern | Status | Owner |
|---------|--------|-------|
| Archive purge `### Removed` audit before v2.10.0 cut | OB4 (open) — see §2.9 | Pending P4 closure |
| Stale `Last verified` dates | OB5 (open) — see §2.9 | Pending verification re-runs |

### §6.2 Operational improvements planned

- `elefante doctor` + `elefante status` CLI (D6, gated on P2) — wraps existing `verify_*.py` scripts; one-command operator surface
- `elefante doctor` extended scope (v2.12.0) — full self-protocol coverage
- Singleton daemon launchd/systemd integration (v2.11.0)

### §6.3 Operational reference (already shipped)

- Backup: `scripts/lifecycle/backup_elefante_data.py`
- Restore: `scripts/lifecycle/restore_elefante_data.py`
- Restart: `scripts/lifecycle/restart_elefante.py`
- Factory reset: `scripts/lifecycle/reset_factory.py`

Reference: [`docs/how-to/<name>.md`](../docs/technical/) (9 ops files).

### §6.4 Hermes integration (live 2026-05-02)

**Status:** Wired. `hermes mcp list` reports `elefante ✓ enabled` with all 20 tools discovered.

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
- ✓ `~/.hermes/.env` created (chmod 600) with `DEEPSEEK_API_KEY=` line ready for paste
- ✓ `~/.hermes/config.yaml` set to `model: deepseek-v4-flash` (smaller / faster; user preference 2026-05-02)
- ✓ `hermes status` confirms `Model: deepseek-v4-flash`, `Provider: DeepSeek`, `.env file: ✓ exists`
- ✓ Verifier script at `/tmp/elefante-gap-028-verify.py` (Layer 0+1+2+3 round-trip test)

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
# Expected: Layer 0 PASS, Layer 1+2 PASS, Layer 3 PASS, "=== GAP-028: CLOSED ✓ ==="
```

**Acceptance for GAP-028 closure:** Verifier reports Layer 3 PASS — Hermes called `elefante-MemorySearch` and surfaced memory id `f1fb77f5` (the Workflow Lifecycle memory). At that point the recursive Hermes ↔ Elefante loop is closed for the first time **from the Hermes side**, not just Claude Code.

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

### §7.4 Open dev process decisions

- Whether to merge `agents/orchestrator.md` + `agents/orchestrator.md` into a single canonical constitution (Phase B of agentic restructure; deferred to next session). (Not P-tracked yet.)

---

## §8 UX Plans

### §8.1 Currently tracked UX concerns

- DMG installer customer surface — FIXED v2.9.0 (BUG-020); guarded by widget-tree check + manual screenshot
- Installer failure recovery routing — FIXED (BUG-019 / BUG-020 closure); persisted summary/status/log files surfaced in installer GUI
- Dashboard blank-on-first-launch — FIXED v2.8.x (BUG-003); readiness wait + forced restart on refresh + frontend retry/backoff

### §8.2 UX backlog (no canonical home until §4.1 backlog absorbs)

- Dashboard UX color-by-memory-type (idea)
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
| 2026-05-02 | **GAP-028 CLOSED.** User pasted DeepSeek API key into `~/.hermes/.env` (rotation pending — key was exposed in chat). Verifier `/tmp/elefante-gap-028-verify.py` reported Layer 0+1+2+3 PASS. First Layer-3 round-trip ran on `deepseek-v4-pro`; subsequently swapped to `deepseek-v4-flash` per user preference (smaller/faster) and re-verified — both surfaced memory id `f1fb77f5` with verbatim content match against the Workflow Lifecycle memory ingested earlier this session. Hermes (running v4-flash) synthesized: "The directive containing this lifecycle is also repeated inline in every Elefante tool response as a permanently injected directive" — proving BOTH the memory body AND the auto-injected directive surface (BUG-006 fix working). | "Close GAP-028 first" + user pasted key + "deepseek should be not with pro version. keep it on the smaller model." | **The recursive Hermes ↔ Elefante memory loop closed for the first time from the Hermes side, not just Claude Code.** Real Layer-3 engagement on `deepseek-v4-flash`. Loop is now a measurable consumer surface. |
| 2026-05-02 | **Documentation-as-journal pattern validated** (this turn). Session produced ~14k LOC of doc work + 6+ ingested memories + 3 directives + 1 Layer-3 Hermes engagement. The 11-step Lifecycle closed multiple times during the session, each ending with a JOURNAL row. Observed: journal made decisions retrievable across the conversation (e.g. Hermes purpose pulled from §6.4 + §10 + memory `f5e15250`); exposed simulation when projection slipped in ("Hermes will load…" without Hermes having run); recorded failure modes (BUG-026 3x recurrences, BUG-027 1033-LOC loss) that would otherwise repeat in next session; proved Elefante's engine works on its own development trace via memory `f1fb77f5` round-trip through DeepSeek. | "learning, how we use the documentation as journal" — user reflective challenge | The journal is **the mechanism by which work compounds across sessions**. Without it, every cycle is a draft. With it, every cycle is a deposit. Discipline cost: every cycle ends with INGEST + JOURNAL + COMMIT. Returns: session continuity, simulation detection, recurrence prevention, dogfood proof. |
| 2026-05-02 | **Memory tool consolidation atomic swap COMPLETE.** Tool count 20 → 16. 5 legacy memory tools (`MemoryAdd` / `MemorySearch` / `MemoryUpdate` / `MemoryDelete` / `MemoryConsolidate`) deleted in same atomic change that introduced `elefante-Memory` with discriminated `action` param. Hermes audit (deepseek-v4-flash) before surgery caught 7 prep items including a silent Compliance Gate regression that I'd have shipped solo — I revised the plan based on the audit (gate stays internally name-keyed via handler-side calls; only error messages updated). Files touched: `src/mcp/server.py` (tool def + dispatcher + 5 system updates), `scripts/verify/verify_e2e_tests.py` (EXPECTED_TOOLS + 13 call sites + grounding check), `tests/test_memory_persistence.py` (2 call sites), `scripts/setup/configure_antigravity.py` + `configure_vscode_bob.py` (IDE allowlists), `README.md` + `docs/README.md` + `docs/reference/tools.md` (counts). Hermes confirms post-swap: 16 tools visible, `elefante-Memory` first listed, full discriminated description retrievable. 18/18 guards green throughout. | "i need to consolidate the tools." + "do it now end-to-end multi-step" + Hermes audit findings | **First successful tool surface consolidation in Elefante history. Lesson learned earlier same day (alongside-deployment is theater) prevented this from being another reverted attempt.** Hermes-as-auditor pattern paid for itself again — would have shipped a Compliance Gate regression solo. |
| 2026-05-02 | **Tool consolidation PRD authored + Phase-1 implementation reverted same day** (workspace/proposals/tool-consolidation.md, revised ~165 LOC). Original proposal: v2.11.0 alongside-deployment of `Memory` consolidated tool + 5 legacy memory tools, v3.0.0 deletes legacy. Phase 1 implemented `elefante-Memory` (5→1) alongside legacy → tool count went 20 → 21. **User caught the error: alongside-deployment is theater, not migration. Cognitive load went UP, not down.** Reverted: server.py back to 20 tools, README/docs/tools.md restored, tests green. Proposal updated to **atomic-swap migration plan** (no overlap window — v3.0.0 deletes legacy and introduces consolidated in same commit). Lesson ingested as Elefante memory + directive (high-priority) so future migration proposals must specify atomic swap, not alongside-deployment. | "why bother to make this step for one tool? aint that stupid??? please think about this? elefante why am i doing this error? learn." | **Genuine self-improvement cycle.** AI implemented; user caught the error in real time; AI reverted + documented + ingested lesson. This is the AI-driven-but-human-curated pattern working: human catches blind spots AI doesn't notice, AI deposits the learning into Elefante so the next agent inherits it. P7 reframed: approve atomic-swap plan only, do not bundle alongside-deployment. |
| 2026-05-02 | **Hermes audit pass — independence-by-different-LLM proved its keep on first run.** User asked Hermes (deepseek-v4-flash) to audit this session's docs. DeepSeek delivered 7 specific findings with file:line evidence: (HIGH×3) ISSUES.md titled "Debug Documentation Index" instead of BUG/GAP tracker; BUG-027/GAP-028 rows had no clear canonical home; memory `5179e3c8` (GAP-028) was stale OPEN status; (MED×2) memory `faeecf42` claimed Hermes never ran; §10.2 BUG count said 26 vs actual 27+3; (LOW×2) docs/debug/ referenced but doesn't exist; §10.2 unmeasurable compliance metric needed reframe. **All 7 actioned this turn:** ISSUES.md retitled "ISSUES — BUG/GAP Tracker" + Layout/postmortem sections rewritten + stale Structure/File Inventory blocks removed; stale memories `5179e3c8` + `faeecf42` marked `deprecated: True` via `elefante-MemoryUpdate` (excluded from normal search); new corrected memories ingested as id `3ed88442` (GAP-028 CLOSED) + id `e0e66320` (Layer 3 state current); §10.2 BUG count updated to 27+3 GAPs; compliance metric reframed as DEFERRED-by-plan, not unmeasured. | "let's ask hermes, self improvements" challenge — user delegated audit to a different LLM to expose Claude Code's blind spots | **Hermes-as-auditor earned its independence value on the first real task** — caught 7 inconsistencies I missed self-reviewing. Pattern proved: different LLM, different blind spots. The cost (one `hermes -z` call) is much smaller than the recurrence cost of shipping the gaps unfixed. 18/18 guards still green. |

### §10.1 Lessons logged this session

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
| BUG count tracked | **27 (BUG-001 → BUG-027) + 3 GAPs (GAP-013, GAP-025, GAP-028)** | `workspace/ISSUES.md` | Tracked |
| BUG recurrence rate (pre-distillation) | known per-row in `ISSUES.md` | `workspace/ISSUES.md` Recurrence column | Tracked |
| BUG recurrence rate (post-distillation) | unknown — needs sustained agent traffic across sessions | will derive from `ISSUES.md` Recurrence column after v2.10.x lands real workload | **NOT MEASURED YET** |
| Hermes Elefante-tool retrieval count | **GAP-028 CLOSED 2026-05-02.** Direct ingestion (Claude-Code-as-MCP-client): 9 lessons submitted, 6+ stored unique, 3 fused via Compliance Gate dedupe; 19 directives total in store. Hermes-as-LLM-agent (deepseek-v4-flash) Layer-3 round-trip surfaced lifecycle memory `f1fb77f5` with verbatim content match + auto-injected directive on every MCP response. **Recursive Hermes ↔ Elefante loop alive on the Hermes side.** | `/tmp/elefante-gap-028-verify.py` (Layer 0/1+2/3 PASS); `/tmp/elefante-self-ingest*.py` for direct ingestion | **MEASURED** |
| Active guard test count | 18 passing | `pytest tests/test_developer_routing.py` | Tracked |
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

