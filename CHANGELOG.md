# Changelog

<!-- markdownlint-disable MD024 -->

All notable changes to Elefante will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

## [2.12.0] - 2026-07-26

### Added

- Memory Intelligence **Briefing** view that explains which durable decision should shape the next agent answer and, when graph evidence exists, shows its old assumption → evidence → decision → enforced guard evolution.
- Deterministic, source-grounded 37-memory dashboard showcase generator with 11 topic/source entities and 95 links. Synthetic access history is explicitly disclosed, no user data is included, and no durable store is opened.
- Exact Elefante emblem asset for the dashboard header, derived from the repository's canonical logo without redrawing or skewing the mark.

### Changed

- Dashboard navigation is now Briefing, Memories, and Connections. All three views share a carbon/tusk/copper palette with brass, clay, and sage reserved for semantic state.
- The dashboard reference and operator guide now document the briefing contract, showcase workflow, trust boundary, current backend, and production edge schema.
- The historical 100-memory Chroma/Kuzu injector is explicitly labeled as a legacy isolated benchmark, requires `--force` before replacing its target, and no longer presents stale Chroma-first product facts.

### Fixed

- Frontend relationship, connectivity, and knowledge-graph consumers now normalize both production `from` / `to` edges and legacy `source` / `target` fixtures.
- Dashboard memory provenance now reports the configured embedded vector backend instead of hard-coding `chromadb`.
- Removed the unused React Router dependency and its two moderate advisories; the locked dashboard dependency tree now audits cleanly.
- Corrected the dashboard header asset from a truncated fragment to the complete canonical elephant-and-network symbol and restricted hover motion to the network region.
- Made the Python lock-freshness CI gate deterministic by seeding the checked-in lock before recompilation, preventing unrelated transitive releases from failing otherwise unchanged pull requests.
- Removed a stale fresh-install test assumption that the retired Chroma directory must exist when SQLite is the configured default; fresh-home coverage now verifies the active vector directory while preserving Kuzu's lazy path ownership.

## [2.11.0] - 2026-07-23

### Added

- Loopback-only Streamable HTTP daemon foundation at `python -m src.mcp.daemon`; it hosts one Elefante MCP server instance at `/mcp` and rejects remote binding.
- Transport-only stdio bridge at `python -m src.mcp.stdio_bridge` for hosts that cannot use local MCP HTTP.
- Dry-run-first legacy provenance backfill at `scripts/lifecycle/backfill_memory_provenance.py`.
- Durable source schema: memories retain a normalized provenance tuple and link to deduplicated `Source` nodes through `WRITTEN_BY` graph edges.
- Dry-run-first user-scope daemon service manager for macOS launchd, Linux systemd-user, and Windows Task Scheduler.
- Install manifest at `~/.elefante/install-manifest.json`, recording whole Elefante-owned artifacts and precise owned entries in shared JSON configuration.
- Manifest-driven uninstall command that preserves files changed after installation.
- Detect-then-emit Cursor and Kiro bridge adapters, each with distinct provenance and precise JSON-entry ownership for safe uninstall.
- Native Claude Code and Codex bridge adapters, using each host's MCP CLI and a matching-configuration fingerprint before uninstall.
- Read-only daemon-service status reporting for file ownership, platform runtime state, and loopback health.
- Read-only `scripts/lifecycle/doctor.py` report for repository runtime, daemon health, installer ownership, configured integration surfaces, and declared compatibility tiers. It never exposes host-registration commands, configuration locations, or values.
- Explicit SQLite vector-store support for fresh, isolated installations. It preserves full memory JSON and float32 embeddings in one local file, implements exact cosine retrieval and the public CRUD/filter/pagination contract, and does not read, modify, or migrate existing ChromaDB data.
- Dry-run-first ChromaDB-to-SQLite migration command with stable source snapshots, exact backup matching before apply, UUID/reconstructed-metadata/embedding parity, and representative search-overlap proof. Apply reserves a new destination without replacing an existing path and leaves ChromaDB and configuration unchanged.
- Disposable SQLite retrieval benchmark, reporting deterministic exact-cosine latency without opening user data; it establishes a measured baseline for the ChromaDB exit decision.
- Gemini CLI and OpenClaw bridge configuration with exact-entry/command manifest ownership and safe uninstall; Agent Zero guidance now distinguishes its documented container-boundary community path from certified host integration.

### Fixed

- **BUG-032:** low-level VS Code adapter configuration now requires an explicit manifest home, preventing isolated tests or callers with temporary targets from writing ownership records into the user's real `~/.elefante/install-manifest.json`.
- Dashboard now binds to loopback by default, uses explicit local CORS origins, and Docker Compose publishes only to loopback.
- `elefante-GraphQuery` is read-only; graph writes stay in the explicit `elefante-GraphConnect` path.
- The documented `pytest tests` command excludes manual observation scripts and now collects the automated suite cleanly.
- Daemon mutations now remain inside one async serialization boundary for the full vector-and-graph write; bridge notifications correctly accept empty `202` responses.
- Existing VS Code and Antigravity emitters now configure the storage-free stdio bridge instead of launching database-owning MCP subprocesses.
- The unified installer now installs the user-scope daemon service before emitting bridge-based MCP configuration.
- Installer removal now stops only an unchanged daemon service and removes only exact Elefante entries from shared IDE configuration; unrelated MCP servers and user-modified service definitions are preserved.
- Dashboard build dependencies now resolve the current Lodash, React Router, Vite, React plugin, PostCSS, and Picomatch security fixes; the locked dashboard dependency tree reports zero audit findings.
- The daemon now rejects invalid TCP ports, and the stdio bridge accepts only an exact `http://127.0.0.1[:port]/mcp/` endpoint without credentials or URL extras.
- Installer-owned Claude Code and Codex registrations can now refresh after an Elefante move or upgrade, with rollback if replacement fails; user-managed registrations remain untouched.
- JSON-based host adapters now apply the same ownership rule: they preserve an existing user-managed `elefante` entry and refresh only an unchanged manifest-owned entry. Their configuration writes are atomic.
- Daemon-service reinstallation now preserves untracked or user-modified service definitions, while refreshing only manifest-owned launchd, systemd-user, and Task Scheduler definitions.
- The installer now waits for the exact loopback daemon health response before it configures MCP clients or reports service installation success.
- Daemon provenance now rejects control characters and bounds untrusted bridge-header and environment metadata before storage, logging, or dashboard rendering; invalid values fall back to explicit safe source labels.
- File-level backup now writes a checksum manifest and excludes nested recovery archives; restore is dry-run-first, rejects unsafe zip paths, symlinks, duplicate members, and integrity failures before it mutates data, then stages a verified archive before replacing the durable data directory.
- Dashboard data routes now read only the redacted static snapshot. Browser-triggered live snapshot generation has been removed; semantic retrieval and live refresh remain on explicit MCP or operator paths, and dashboard responses no longer expose local data-directory paths.
- The stdio bridge now rejects malformed or oversized (over 1 MiB) JSON-RPC messages before forwarding them and does not reuse a previous request ID when parsing a later malformed line fails.
- The direct Streamable HTTP daemon now applies the same 1 MiB request-body boundary before handing a request to the MCP session manager, including chunked requests, so direct clients cannot bypass bridge-side input limits.
- The standalone dashboard image no longer overrides the loopback bind default. Docker Compose retains its internal-container bind while publishing only to host loopback; external dashboard exposure is now explicitly documented as a reverse-proxy security responsibility.
- Every declared direct Python runtime and development dependency is now pinned to a tested version, and `requirements.lock` carries the universal, hash-checked transitive resolution. Installers, Docker, and CI use the lock; CI also verifies that it remains fresh.
- Tagged releases now run a hash-checked `pip-audit` gate against `requirements.lock` before GitHub publication, so a known advisory cannot be bypassed by the artifact workflow.
- The MCP Python SDK now uses v1.28.1, removing the three advisories reported against the prior v1.23.1 runtime while retaining the verified daemon and bridge contracts.
- Black, pytest, pytest-asyncio, FastAPI, and Starlette now use compatible patched versions. SentenceTransformers v5.6.0 and Transformers v5.14.1 remove the remaining model-stack advisories while preserving Elefante's configured local 768-dimensional `thenlper/gte-base` output; the new loader contract has a regression test.
- Cognitive retrieval now applies a positive co-activation contribution after its vector-similarity floor, so the floor cannot erase a proven related-memory boost.
- The vector store now has a regression guard requiring Chroma's embedded `PersistentClient` and rejecting introduction of its network client surface; this mitigates exposure to the unresolved server-endpoint advisory but does not waive the release gate.
- The post-update audit is reduced to one ChromaDB advisory (PYSEC-2026-311) with no published fixed version; it remains release-blocking.
- Controlled daemon and Elefante-mode shutdown now release SQLite vector-store handles; file-level backup and restore have a regression proof for the opt-in SQLite database alongside existing ChromaDB data recovery coverage.
- The direct stdio server now follows the same controlled shutdown path as the daemon. Antigravity configuration no longer leaves an untracked `.json.bak` copy; atomic, ownership-aware writes remain recoverable through the normal manifest and data backup paths.
- The manual startup guide, self-protocol, demo seed, and test guide now state the current source-derived 16-tool MCP surface rather than the obsolete 20/21-tool counts.
- Entrypoint and error routing now point agents to `workspace/ISSUES.md` and its linked postmortems, restoring the live response contract after the documentation layout migration.
- Docker bundle generation now includes the hash-locked dependency resolution and current Docker/Agent Zero guides; its output directory is configurable for isolated automation, and it no longer references deleted `docs/technical` files.
- The native Codex CLI lifecycle regression now proves that a later user-owned replacement of the `elefante` registration is preserved during manifest-driven uninstall; normal installer-owned removal remains covered separately in the same isolated `CODEX_HOME` round trip.
- Package metadata now derives exact direct runtime and development versions from `requirements.txt`, and the built wheel includes the `src` namespace used by all documented `python -m src.mcp...` commands. The README and installation guides now reflect MCP v1.28.1, the optional SQLite backend, the full detected-host configuration surface, and the daemon-plus-stdio-bridge architecture rather than a database-owning IDE subprocess.
- The read-only memory exporter and dashboard snapshot pipeline now use the configured embedded vector store, including fresh SQLite stores. Factory reset now moves configured/default ChromaDB, SQLite, and Kuzu paths into its recovery area, honors `ELEFANTE_DATA_DIR`, and refuses configurations that would contain that recovery directory.

### Changed

- Added pull-request and `main` quality checks for the Python suite and dashboard production build.
- Version synchronization now targets only real release identifiers and provides a guarded `bump_version.py --sync` repair path; historical postmortem, schema, and document-version labels are no longer rewritten as product versions.
- The living plan now tracks the active v2.11.0 Trust Release instead of retaining already-shipped v2.10.0 decision scaffolding; a routing regression prevents that stale state from returning.
- Active routing and the v3 tool-consolidation proposal now use the source-derived 16-tool baseline and current `docs/`, `workspace/`, and `agents/` homes; obsolete 20-tool and retired-surface references were removed.

## [2.10.0] - 2026-05-02

Memory MCP tool surface consolidated: 5 legacy memory tools (`elefante-MemoryAdd`, `elefante-MemorySearch`, `elefante-MemoryUpdate`, `elefante-MemoryDelete`, `elefante-MemoryConsolidate`) deleted and replaced with one `elefante-Memory` tool taking an `action` discriminator (`add` | `search` | `update` | `delete` | `consolidate`). Clients must update tool calls — see `### Changed` below for migration mapping.

This is a breaking change to the Memory MCP surface, deliberately bundled as 2.10 rather than 3.0: the v3.0.0 banner is reserved for the full domain consolidation (Knowledge / Task / Process / Directive / System) shipping in one coordinated migration, alongside async ingestion and schema versioning.

This release also bundles the agentic documentation restructure (Diátaxis-pure `docs/`, `workspace/` for live state, `agents/` for loadable protocols), the Hermes <-> Elefante recursive memory loop closure (Layer 3 verified via DeepSeek-v4-flash), and the unified Workflow Lifecycle (steps 0–10 in `agents/orchestrator.md`). All non-Memory changes are additive.

Counts: tool surface 20 → 16. Doc active surface 13,184 → ~9,000 LOC. Postmortems 5,024 → 597 LOC distilled (originals preserved verbatim in `_archive/`). 76/76 active guards green.

### Fixed

- **GAP-028 CLOSED — Hermes <-> Elefante recursive memory loop ran for the first time from the Hermes side (2026-05-02).** Configuration: `~/.hermes/.env` chmod 600 with `DEEPSEEK_API_KEY` (user-provided, recommended to rotate post-session); `~/.hermes/config.yaml` `model: deepseek-v4-flash` (smaller/faster per user preference 2026-05-02). Verifier `/tmp/elefante-gap-028-verify.py` reports Layer 0 PASS (Hermes status: `Model: deepseek-v4-flash` + `Provider: DeepSeek` auto-detected) + Layer 1+2 PASS (20 elefante-* tools discoverable) + Layer 3 PASS (`hermes -z` invoked deepseek-v4-flash, which called `elefante-MemorySearch`, surfaced memory id `f1fb77f5-5863-46cf-9471-d3a3872ba5d3` with verbatim content match against the Workflow Lifecycle memory ingested earlier in this session, and synthesized an accurate answer noting the lifecycle is BOTH a memory AND an auto-injected directive). **The recursive memory loop is no longer projection** — Hermes is a real LLM-driven Elefante consumer. Verifier heuristic also tightened: closure now requires UUID match or verbatim memory-body quote (proves tool execution), not literal "elefante-MemorySearch" mention (LLMs synthesize prose without echoing tool names). Closes the "WHY HAVE YOU STOPPED?" / "NEVER SIMULATE. ALWAYS FACT DRIVEN" challenges with measurable round-trip evidence.

### Added

- **Tool consolidation PRD authored at `workspace/proposals/tool-consolidation.md` (2026-05-02, ~165 LOC; revised same day after Phase-1 implementation revealed the alongside-deployment trap — see below).**

### Changed

- **Memory tool consolidation — atomic swap shipped (v2.10.0, 2026-05-02).** Tool count **20 → 16.** Five legacy memory tools (`elefante-MemoryAdd`, `elefante-MemorySearch`, `elefante-MemoryUpdate`, `elefante-MemoryDelete`, `elefante-MemoryConsolidate`) deleted in the same change that introduced `elefante-Memory` with discriminated `action` parameter (`add`/`search`/`update`/`delete`/`consolidate`). Atomic-swap migration (no overlap window) per the lesson learned earlier same day that "alongside-deployment is theater." Compliance Gate preserved: handlers still call `_check_compliance_gate(<legacy-name>)` internally — only the public surface consolidated. Updates: `src/mcp/server.py` (tool def + dispatcher + class docstring + `_CONTEXT_SKIP_TOOLS` + `_inject_pitfalls` + gate error messages + grounding prompt); `scripts/verify/verify_e2e_tests.py` (EXPECTED_TOOLS + 13 call sites + grounding-text check); `tests/test_memory_persistence.py` (2 call sites); `scripts/setup/configure_antigravity.py` + `configure_vscode_bob.py` (IDE MCP allowlists); `README.md` + `docs/README.md` + `docs/reference/tools.md` (counts + consolidation note). Hermes-driven pre-surgery audit (deepseek-v4-flash) caught a silent Compliance Gate regression risk that solo self-review missed. Post-swap verified: `hermes mcp test elefante` shows 16 tools with `elefante-Memory` first listed; `tests/test_developer_routing.py` 18/18 green. **Other 5 domain consolidations (Knowledge/Task/Process/Directive/System) remain in `workspace/proposals/tool-consolidation.md` as deferred — each will need its own atomic swap pass.** Proposes v3.0.0 surface reduction from 20 atomic tools to 6 domain-grouped tools with action discriminator: `Memory(action=add|search|update|delete|consolidate)`, `Knowledge(action=graph_connect|graph_query|context|sessions)`, `Task(action=create|update|read)`, `Process(action=process|classify)`, `Directive(action=add|list|remove)`, `System(action=status|toggle|dashboard)`. Architecturally distinct from rejected X1 (PLANNING.md §2.5) — addresses each of X1's 4 objections individually: action param is explicit (not hidden routing), per-action sub-schemas are normal pattern (not maintenance doubling), Compliance Gate inspects `arguments.action` exactly as it inspects `tool.name` today (no visibility loss), Tasks/Process stay separate domain tools (no conflation). Migration plan: v2.11.0 ships 20+6 alongside (one-release deprecation window); v3.0.0 deletes the 20. Acceptance criteria: ≥50% drop in `TOKEN_STATS.overhead_tokens` per MCP response, behavioral parity tests for every old-tool→new-action mapping, Hermes round-trip verification. P7 added to `workspace/PLANNING.md §2.6` pending user approval. Ingested as Elefante memory id=`4d847761`. Async ingestion pipeline + schema versioning are architecturally adjacent but **separable** (kept as future v3.0.x / v3.1 patches, not bundled).

- **BUG-027 + GAP-028 tickets opened in `workspace/ISSUES.md` (2026-05-02).** **BUG-027** (file-edit destructive op without preservation, parent class BUG-006) — agent ran `rm` on uncommitted files without `git status --porcelain` check or archive-first preservation; 1033 LOC of original PRD prose permanently unrecoverable. Mitigation: Lifecycle step 4 ARCHIVE in `agents/orchestrator.md` + Elefante directive auto-injecting the rule. No active filesystem guard yet (v2.11+ architectural item). **GAP-028** (Hermes LLM provider configuration) — Hermes wired to Elefante (Layers 1+2 ✓) but cannot run as LLM agent: `hermes status` reports `Model:(not set)`, `Provider:Auto`, `.env file: ✗`, all 12 native API keys ✗. User intent: route certain tasks through DeepSeek. Decision matrix authored in `workspace/PLANNING.md §6.4.1` with three paths (A: OpenRouter recommended; B: direct DeepSeek via OpenAI-compat endpoint; C: hybrid primary+fallback) + per-task DeepSeek model selection (`deepseek-chat` V3 / `deepseek-reasoner` R1) + concrete `hermes login` commands per path + acceptance test (`hermes -z "Use elefante-MemorySearch ..."` round-trip surfaces an Elefante memory). User-side action required to close. Architect recommends **Path A (OpenRouter)** for first close.

- **Unified Elefante Workflow Lifecycle authored in `agents/orchestrator.md` (2026-05-02).** 11 canonical steps (0 ENGAGE → 1 CLASSIFY → 2 SEARCH → 3 PROPOSE → 4 ARCHIVE → 5 WRITE → 6 INDEX → 7 INGEST → 8 VERIFY → 9 JOURNAL → 10 CLOSE) replacing scattered overlapping protocols (The Loop / Five Gates / Memory Janitor Mandate / Documentation Skill / Closure Sequence — now framed as detailed implementations of steps 5+8, not separate protocols). Linear top-to-bottom; no skipping. Every cycle ends with INGEST + JOURNAL + COMMIT — without all three, the loop has not closed. `AGENTS.md` mirrors the Lifecycle table at top so it's the first thing every agent sees on session entry. Lifecycle stored as Elefante memory id=`f1fb77f5` (retrievable on `MemorySearch("workflow lifecycle")` at score 0.755) + installed as directive (DirectiveList count 16→19) auto-injecting on every MCP tool response. Source: `agents/orchestrator.md` § The Elefante Workflow Lifecycle.

### Changed

- **Layer 3 Hermes/Elefante engagement first achieved (2026-05-02).** Direct stdio JSON-RPC ingestion from this session: 9 lessons submitted via `elefante-MemoryAdd`, 6 stored unique (UUIDs returned), 3 fused with existing memories via Compliance Gate dedupe (working-as-designed semantic compression at consumer side); 3 directives added via `elefante-DirectiveAdd` (count 13→16); verification queries surface ingested memories at similarity 0.61–0.81 on distinctive phrasing. **Layer 1 (config saved) and Layer 2 (20 tools discoverable) had been ✓ since earlier wiring; Layer 3 (active retrieval) had been idle for ~10 hours of session producer-side work until the user's "WHY HAVE YOU STOPPED? WHAT IS YOUR MAIN OBJECTIVE?" challenge.** Hermes-as-LLM-driven-agent still blocked on missing model config in `~/.hermes/config.yaml`; the loop is consumer-agnostic — any MCP-capable agent closes it. Source: `workspace/PLANNING.md §10` journal + `/tmp/elefante-self-ingest*.py` runs.

- **Information preservation discipline adopted (2026-05-02). "We don't cut information, it gets documented" rule now enforced.** Triggered by user directive after curation pass 1 deleted 2 uncommitted proposals (`surface-split.md` 583 LOC + `documentation-strategy-protocol.md` 450 LOC) without preservation. Recovery: 4 distilled postmortem originals restored verbatim from git HEAD into `workspace/postmortems/_archive/` (3,687 LOC); `memory.md` (1,255 LOC) archived BEFORE distillation per the new rule; 2 unrecoverable proposals received absorption-map stubs at `workspace/proposals/_archive/<name>-full.md` documenting where every section's content survives in the active surface. **New rule:** archive verbatim before distill; CHANGELOG entries describe the change, not the content. Total preserved this session: 5,464 LOC across `docs/_archive/`, `workspace/postmortems/_archive/`, `workspace/proposals/_archive/`. Filed as BUG-027 conceptually (parent class BUG-006 — passive-protocol bypass on file-edit surface).

- **Postmortem distillation pass 3 — memory.md 1,255 → 131 LOC (89% cut, 15 issues).** Same model as installation/ai-behavior/database/dashboard. Original archived first to `_archive/memory-full.md`. Atomic Trigger/Root cause/Solution/Lesson chunks per closed BUG; cross-bug pattern footer points to `workspace/lessons.md`. **Cumulative postmortem reduction across all 5 files: 5,024 → 597 LOC (88% cut). All 5 originals preserved verbatim.** 18/18 guards green throughout.

- **Postmortem distillation pass 2 (2026-05-02): 4 of 5 postmortems compressed to atomic Trigger/Root cause/Solution/Lesson chunks for Elefante memory ingestion.** Each closed BUG now distills to ≤30 LOC; long narrative bloat (Cognitive Failure Analysis, Why This Took So Long, Prevention Protocol, Methodology Failures, Appendix Issue Templates, Quick Install References, multi-paragraph Solution code blocks) cut. Verification commands moved to `workspace/ISSUES.md` rows (single canonical home). Cross-bug patterns extracted as pointers to `workspace/lessons.md`.
  - `workspace/postmortems/installation.md`: 1,401 → 130 LOC (91% cut, 14 issues)
  - `workspace/postmortems/ai-behavior.md`: 1,044 → 110 LOC (89% cut, 12 issues)
  - `workspace/postmortems/database.md`: 572 → 77 LOC (87% cut, 8 issues)
  - `workspace/postmortems/dashboard.md`: 729 → 86 LOC (88% cut, 9 issues)
  - `workspace/postmortems/memory.md` (1,255 LOC): pending next pass.
  Total postmortem reduction: 3,746 → 403 LOC (89% cut). 18/18 guards green throughout. The Elefante-as-memory lens drove the cuts: each chunk must justify its tokens by raising correctness probability on retrieval — long narratives surface as low-signal noise.

### Removed

- **`workspace/proposals/surface-split.md`** (583 LOC) — superseded by the 2026-05-02 restructure. Plan was to add `docs/user/` + `docs/developer/`; actual restructure went beyond and adopted Diátaxis. Multiple stale refs to "legacy" `docs/elefante-orchestrator-agent.md` and "Stays as forwarding source during v2.10.x" — that file is now deleted. X-series rejection rationales preserved verbatim in `workspace/PLANNING.md §2.5`.
- **`workspace/proposals/documentation-strategy-protocol.md`** (450 LOC) — absorbed into `agents/orchestrator.md` § Documentation Skill (Phase B merge). Closed Surface Map, audience axis, authority declaration all live there now. Continued existence was duplicate authority.

### Changed

- **Content curation pass 1 (2026-05-02): stripped drift-bait stamps and stale internal sibling refs across the new Diátaxis surface.** All `**Status**: ESSENTIAL/PRODUCTION/ENFORCED/UPDATED` and `**Version**: X.Y.Z`/`**Last Updated**: YYYY-MM-DD`/`**Document Version**: X.Y.Z`/`**Feature Version**: X.Y.Z` boilerplate stamps removed from `docs/reference/*.md`, `docs/how-to/*.md`, `docs/explanation/*.md` (they surface as wrong context when Elefante retrieves the doc). Internal sibling refs using old `spec-X.md`/`ops-X.md` filenames updated to new Diátaxis names via per-folder sed pass. Cross-folder refs (`how-to/` → `reference/`, `reference/` → `how-to/`) corrected. Compendium refs in how-to/ updated to `workspace/postmortems/<domain>.md`. `scripts/ci/bump_version.py` line 63 stale `docs/technical/README.md` sync target removed. Phase 1 of content curation; deeper postmortem distillation (Trigger/Rule/Why/Proof/Avoid format) deferred.

- **Architectural restructure: `docs/` rebuilt from the ground up on tri-axis Diátaxis topology (2026-05-02).** The pre-restructure tree mixed four orthogonal organizing axes (audience / type / lifecycle / surface) in eight subfolders, producing endless migration cycles, empty boundary READMEs, tombstones in active dispatch, and persistent drift. New shape: `docs/{reference,how-to,explanation,_archive}/`. State separated into `workspace/{ISSUES,lessons,postmortems/,proposals/,decisions/,PLANNING.md}`. Manifests centralized in `agents/manifests/`. Pre-restructure tree preserved verbatim in `docs/_archive/` as audit trail (no information loss). **Migrations (29 files):** spec-* → `docs/reference/` (9 files); ops-* + dev-etiquette → `docs/how-to/` (10 files); spec-vision → `docs/explanation/`; ide-integration-matrix.yaml → `agents/manifests/`; debug/* → `workspace/{ISSUES,lessons,postmortems/}` (7 files); planning/* drafts → `workspace/proposals/` (7 files). **Cascade:** ~50 cross-references updated via single sed pass; 4 tests adjusted; CHANGELOG history (frozen) deliberately untouched. Audience-axis folders (`docs/user/`, `docs/developer/`) and type-mixing folder (`docs/technical/`) deleted; lifecycle is now a `status:` frontmatter field, not a folder name. Authority: [`docs/README.md`](docs/README.md) for tri-axis routing; [`docs/_archive/README.md`](docs/_archive/README.md) for full migration index. All 18 active guards green after cascade. Hermes MCP connection unaffected (verified `hermes mcp test elefante` returns all 20 tools).

### Removed

- **`docs/elefante-orchestrator-agent.md`** (298 LOC) — Phase B of agentic restructure 2026-05-02. Merged into `agents/orchestrator.md` (single canonical developer constitution). Eliminates the 3-way authority confusion (full constitution vs. loadable agent vs. dev-doctrine synthesis). The merged orchestrator is ~270 LOC, trigger-loaded (`LOAD_WHEN: Building or debugging Elefante itself`), and includes Loop / Five Gates / Memory Janitor Mandate / Documentation Skill (Closed Surface Map + Forbidden Patterns + Pre-write checklist + New-File Test + Failure Conditions + Lifecycle) / Embedding Rule / Modes / Compendium Trigger Map / DEVELOPER routing / Closure Sequence / Where Things Live / Specialist Handoffs / Critical Thinking + Question-First / Changelog Contract / Never list. Cascade: ~25 reference updates across `AGENTS.md`, `CONTRIBUTING.md`, `README.md`, `.claude/README.md`, `docs/README.md`, `docs/debug/README.md`, `docs/debug/best_practices.md`, `docs/developer/README.md`, `docs/planning/README.md`, `docs/technical/README.md`, `docs/technical/spec-token-intelligence.md`, `agents/integration-inspector.md`, `agents/memory-janitor.md`, `scripts/README.md`, `scripts/ci/bump_version.py` (line 70 sync target removed), `scripts/verify/verify_e2e_tests.py` docstring, `src/core/orchestrator.py:66` runtime citation, `tests/test_developer_routing.py` (4 path assertions + 2 docstring references), `workspace/README.md`, `workspace/PLANNING.md` (5 references). All 18 active guards green after cascade.

- **`docs/developer/dev-doctrine.md`** (303 LOC) — redundant synthesis duplicating content already canonical in `docs/elefante-orchestrator-agent.md` (constitution), `docs/planning/spec-vision.md` (Four Laws + thesis), and `docs/technical/dev-etiquette.md` (closure sequence). Violated Documentation Skill "no new markdown unless every existing canonical surface is proven insufficient" — no proof was attached. Resolution: deleted; no replacement (the canonical sources are sufficient). Phase A of agentic restructure 2026-05-02.
- **`docs/debug/dev-developer-agent.md`** (8 LOC tombstone) — forwarded to `docs/elefante-orchestrator-agent.md`. Memory Janitor mandate: delete with record, not zombie in active dispatch table. Active dispatch references in `docs/README.md` and `docs/debug/README.md` updated to point directly to the constitution. Phase A of agentic restructure 2026-05-02.
- **`docs/technical/dev-sdd.md`** (10 LOC tombstone) — same pattern. Cascade: removed from `docs/README.md` Development table, `docs/technical/README.md` Development table, `docs/developer/README.md` Process & workflow row, and `scripts/ci/bump_version.py:71` version-sync target. Phase A of agentic restructure 2026-05-02.

### Changed

- **`docs/debug/self-elefante-protocol.md` → `docs/technical/spec-self-protocol.md`.** Whole-system MCP verification is a positive contract (what the system promises), not a debug postmortem (what broke). Wrong-axis placement corrected per Diátaxis (reference vs explanation). Cascade: 5 reference updates across `docs/README.md`, `docs/debug/README.md`, `docs/debug/best_practices.md`, `scripts/README.md`, `scripts/verify/verify_e2e_tests.py` docstring, and 4 test assertions in `tests/test_developer_routing.py`. Phase A of agentic restructure 2026-05-02.
- **`docs/planning/spec-token-intelligence.md` → `docs/technical/spec-token-intelligence.md`.** Token Intelligence shipped v2.5.0; planning/ is for future-facing intent (per `docs/planning/README.md` boundary). Wrong-folder placement corrected. Cascade: 2 reference updates across `workspace/PLANNING.md §4.4` and `docs/planning/README.md`. Phase A of agentic restructure 2026-05-02.

### Added

- **Hermes <-> Elefante MCP wiring (live 2026-05-02).** Hermes (`/Volumes/OWC2TB/2026-M5/AI Projects/hermes-agent`) registered as a stdio MCP client of Elefante via `~/.hermes/config.yaml` `mcp_servers.elefante`. Command: `<elefante>/.venv/bin/python -m src.mcp.server` with `PYTHONPATH=<elefante>` env. `hermes mcp list` reports `✓ enabled` with all 20 tools. Prerequisite: `mcp==1.27.0` installed in Hermes's uv venv (Hermes treats the SDK as optional; without it `hermes mcp test` raises `StdioServerParameters not defined`). This is Elefante's first non-IDE MCP consumer and the empirical measurement surface for the v2.10.0 -> v2.11.0 restructure decisions. Stdio-per-client means Hermes and any IDE-attached Elefante session compete for the Kuzu single-writer lock (GAP-025); concurrent use is unsafe until v2.11.0 daemon ships. Source-of-truth: [`workspace/PLANNING.md §6.4`](workspace/PLANNING.md).

- **`agents/` folder — token-disciplined specialist protocols.** Per `docs/planning/spec-v2.10.0-surface-split.md`, agents are loaded by an LLM at the moment of failure, not read by humans browsing. Each declares `PROTOCOL_VERSION`, `LOAD_WHEN`, `DIAGNOSTIC_QUESTION` in YAML frontmatter and is ≤100 lines. Eleven files ship in this release:
  - `agents/orchestrator.md` (100 lines) — distilled from `docs/elefante-orchestrator-agent.md`. Loaded when building or debugging Elefante itself (DEVELOPER mode). The old file remains in place as a forwarding source during the v2.10.x runway.
  - `agents/memory-janitor.md` (68 lines) — auto-loaded on every `MemoryAdd` / `MemoryUpdate` / `MemoryDelete`. Promoted from the orchestrator's Memory Janitor Mandate section. Three rules: delete with a record, create with a question, resolve do not file.
  - `agents/memory-inspector.md` (57 lines) — read-only memory inspection. Search-first discipline; routes any write to memory-janitor.
  - `agents/installer.md` (61 lines) — install fresh, broken venv, repair. Reads the three persisted install files (`.elefante-install-summary.txt`, `-status.txt`, `.log`) before any action.
  - `agents/restarter.md` (60 lines) — MCP server stuck, IDE not seeing tools. Three-layer diagnostic (server / IDE / lock) with graceful restart sequence.
  - `agents/release-manager.md` (80 lines) — version bump, CHANGELOG, tag, GitHub release. Owns the inviolable order: CHANGELOG → advise → bump → commit → tag → push.
  - `agents/operator.md` (80 lines) — backup, restore, factory reset, restart. Backup-first is non-negotiable; server stopped before file-level operations.
  - `agents/researcher.md` (42 lines) — RESEARCH mode specialist. Loaded when the current line of attack is suspect (illogical, premature, overfit, under-evidenced). Owns the 4-step protocol; forbids version bump, release claim, and "done" claim from emerging in this mode.
  - `agents/puppeteer.md` — dangerous `PRIVILEGED` specialist for control-plane surgery. Loaded only with explicit authorization when governing behavior itself must be retuned: parameters, conditioned ideas, authority boundaries, acceptance thresholds, or janitor escalation. Requires direct risk statement and rollback path.
  - `agents/integration-inspector.md` — **dormant in v2.10.0** (no runtime wiring yet). Ships as the protocol contract for the continuous doc-drift audit over `docs/technical/ide-integration-matrix.yaml`. Trigger-first; WebFetch-only; read-only. Activation gated by v2.11 (matrix file exists) and v2.12 (CI drift audit wires it). See `docs/planning/spec-ide-integration-surface.md` §4.4 and §15.
  - `agents/_glossary.md` (42 lines) — Layer 1 codename stub. Glossary table empty; populated as agents adopt codenames.

- **`docs/user/README.md`** — dispatch index for user-facing content. Routes to existing `docs/technical/ops-*.md` files during the v2.10.x migration. Forwarding from old paths is preserved (every link continues to work).

- **`docs/developer/README.md`** — dispatch index for developer-facing content. Routes to existing `docs/technical/`, `docs/debug/`, `docs/planning/` files during the v2.10.x migration.

- **`AGENTS.md` at repo root** — universal agent entry point per the 2025-2026 cross-IDE convention (auto-loaded by Codex, Cursor nested, VS Code Copilot, Cline, Roo, Kilo, Zed). Single canonical door for any AI agent operating on this repository. Routes by audience (end-user agents → `.github/copilot-instructions.md` constitution + `docs/`; developer agents → `docs/elefante-orchestrator-agent.md` constitution + `workspace/PLANNING.md` + `agents/`). Closes the long-standing gap of multiple competing entry points. Pulls forward from v2.11.0 plan (`docs/planning/spec-ide-integration-surface.md §3` — "Universal AGENTS.md root-file emission") because the convergence-point file can ship now and partially satisfies seven IDE surfaces (Codex, Cursor nested, VS Code Copilot, Cline, Roo, Kilo, Zed) without daemon dependency.

- **`docs/technical/ide-integration-matrix.yaml`** — machine-readable inventory of all 16 IDE / agent integration surfaces (Claude Code, VS Code Copilot, Cursor, Windsurf, IBM Bob, Kiro skills+steering, Gemini, Codex, Cline, Roo, Kilo, Continue, Zed, Aider; OpenClaw confirmed out-of-scope). Per-surface fields: `in_repo` paths (with `tracked` and `installer_writes` status), `user_home` paths per platform, `skill_paths`, `format`, `documentation` references, `doc_urls`, `last_verified`, `verified_doc_hash`, current `status` (`configured` / `planned` / `out-of-scope`). Pulls forward from v2.11.0 plan as a v0 scaffold; integration-inspector run before v2.11.0 cuts will refresh `verified_doc_hash` per row. Single source of truth for `agents/installer.md` (which surfaces to detect-then-emit), `agents/integration-inspector.md` (continuous doc-drift audit), `docs/technical/ops-ide-configuration.md` (per-surface install reference), and `tests/test_developer_routing.py` (drift guards).

- **`.claude/README.md`** — documentation for `.claude/` directory contents. Records the rationale for the 7 WebFetch domains whitelisted in `.claude/settings.local.json` (each domain mapped to a specific IDE integration target in the matrix). Prepares the namespace for the planned `.claude/skills/<name>/SKILL.md` files in v2.11.0. Closes a documentation gap that existed since `.claude/settings.local.json` was first authored without explanation.

- **`workspace/` developer surface** — top-level directory for developer-workspace material, separate from `docs/` (which becomes the client-facing surface as Elefante approaches ship-readiness). Per the user's diagnosis 2026-05-02: "I need a clear division in both [client and developer workspace]" while keeping agentic patterns active in both.
  - `workspace/README.md` — workspace dispatch + migration state.
  - `workspace/PLANNING.md` — single living plan consolidating Vision (§1), Active Release v2.10.0 with full ledger (§2: A-series accepted, D-series in-development gated by P-series, X-series rejected, OB-series workspace blockers, Resume verdict), Multi-release Roadmap (§3: v2.10.x / v2.11.0 / v2.12.0), Features by status (§4: backlog → in-design → active → shipped → rejected), Optimization (§5), Ops Plans (§6), Dev Process Plans (§7), UX Plans (§8), Meta-process (§9), Update history (§10). Replaces 9-file fan-out in `docs/planning/` for resume questions. Source PRDs in `docs/planning/spec-*.md` remain authoritative for full PRD bodies until follow-on consolidation phase.
  - `workspace/decisions/README.md` — placeholder for ADRs (Architecture Decision Records, sequential `ADR-NNNN-*.md`); migration plan documented for ~12+ ADRs absorbing currently-scattered decision rationales (rejected-proposals X1-X6 from `spec-surface-split.md §0.6.2`, BUG-016/017/018 scoring decisions, BUG-026 active-guard adoption, this session's killed dated- and version-stamped patterns).

### Changed

- **Repository structure introduces three-axis separation.** Previous structure split content by audience (`user/` / `developer/` / `technical/` / `debug/` / `planning/`) and by content type (`spec-` / `ops-` / `dev-` prefixes). New axis added 2026-05-02: **integration target** — the distinction between in-repo documentation (`docs/`, `workspace/`) and IDE-side integration files that agents actually load (`.github/copilot-instructions.md`, `.claude/skills/*/SKILL.md`, `.cursor/rules/*.mdc`, etc.). Captured in `docs/technical/ide-integration-matrix.yaml` as a queryable manifest.

- **Expanded control-plane spec in `docs/planning/spec-v2.10.0-surface-split.md`**: §0 Execution Status (live, updated per phase); §1.5 The Swarm Law; §1.6 Response Discipline; §1.6.1 Research Mode; §1.7 Why the dev/user split is structural; §2.2.1 Agent Naming Convention; §2.4.1 Puppeteer Security Boundary.

### Changed

- **`README.md` (repo root)** — added "Three audiences, three surfaces" routing table and an agent dispatch table. Pointer to the orchestrator updated from `docs/elefante-orchestrator-agent.md` to `agents/orchestrator.md` (the old file remains as a forwarding source during the v2.10.x runway). Existing reference list preserved.
- **Developer-side Research mode** — the orchestrator now distinguishes `DEVELOPER` execution from `RESEARCH`, a bounded experimental lane for moments when the current path may be illogical or under-evidenced. Why: honest self-check needs a named protocol, not ad-hoc hesitation. What: the authority docs and developer index now require smallest-proof alternative checks and forbid release/version/done claims from this mode. Impact: exploratory work can pause and redirect without contaminating shipping flow.
- **Agent invocation name (`INVOKE: elefante-<role>`)** — every loadable agent now declares a second frontmatter key that is its *dispatch identity*, distinct from the filename (*disk identity*). The `elefante-` prefix is fixed and matches the MCP tool naming scheme (`elefante-MemoryAdd`, `elefante-HealthCheck`), so the full protocol surface — tools and agents — reads with one voice. Why: dispatchers (README tables, error messages, orchestrator handoffs) need one canonical invocation that carries the brand. What: rule lives in spec §2.2.1 with a ten-agent manifest; `_glossary.md` (meta) is excluded. Impact: planned `scripts/verify/verify_agents.py` fails CI if any agent lacks `INVOKE`, has a non-`elefante-` prefix, or drifts from its filename.
- **Renamed `docs/planning/spec-v2.10.0-surface-split.md` → `docs/planning/spec-surface-split.md`** — filename now describes the multi-release feature (v2.10.0 additive split → v3.0.0 stub deletion), not the v2.10.0 release. Resolves BUG-026 recurrence #1 (version-stamped filename was the same anti-pattern as `HANDOFF-YYYY-MM-DD.md`). Cross-references cascaded across 12 files. Documentation Skill Forbidden Patterns in `docs/elefante-orchestrator-agent.md` extended to enumerate `spec-vXX.YY.ZZ-*.md` as forbidden. CHANGELOG.md historical references to the old name are left untouched (Keep-a-Changelog historical-record principle).

### Removed

- **`docs/planning/HANDOFF-2026-04-17.md`, `docs/planning/HANDOFF-2026-04-18.md`, `docs/planning/HANDOFF-2026-05-01.md`** — *resolution: superseded by `docs/planning/spec-surface-split.md §0` (Execution Status + Resume Snapshot).* Date-stamped session-handoff filenames violate the Documentation Skill Forbidden Patterns established in this release (`HANDOFF-YYYY-MM-DD.md` is the canonical example of the killed pattern). All three files were SUPERSEDED on 2026-05-02 and removed on the same day after content was confirmed absorbed into canonical homes: live ledger state in `spec-surface-split.md §0.5`/`§0.6`/`§0.7`; v2.11.0/v2.12.0 deployment plan in `spec-ide-integration-surface.md §15`; BUG-026 audit narrative in `docs/debug/ops-ai-behavior-compendium.md` Issue #12. Caught BUG-026 recurrence #3 (deferred-work-not-executed when the canonical authority ruled the pattern dead). Per Memory Janitor mandate: delete with a record. Conversation arcs are not lost — they are now distilled in the canonical homes; the original date-stamped capsules served their session-handoff purpose at the time of writing and no longer carry signal worth their tokens.

- **Surface split (additive, minor bump).** v2.10.0 separates the repository into three audiences — end-users (`docs/user/`), developers (`docs/developer/`), and agents (`agents/`) — each with its own loading model. Mass file moves from `docs/technical/`, `docs/debug/`, `docs/planning/` are deliberately deferred to v2.10.x patches; the dispatch indexes route through the existing locations so no link breaks. v3.0.0 will delete the forwarding stubs once the new layout has earned its keep through real operational use.

- **IDE Integration Surface — Phase 2 of the installer, fully planned (implementation deferred).** Four new/amended planning artifacts ship as documentation only; no runtime code changes land in v2.10.0:
  - `docs/planning/spec-ide-integration-surface.md` — PRD covering the verified 16-surface IDE integration matrix (Claude Code, VS Code Copilot, Cursor, Windsurf, Kiro skills+steering, IBM Bob, Gemini, Codex, Cline, Roo, Kilo, Continue, Zed, Trae, Aider, and `AGENTS.md` universal fallback), the singleton daemon architecture that replaces stdio-per-client, the `(:Memory)-[:WRITTEN_BY]->(:Source)` schema closing GAP-025, the `docs/technical/ide-integration-matrix.yaml` single source of truth, the detect→emit installer contract, and §15 Deployment Plan (v2.11 bundles daemon + schema + six adapters; v2.12 adds inspector CI + Phase 3 extension surfaces).
  - `docs/planning/spec-session-intelligence.md` §6.7 + §13 — amended with the Source/Origin tuple schema that session-intelligence requires as its join key, and cross-linked to GAP-025.
  - `docs/debug/ops-memory-compendium.md` Issue #15 — post-mortem for the multi-instance write origin tracking gap: two compounding architectural absences (no `source.*` tuple on writes, stdio-per-client transport violates Kuzu's single-writer contract under concurrent IDE use) filed with closure plan.
  - `docs/debug/README.md` — **GAP-025** row added to the Known Issues table. Status: DOCUMENTED. Closure gated on v2.11 Phase A + B acceptance.

---

## [2.9.3] - 2026-04-17

### Added
- **Native AppKit Installer files**: Added explicit git tracking for `scripts/ci/installer_app.swift` and installer icon assets that were omitted in previous commits.

### Removed
- **`scripts/ci/backfill_github_releases.py`** — *resolution: one-time task complete.* Created to retroactively publish GitHub Releases for historical tags that had CHANGELOG entries but no release. All targeted historical tags are now published; the script has no recurring trigger and no compendium reference. Future missing-release recovery is covered by the standard `ci/render_release_notes.py` + `gh release create` flow.
- **`scripts/debug/dump_memories_all.py`** — *resolution: superseded.* Provided a direct ChromaDB dump that bypassed orchestrator filtering. Superseded by `elefante-MemorySearch` with `list_all=true` (returns the full corpus through the supported MCP surface). Keeping a parallel direct-DB dump created drift risk against the live retrieval pipeline.
- **`scripts/debug/list_memories_recent.py`** — *resolution: superseded.* Returned the last 10 memories via the orchestrator. Superseded by `elefante-MemorySearch` with sort/limit (same data, supported surface, no extra script to maintain).
- **Script deletion policy**: Updated `scripts/README.md` Philosophy to require that any script removal land with a `### Removed` CHANGELOG entry naming the resolution reason (`resolved`, `superseded by X`, `abandoned`, `one-time task complete`). Deleting without a record is itself waste.

### Documentation
- **Bug Post-Mortems**: Added detail and root causes for BUG-022 (ChromaDB query filter issue) and BUG-024 (broken venv bundle traversal) to `docs/debug/ops-memory-compendium.md` and `docs/debug/ops-installation-compendium.md`.
- **Mode-routing protocol**: `docs/elefante-orchestrator-agent.md` now defines USER / DEVELOPER / OPERATOR / RELEASE / PRIVILEGED modes with exclusive script authority per mode. DEVELOPER mode carries the explicit symptom→script routing table (covers `verify_scoring_sandbox.py`, `list_mcp_tools.py`, `manage_lock.py`, `reset_kuzu_nuclear.py`, etc.) so each `scripts/debug/*` invocation maps to a stated diagnostic question.

---

## [2.9.2] - 2026-04-17

### Fixed

- **Installer bundle build crashed on local `.venv.broken.*` backups (BUG-024)**: `scripts/ci/build_installer_bundle.py` excluded only the exact `.venv` directory, so a recovered workspace with `.venv.broken.<timestamp>` tried to package broken interpreter symlinks and failed with `FileNotFoundError`, leaving stale `dist` artifacts in place. Why: the packager's top-level exclusion logic matched one directory name instead of the full local-environment family created by recovery flows. What: the packager now excludes top-level `.venv*` directories, raises a targeted runtime citation if an unexpected broken symlink still reaches the archive step, and is guarded by a broken-backup regression in `tests/test_installer_bundle.py`. Impact: installer bundles and downstream DMGs can be rebuilt again from a repaired local workspace.

## [2.9.1] - 2026-04-17

### Fixed

- **MemoryAdd broken for preference memory type (BUG-022)**: `elefante-MemoryAdd` with `memory_type="preference"` always failed with `ChromaDB InternalError: Error executing plan: Internal error: Error finding id`. Why: the preference reassertion merge (STEP 1.75, `orchestrator.py:361`) passed `where_override={"memory_type": "preference"}` to `collection.query()`. ChromaDB 1.3.5's Rust backend fails on any `where` filter against large production collections (400+ memories). What: removed the redundant `where_override` argument — the Python-side `pref_like` filter immediately after already handles the same filtering correctly. Impact: MemoryAdd for preferences now succeeds; preference reassertion merge works against the production database. Documented as BUG-022 in `ops-memory-compendium.md #14`.

### Documentation

- **BUG-019/020 deeper analysis**: Extended `ops-installation-compendium.md` Issue #10 with the causal chain from BUG-019 to BUG-020 (multi-edit syntax corruption → syntax rewrite → implicit Tk/Aqua `bg=` assumption → invisible text), residual test gap documentation, and two verified guard test functions. Added `test_installer_app_class_is_importable` (BUG-019 guard) and `test_installer_app_has_no_bg_overrides_on_ttk_labels` (BUG-020 AST guard) to `tests/test_installer_gui.py`. All 4 tests pass.

---

## [2.9.0] - 2026-04-16


### Added

- **Downloadable installer bundle bootstrap path**: Elefante now ships a dedicated stable-path bootstrap surface through `scripts/setup/bootstrap_release_bundle.py` and `scripts/ci/build_installer_bundle.py`. Why: the phase-1 installer product must stop assuming `git clone` and disposable working directories. What: release packaging can now build `elefante-installer-<OS>.zip`, generate top-level installer entrypoints, place the payload into `~/.elefante/app/current` or `%LOCALAPPDATA%\Elefante\app\current`, and then delegate the real setup work to the installed `scripts/setup/install.py`. Impact: Elefante now has a real installer-bundle path without forking installer logic.
- **Branded macOS DMG installer**: `scripts/ci/build_dmg.py` wraps the installer bundle zip into a compressed `.dmg` with the Elefante logo as volume icon, branded README, and www.elefante.ai link. Why: macOS users expect a native disk image, not a raw zip. What: CI builds the DMG on macOS after the installer bundle, uploads it as a release artifact. Optional `--sign` for notarized releases. Impact: GitHub Releases now ship a branded `.dmg` alongside the existing zip bundles. Spec: `spec-vision.md` section F.
- **Native macOS AppKit installer (primary surface)**: `scripts/ci/installer_app.swift` is a native AppKit installer compiled into the DMG `.app`. Why: Tk/Aqua failed the screenshot gate in BUG-020 — a live widget tree is not proof of a usable UI, and a polished macOS installer experience requires a native presentation layer. What: 794-line Swift installer with a branded window, install-path picker, real-time progress, scrollable output log, and — critically — recovery-file paths (summary, status, log) surfaced in the UI before installation starts with one-click open actions for each. `scripts/ci/build_dmg.py` compiles the AppKit binary when Swift is available and ships it as the primary `.app`. Impact: the DMG now opens a native AppKit window; Tk is demoted to fallback only.
- **Tk installer retained as compatibility fallback**: `scripts/ci/installer_gui.py` now acts only as the fallback when Swift compilation is unavailable. Why: users without a Swift toolchain still need a graphical install path. What: the module now exports `build_install_artifact_paths()` and `render_failed_install_guidance()` at module level so the fallback UI surfaces the same persisted recovery files (summary → status → log) that the AppKit surface does. Impact: both surfaces route failures to the same durable evidence files; contract parity is guarded by `tests/test_installer_gui.py`.

### Changed

- **Release pipeline now publishes installer bundles alongside binary artifacts**: `.github/workflows/build-binaries.yml` builds and uploads platform-specific installer zips, and `scripts/ci/select_release_assets.py` now considers those installer artifacts during release publication. Why: the phase-1 installer product must be a downloadable release artifact, not just a PRD. What: CI now packages the bundle after dashboard assets are built and keeps the selection logic locally testable. Impact: GitHub Releases can ship a stable-path installer bundle for Elefante instead of only the PyInstaller runtime bundle.

### Fixed

- **BUG-019: DMG GUI installer .app regression** — `installer_gui.py` was corrupted by overlapping multi-edit patches during a dark-to-light palette rewrite. Fatal `SyntaxError` at line 173, undefined variables, duplicate widget constructors. The `.app` exited immediately with code 1. Rewrote the corrupted UI construction zone (~140 lines) as a single coherent light-mode version. See `ops-installation-compendium.md` Issue #10.
- **BUG-020: DMG installer customer surface broken** — the `.app` launched, `GUI_RUNNING=YES` passed, and the Tk widget tree was intact, but the rendered macOS window remained visually broken. Root cause: Tk/Aqua was an unreliable foundation for a polished macOS customer installer. Fix: pivoted the primary surface to a native AppKit installer (`scripts/ci/installer_app.swift`) compiled by `build_dmg.py` when Swift is available, with Tk retained only as fallback. Recovery-file routing (summary/status/log) is now exposed in the installer UI before failure. Contract parity and stage-marker dedup are guarded by `tests/test_installer_gui.py`; customer-visible screenshot of the packaged `.app` remains the authoritative final proof. See `ops-installation-compendium.md` Issue #11.

### Documentation

- **Installer procedure PRD corrected to phase 1**: `docs/planning/spec-installer-procedure.md` now defines the correct first milestone for installer work: a downloadable Elefante installer product that removes `git clone` from the end-user flow while preserving `scripts/setup/install.py` as the single installation authority. Why: the real gap is product packaging and first-run entrypoint, not provider selection. What: the draft now centers stable install location, visible terminal UX, cancel/status/log behavior, bundled dashboard assets, and maintained Elefante verifiers, while explicitly deferring provider choices to phase 2. Impact: installer work is now scoped to the actual highest-risk surface without mixing in optional runtime-provider features too early.
- **BUG-019 post-mortem**: Added to `ops-installation-compendium.md` Issue #10, `best_practices.md` (multi-edit syntax verification rule), and Known Issues table.
- **BUG-020 post-mortem closed**: `ops-installation-compendium.md` Issue #11 updated to past-tense Solution + status FIXED. `best_practices.md` rules "Screenshot Beats Widget Introspection For Customer UI", "Installer Failures Must End With Persisted File Routing", and "Installer UI Must Expose Recovery Files Before Failure" guard the lessons.

---

## [2.7.1] - 2026-04-15

### Fixed

- **BUG-015 — release-stage failure narrowed to GitHub's 2 GiB asset cap**: The `v2.6.0` release object was created and macOS/Windows assets uploaded successfully, but the Linux artifact measured `4,021,041,080` bytes and caused `Create GitHub Release` to fail. Why: GitHub Actions artifacts can exceed the GitHub Releases per-file cap. What: `.github/workflows/build-binaries.yml` now delegates asset filtering to `scripts/ci/select_release_assets.py`, only passes files under `2 GiB` to `softprops/action-gh-release@v1`, reports skipped oversized assets in the job summary, and is guarded locally by `pytest tests/test_release_pipeline.py -v`. Impact: the release-stage logic is now explicit and locally guarded; live closure still depends on a fresh tag publish.

### Changed

- **GitHub release bodies are now generated from CHANGELOG**: release publication now checks out the repo, renders `release-notes.md` via `scripts/ci/render_release_notes.py`, and passes that file to `softprops/action-gh-release@v1` through `body_path`. Why: generated GitHub release pages were too sparse and often failed to explain the version meaning. What: every tag now ships with curated release notes plus links to README, the full changelog, installation, and debugging docs. Impact: version bumps are documented at the release page itself instead of relying on empty shells.

### Documentation

- **Versioning and release docs corrected**: `CONTRIBUTING.md` now points to `scripts/ci/advise_version_bump.py` instead of the stale `version_counsel.py` name, and `README.md` now explains where release notes live. Why: current versioning docs drifted from the actual scripts and release flow. What: updated commands, rules, and links. Impact: the documented release process now matches the live repo.

---

## [2.7.0] - 2026-04-15

### Fixed

- **BUG-016 — Domain signal removed from scoring**: The domain signal (15% weight) was dysfunctional — `analyze_query()` inferred `None`/`"work"`/`"personal"` but memories default to `DomainType.REFERENCE`. Value spaces never intersected. Weight redistributed to vector (0.35) and concept (0.30).
- **BUG-017 — Spec override intent-gated**: The `+0.30` specification/directive boost was unconditional, creating a ranking monopoly on all queries. Now gated on `query.inferred_intent == "system"` (keywords: spec, directive, rule, requirement, architecture, constraint, sdd, compliance).
- **BUG-018 — Co-activation cold-start resolved**: `_session_retrieval_history` reset to `[]` on every server restart. Now persisted to `DATA_DIR/session_retrieval_history.json` with 7-day expiry. First query of a new session can leverage prior session context.

### Changed

- **Vector baseline floor lowered**: From `0.85 * vector_score` to `0.70 * vector_score`, giving the composite formula more room to differentiate.
- **Scoring weights**: 5-signal model (domain removed): vector=0.35, concept=0.30, coactivation=0.15, authority=0.10, temporal=0.10.
- **System intent detection**: `analyze_query()` now detects `"system"` intent for specification/architecture queries.

### Documentation

- Full bug post-mortems added to `ops-memory-compendium.md` (Issues #11, #12, #13).
- `spec-architecture.md` updated for V4.1 scoring model.
- `best_practices.md` updated with Write→Read Value-Space Verification rule.

---

## [2.6.0] - 2026-04-15

### Added

- **Installer `.venv` strategy prompt**: One-click installation now asks how to handle an existing repository virtual environment before dependency work starts. Why: reruns previously reused `.venv` silently, which made stale or wrong-version environments too easy to carry forward. What: `scripts/setup/install.py` now offers four explicit choices when `.venv` exists — fresh delete and reinstall (default), backup+fresh, reuse, or abort — and records the decision before proceeding. Impact: reinstall behavior is explicit, recoverable, and safer during upgrades or repairs.

### Changed

- **Wrapper installers no longer activate `.venv` before the installer decides**: `install.sh` and `install.bat` now launch `scripts/setup/install.py` directly with the detected compatible Python instead of sourcing the existing `.venv` first. Why: activating a stale environment before installer logic ran recreated the same ambiguity the installer is meant to resolve. What: environment selection moved into the Python installer as the single authority. Impact: fresh reinstall and backup+fresh paths can run before any stale repo-local interpreter is trusted.

### Documentation

- **Installation flow updated for explicit `.venv` choices**: The README, technical installation guide, and scripts overview now describe the new existing-environment prompt and the safer PowerShell/manual entrypoint. Why: install docs previously implied `.venv` would always be silently reused or freshly created. What: the new docs explain the four choices and the default destructive reinstall path. Impact: operators know exactly what will happen to an old repository environment before rerunning the installer.

---

## [2.5.5] - 2026-04-15

### Fixed

- **Verification and maintenance scripts no longer crash at import time**: `scripts/verify/verify_mcp_handshake.py`, `scripts/pipeline/update_dashboard_data.py`, and `scripts/lifecycle/reset_factory.py` shipped with missing imports and a malformed module header. Why: the documented verification and recovery ladder could fail before doing any useful work. What: restored the missing imports and repaired the `_utc_ts()` helper/module preamble. Impact: handshake verification, dashboard snapshot refresh, and factory reset utilities execute instead of dying on load.
- **Maintained regression tests run cleanly in isolated environments again**: `tests/test_memory_guard.py`, `tests/test_developer_routing.py`, `tests/test_no_emojis.py`, and `tests/test_refinery.py` were missing required imports, and `tests/test_memory_persistence.py` dropped model-cache environment variables in its subprocess harness. Why: the full suite could fail for harness drift rather than product regressions. What: added the missing imports and propagated `HF_HOME`, `TORCH_HOME`, and `SENTENCE_TRANSFORMERS_HOME` into the live MCP shutdown-regression subprocess. Impact: the Python 3.11 verification path returns to a trustworthy full-suite pass state.

### Documentation

- **BUG-014 scope clarification + BUG-015 logging**: Debug documentation now separates the already-fixed matrix build failure from the new open release-stage failure in `Build One-Click Binaries`. Why: the latest warning email shows all three platform builds succeeded, which proves the v2.5.4 build-stage fix held. What: `docs/debug/README.md` keeps BUG-014 fixed and adds BUG-015 as an open release-publication issue; `docs/debug/ops-installation-compendium.md` adds Issue #9 with the proven fault boundary (`actions/download-artifact` / `softprops/action-gh-release`) and explicitly marks root cause as unknown pending the failed job log. Impact: future debugging starts at the release job instead of relitigating the resolved frontend/dist failure.
- **No-emoji policy cleanup in active docs**: Active documentation and changelog rows no longer rely on emoji/status glyphs in user-facing policy tables. Why: the no-emoji guard treated those markers as test failures. What: converted archive/warning/import-status markers to plain-text equivalents and added the rule "A Green Build Matrix Is Not A Release Proof" to `docs/debug/best_practices.md`. Impact: documentation now matches repository policy and the docs themselves stop tripping the guardrails they describe.

---

## [2.5.4] - 2026-04-15

### Fixed

- **BUG-014 — CI binary build: missing frontend build step and wrong Vite output directory**: `build-binaries.yml` had no Node.js/npm step — `src/dashboard/ui/dist/` is gitignored so CI checked out a repo with no built UI. Additionally, `elefante.spec` referenced `src/dashboard/ui/build` but Vite outputs to `src/dashboard/ui/dist` (configured in `vite.config.ts`). The `build/` directory has never existed. Fix: added `setup-node@v4` + `npm ci` + `npm run build` before the PyInstaller step; corrected spec `datas` path from `build` to `dist`. First discovered on v2.5.3 tag push — this was the first binary release attempt. Full post-mortem: `docs/debug/ops-installation-compendium.md` Issue #8.

### Documentation

- **GAP-013 post-mortem**: `docs/debug/ops-ai-behavior-compendium.md` Issue #11 documents the missing import path for JSON exports. Root cause: `export_memories.py` was built for offline analysis, not migration. Embeddings are stored explicitly using `thenlper/gte-base` and are NOT in the JSON output — any import script must regenerate them using the same model or semantic search will be silently corrupted by ChromaDB's default `all-MiniLM-L6-v2`. Import is confirmed feasible (~120 lines, direct ChromaDB upsert). Issue labels the JSON export as read-only analysis output (not a backup) pending `import_memories.py`.
- **BUG-014 post-mortem**: `docs/debug/ops-installation-compendium.md` Issue #8 — CI build pipeline: missing frontend compilation step and wrong spec output path.
- **best_practices.md**: New entry "A Write-Only Export Is Not a Backup" — every export format must document its import path or be explicitly labeled read-only.
- **best_practices.md**: New entry "CI Pipelines Must Build Every Artifact They Package" — gitignored build outputs do not exist in CI; verify output dir names against build tool config before referencing them in build specs.

### Known Gap (next release)

- **`scripts/pipeline/import_memories.py`** — seeds a fresh Elefante install from a JSON export; regenerates embeddings via configured model; supports `--dry-run`, `--skip-existing`, `--conflict skip|overwrite`; closes the round-trip gap (GAP-013).

---

## [2.5.3] - 2026-04-15

### Fixed

- **BUG-012 — Elefante cold-start trigger gap**: Agent never called `elefante-MemorySearch` when working in any workspace other than `elefante/`, because `.github/copilot-instructions.md` is workspace-scoped and only loads when `elefante/` is the VS Code workspace root. Fix is two-layer: (1) system-level — `github.copilot.chat.codeGeneration.instructions` in VS Code user `settings.json` now points to `elefante/.github/copilot-instructions.md`, loading the full Elefante constitution globally for every workspace; (2) workspace fallback — `BOB/.github/copilot-instructions.md` provides a minimal `search_before_assert` bootstrap for the BOB workspace root. ARAA rejected a workspace-only fix as insufficient: the correct scope for behavioral instructions is the broadest available scope, not the narrowest that works in the demo scenario.

### Documentation

- **BUG-012 post-mortem**: `docs/debug/ops-ai-behavior-compendium.md` Issue #10 documents the three-layer root cause (instruction delivery scope vs. MCP registration scope vs. server-side directive cold-start gap), the ARAA audit that rejected the weak fix, and the verification procedure.
- **BUG-012 Known Issues row**: `docs/debug/README.md` now tracks BUG-012 with status FIXED (partial) and a manual verification procedure.
- **best_practices.md**: New entry "Instruction Delivery Scope Must Match The Broadest Usage Scope" — distilled rule from BUG-012, promoting the lesson that workspace-scoped instruction files silently degrade coverage for adjacent usage patterns.

---

## [2.5.2] - 2026-04-15

### Fixed

- **BUG-011 README row**: Status was still showing OPEN after the fix landed in 2.5.1. Row now reads "FIXED (guarded)" with recurrence count updated to 2x and a note on the `rejection_reason` guard.

### Changed

- **`bump_version.py` enforcement gates**: Three new pre-conditions prevent unsafe version cascades: (1) CHANGELOG presence gate — `_check_changelog_entry()` validates a `## [X.Y.Z]` entry exists before writing any file; (2) downgrade guard — `_check_no_downgrade()` blocks any bump where the new semver tuple is ≤ the current one; (3) pattern-miss WARNING — every TARGETS entry that matches zero bytes in its target file now prints a WARNING line and is collected in a `warned` list shown at the end. Previously all three conditions were silent.
- **`bump_version.py` TARGETS expanded**: 9 new targets added covering all living documentation that carries a version declaration: `docs/technical/ops-installation.md`, `docs/planning/spec-vision.md`, `docs/technical/ops-rollback.md`, `docs/technical/spec-ingestion.md`, `docs/debug/best_practices.md`, `docs/debug/ops-ai-behavior-compendium.md`, `docs/debug/ops-dashboard-compendium.md`, `docs/debug/ops-installation-compendium.md`, `docs/debug/ops-memory-compendium.md`. Previously these could drift silently across bumps.
- **Version headers added to 7 living docs**: `best_practices.md`, `ops-ai-behavior-compendium.md`, `ops-dashboard-compendium.md`, `ops-installation-compendium.md`, `ops-memory-compendium.md` now declare `**Applies to**: v2.5.2+`; `ops-rollback.md` and `spec-ingestion.md` now declare `**Version**: 2.5.2`. Without these declarations the documents could silently describe stale behaviour.

### Removed

- **8 redundant archive files deleted**: `docs/archive/kuzu-best-practices.md`, `docs/archive/kuzu-lock-monitoring.md`, `docs/archive/ELEFANTE_DEVELOPMENT_SKILLS.md`, `docs/archive/memory-schema-v4-cognitive.md`, `docs/archive/memory-schema-v5-topology.md`, `docs/archive/python-version-requirements.md`, `docs/archive/RELEASES.md`, `docs/archive/planning/v5-cognitive-retrieval-requirements.md`. All content was already superseded by and present in living documentation. Retaining them created confusion about canonical source.
- **Empty folder `docs/debug/phoenix-handoff-2026-04-13/` deleted**.

### Documentation

- **ARCHIVED banners on 12 historical archive files**: All remaining files in `docs/archive/` now carry `> [ARCHIVED] — ...` banners immediately after the title, with an explicit pointer to the current living document. Readers can no longer mistake historical snapshots for current guidance.
- **Agent-oriented headers — all 22 scripts**: Every file in `scripts/` now carries a `NAME · VERSION · CHANGED · PURPOSE · WHEN · USAGE · NOTES · LASTRUN` header block with concrete trigger conditions (WHEN) and prerequisites/caveats (NOTES). Previously headers described what a script does but gave no guidance on when to reach for it vs. an alternative. `LASTRUN` is now a fillable placeholder (`yyyy-mm-dd hh:mm — update manually`) rather than the static "not tracked".
- **MODULE headers — all `src/` Python files**: Every substantive file in `src/core/`, `src/mcp/`, `src/utils/`, `src/models/`, `src/main.py`, and `src/desktop.py` now carries a `MODULE · VERSION · CHANGED · PURPOSE · ROLE · TOUCHED` header with critical TOUCHED warnings (e.g., the BUG-010 concurrency constraint in `embeddings.py`, the Kuzu schema-reset requirement in `graph_store.py`).
- **TEST headers — all 14 `tests/` files**: Every test file now carries a `TEST · VERSION · CHANGED · PROVES · RUN · WHEN` header documenting the exact contract each suite guards and the precise `pytest` invocation to run it.
- **`scripts/README.md` complete rewrite**: Rewritten with 4-column tables (What / When / Why / Why Here) per script group, a verification ladder (`verify_health → verify_mcp_handshake → verify_e2e_tests`), a 5-step release workflow sequence, and a lock guidance section. Old entries for the 4 deleted scripts removed; `export_memories.py --format` documented.

### Removed

- **4 scripts merged and originals deleted**: `scripts/debug/remove_lock_kuzu.py` and `scripts/debug/unlock_database_transactions.py` were merged into `scripts/debug/manage_lock.py` (adds `--kill` flag; dry-run by default; requires `ELEFANTE_PRIVILEGED=1 --apply --confirm DELETE`). `scripts/pipeline/export_memories_csv.py` and `scripts/pipeline/export_memories_json.py` were merged into `scripts/pipeline/export_memories.py` (unified `--format json|csv|all` flag). The two originals for each merge were strict subsets with no independent functionality — retaining them created duplicate maintenance surfaces.

---

## [2.5.1] - 2026-04-15

### Fixed

- **BUG-010 — Self-protocol cold-start deadlock**: `from sentence_transformers import SentenceTransformer` (which imports torch) deadlocks indefinitely when executed in a worker thread under an active anyio 4.x event loop with piped stdio on Windows + Python 3.11. Root cause was misdiagnosed twice: first as a timeout (90 → 180 s had no effect) then as a threading issue (`asyncio.to_thread` moved the deadlock rather than eliminating it). Fix: pre-load the embedding model synchronously in `server.py __main__` before `asyncio.run()`. `_load_model()` becomes a no-op at runtime because `self._model` is already set. Self-protocol result: 45/45 PASS, 1 SKIP, 0 FAIL.
- **BUG-010 ARAA follow-up — contradicting docstring**: `src/core/embeddings.py` CONCURRENCY RULE docstring previously stated the model "MUST run via `asyncio.to_thread()`" — directly contradicting the fix and guiding future contributors toward the deadlock. Docstring now states operations DEADLOCK in a worker thread and MUST be pre-loaded in `__main__` before `asyncio.run()`.
- **BUG-010 ARAA follow-up — silent fallback**: `generate_embeddings_batch()` retains `asyncio.to_thread(self._load_model)` as a last-resort path for non-`__main__` entry points, but now fires `logger.critical("embedding_model_not_preloaded")` with an explicit BUG-010 attribution before attempting it. The failure path is no longer silent.
- **BUG-011 — MemoryAdd silent IGNORE with opaque rejection reason**: `elefante-MemoryAdd` was returning `status: ignored` with only `"Memory filtered by Intelligence Pipeline"` and no indication which of the 9 heuristic conditions fired. Fix: `src/core/orchestrator.py` now captures `_last_rejection_reason` with the exact condition label and `src/mcp/server.py` injects it as `rejection_reason` in the IGNORE response body. Agents can now correct and retry without guessing.

### Changed

- **BUG-010 platform scope in `docs/debug/README.md`**: BUG-010 status row now reads "FIXED (guarded) [WARN] Windows/Python 3.11/CPU only — untested on Linux, macOS, Python 3.12" to prevent overclaiming across untested configurations.
- **`docs/debug/best_practices.md`**: Replaced the stale "Verifier Timeout Constants" entry (written when the bug was misdiagnosed as a timeout) with three updated/new entries: (1) "Verifier Timeout Constants" — reframed to note the initial timeout misdiagnosis, (2) "Heavy Imports Must Run Before The Event Loop" — rule against deferring C-extension imports to `asyncio.to_thread`, (3) "Differentiate Slow From Hung Before Choosing A Fix" — heuristic: if 2× timeout still fails, investigate deadlock not latency.

## [2.5.0] - 2026-04-15

### Added

- **Token intelligence**: Every tool response now includes a `TOKEN_STATS` block with `output_tokens`, `overhead_tokens`, and `signal_ratio`. Agents can see what each tool call costs in tokens and how much is payload vs. protocol overhead. New module `src/utils/token_counter.py` provides heuristic token counting with negligible CPU cost and multilingual support (CJK/Arabic ratio blending). Memory type budgets (`specification`: 800, `directive`: 200, etc.) drive proportionality scoring. `elefante-MemoryAdd` responses now include `content_tokens`, `token_density`, and a `density_warning` when content exceeds 2.0x its type budget. 39 new tests in `tests/test_token_intelligence.py` guard the full surface.
- **Token Intelligence architecture section**: `docs/technical/spec-architecture.md` now documents the 6-step token measurement pipeline (heuristic counting, overhead measurement, per-call snapshots, session ledger, type-proportional budgets, TOKEN_STATS injection).
- **TOKEN_STATS in tool response contract**: `docs/technical/spec-tools.md` now documents `TOKEN_STATS` as part of the standard tool response contract alongside `MANDATORY_PROTOCOLS`, `DIRECTIVES`, and `RELEVANT_CONTEXT`.
- **TOKEN_STATS in agent constitution**: `.github/copilot-instructions.md` `tool_response_contract` rule now documents TOKEN_STATS fields and includes actionable TOKEN_STATS AWARENESS guidance (signal_ratio < 0.3, density_warning thresholds).
- **E2E TOKEN_STATS assertions**: `scripts/verify/verify_e2e_tests.py` now verifies TOKEN_STATS presence and field validity on success responses, error responses, and MemoryAdd responses (content_tokens, token_density). 46/46 E2E checks.
- **Token Intelligence PRD**: `docs/planning/spec-token-intelligence.md` formally specifies the feature with honest leakage surface scan, success criteria, deferred items, risks, and competitive position.

### Fixed

- **Dynamic stats_overhead (ADV-013)**: `stats_overhead` in `_record_and_inject_token_stats()` is now computed dynamically via `estimate_tokens_json()` instead of a magic constant. Previously hardcoded at 45, then 25 -- both drifted from reality. Dynamic measurement (currently 22 tokens) can never drift.
- **"zero CPU" false claim (ADV-011)**: `src/utils/token_counter.py` docstrings corrected from "zero CPU cost" to "negligible CPU cost".
- **PRD leakage honesty (ADV-016)**: Dashboard snapshot row in `docs/planning/spec-token-intelligence.md` changed from "PASS (by design)" to "FAIL (accepted risk)" with explicit rationale.
- **spec-vision.md tool count**: Changed "21 MCP tools" to "20 MCP tools and 2 prompts" to match the live surface.

### Changed

- **spec-vision.md shipped table**: Token intelligence now listed as a shipped capability.
- **README.md Layer 1 description**: Now describes Token Intelligence alongside Compliance Gate, Context Injection, and Directives.

## [2.4.1] - 2026-04-13

### Added

- **Self-Elefante protocol**: `scripts/verify/verify_e2e_tests.py` now serves as the authoritative isolated whole-system verifier. It proves the live MCP tool/prompt inventory, prompt retrieval, routing injection, compliance gate, memory/graph/context/session/task/ETL/refinery flows, restart persistence, and cleanup in a temporary Elefante home/data directory. `--with-dashboard-open` enables the browser/port side-effect tool only in explicit full-surface mode.
- **Whole-system verification doc**: `docs/debug/self-elefante-protocol.md` now explains when to use the self-protocol, what it proves, how cleanup works, and why `elefante-DashboardOpen` stays opt-in by default.

### Fixed

- **Graph/session schema contract drift**: `src/core/graph_store.py` now creates `CREATED_IN` and `WORKS_ON` relationships without injecting unsupported `strength` properties, and `src/mcp/server.py` now lists synthetic session entities by `created_at` while parsing optional metadata from JSON `props`. `tests/test_memory_persistence.py` guards both contracts.
- **Self-protocol verifier drift**: `scripts/verify/verify_e2e_tests.py` now accepts the live home-derived dashboard snapshot path during `--with-dashboard-open` and sizes the MCP subprocess stream for large `ContextGet` payloads, so the maintained 20-tool proof no longer reports false failures.

### Changed

- **Verification routing**: `docs/debug/README.md`, `docs/debug/dev-developer-agent.md`, `docs/README.md`, `scripts/README.md`, and `tests/README.md` now route "is Elefante actually running?" claims through the maintained self-protocol instead of relying on a collection of narrow regressions.
- **Closure rules**: `docs/technical/dev-sdd.md`, `docs/technical/dev-etiquette.md`, built-in system directives, and the seeded Developer Etiquette specification now all enforce the live changelog contract `### Added` / `### Fixed` / `### Changed` plus the choose-then-apply versioning flow `advise_version_bump.py` -> `bump_version.py`. `tests/test_developer_routing.py` guards the contract.
- **Scripts documentation**: `scripts/README.md` now documents every live script as an operator entrypoint, explains why each subdirectory exists, and distinguishes overlapping recovery tools like the two write-lock helpers. `tests/test_developer_routing.py` now guards the live scripts inventory and the privileged script command names.
- **Tool-surface auditability**: `scripts/ci/list_mcp_tools.py` now reports tools and prompts separately from source instead of mislabeling the 2 prompts as tools, and `docs/debug/self-elefante-protocol.md` now includes an explicit coverage map for every live tool and prompt. `tests/test_developer_routing.py` guards both surfaces.
- **Prompt and response-contract docs**: `docs/technical/spec-tools.md` now documents that `RELEVANT_CONTEXT` is conditional and that `elefante-context` requires a `topic` argument and performs a live hybrid search. The manual registration checker `tests/manual/test_tools.py` now audits tools and prompts separately against the current surface.

## [2.4.0] - 2026-04-13

### Fixed

- **BUG-006 agent entry point bypass**: The MCP server now injects the exact developer entry sequence into every tool response, including failure responses. The first successful and first failing tool calls now both route through `docs/debug/README.md`, the matching verification command, the linked compendium, and `tests/README.md` instead of exposing only generic passive hints.

### Changed

- **Tool response contract**: `ENTRYPOINT_SEQUENCE_READ_THIS_FIRST` is now part of the live MCP response contract alongside `MANDATORY_PROTOCOLS_READ_THIS_FIRST`, `DIRECTIVES`, and optional `RELEVANT_CONTEXT`.

### Added

- **BUG-006 live proof**: `scripts/verify/verify_e2e_tests.py` now proves entry routing on both success and failure paths, and `tests/test_autonomous_coactivation.py` now guards the source-level entrypoint injection contract.

## [2.3.1] - 2026-04-13

### Fixed

- **Developer routing drift**: Active developer-process guidance no longer routes through deleted files like `docs/pitfall-index.md` or retired doc names. Gate 0 now routes debugging through `docs/debug/README.md`, changelog reads are assumption-driven instead of ritual, and the MCP handshake expectation is corrected to 20 tools.
- **Tool reference drift**: `README.md`, `docs/README.md`, and `docs/technical/spec-tools.md` now match the live MCP schema in `src/mcp/server.py`, including the 20-tool plus 2-prompt surface, current ETL fields, and the correct dashboard operations doc path.

### Changed

- **Bug tracking**: `docs/debug/README.md` and `docs/debug/ops-ai-behavior-compendium.md` now record BUG-007 with a formal post-mortem, exact proof command, and guarded status.

### Added

- **Developer routing regression**: `tests/test_developer_routing.py` now guards active developer-routing files against retired paths and verifies the current contract points to the right docs and tool-count expectation.

## [2.3.0] - 2026-04-13

### Fixed

- **Stale verification surface**: the maintained test/docs path now prefers existing `scripts/verify/*` and `tests/README.md` coverage over scratch validation, the dashboard serializer file is now real pytest coverage, the MCP smoke test no longer swallows generic failures, and stale extension-era or deleted-script references were removed from active docs and tests.
- **Kuzu lock contention**: `GraphStore.close()` now calls the actual `kuzu.Connection.close()` and `kuzu.Database.close()` APIs. Previously these were commented out, leaving the OS-level exclusive file lock held indefinitely. `reset_graph_store()` also now calls `close()` before setting `_graph_store = None`.
- **Kuzu native shutdown crash**: eliminated a persistent macOS `SIGSEGV` race where MCP tools could close the global `GraphStore` while background co-activation work or leaked `QueryResult` objects were still alive. `GraphStore` now serializes Kuzu access, materializes rows inside the worker thread, and waits for in-flight operations before closing.
- **MCP cold-start handshake timeout**: `src.mcp.server.run()` no longer blocks `initialize` behind orchestrator and embedding-model warmup. Fresh stdio sessions now answer the MCP handshake immediately, while system baseline seeding occurs on first orchestrator use.
- **Ghost memories after delete**: `elefante-MemoryDelete` now removes the matching graph entity as well as the Chroma record, so hybrid search and graph-backed retrieval cannot surface deleted memories after a successful delete.
- **Standalone E2E harness drift**: `scripts/verify/verify_e2e_tests.py` now provisions its own temporary HOME and `ELEFANTE_DATA_DIR`, enables test-memory mode for spawned MCP servers, and reports the current Elefante version dynamically. The shipped verifier no longer depends on external shell env setup to avoid polluting the user's durable store.
- **Fresh-install SDD drift**: new installs now get the runtime SDD baseline from core code. `DirectiveStore` exposes built-in system directives immediately, and `MemoryOrchestrator.ensure_system_baseline()` idempotently seeds the required specification memories on first use.
- **Regression coverage gap**: the crash fix is now guarded three ways: a static raw-Kuzu-boundary test, an isolated live MCP subprocess regression under pytest, and the shipped E2E harness now exercises the repeated search/co-activation shutdown-race path.
- **Version drift in specification docs**: `scripts/ci/bump_version.py` now updates `docs/technical/developer-etiquette.md`, `docs/technical/sdd-development-protocol.md`, and the footer version in `docs/technical/README.md`, preventing manual semver drift in closure-critical docs.
- **E2E harness residue**: `scripts/elefante_e2e_test_engine.py` now runs against an isolated temporary Elefante home/data directory and fails if tagged test memories remain after cleanup, preventing verification runs from polluting the real store.
- **Dashboard semantic search broken**: `/api/search` returned nested `{memory: {id, content, metadata}, score}` but the frontend expected flat `{id, content, metadata, similarity}`. All search results rendered as blank rows. Fix: flatten the response in `server.py` to match the TypeScript `SearchResult` interface.
- **Dashboard "Untitled" memories**: 3 memories with empty `title` metadata in ChromaDB now backfilled. Snapshot script fallback improved to extract first 10 words (matching `generate_title()`) instead of 5.
- **Purged 200 test memories**: `entity_target_0` through `entity_target_99` (duplicated twice) were polluting ChromaDB. Deleted from vector store. Added `entity_target` pattern to `_is_test_artifact()` so snapshot never includes them again.

### Changed

- **Documentation authority alignment**: active docs now treat SDD as legacy/internal terminology, route verification through `docs/debug/dev-developer-agent.md`, remove the deleted VS Code extension from the active vision surface, and reframe the live E2E harness around concrete MCP verification goals.
- **Debug-to-test routing**: every `ops-*-compendium.md` now has a Verification Commands table mapping documented issues to specific `pytest` targets. `docs/debug/README.md` is now a Known Issues tracker (BUG-001 through BUG-006) with status, compendium link, exact verification command, and recurrence count. Runtime error messages in `graph_store.py` and `server.py` now cite the relevant compendium entry so agents are routed to documentation through terminal output, not discipline.
- **Dashboard score differentiation**: Replaced pure exponential-decay score in `_compute_live_score()` with a composite metric: 50% temporal vitality + 25% memory-type weight + 25% engagement (access frequency). Specifications/decisions now rank visibly higher than conversations; frequently-accessed memories score above one-shot entries. Score Distribution chart now shows a meaningful spread (range ~58-95) instead of 84% clustering at 100.
- **Agent entry-point docs**: installation and IDE configuration docs now explicitly document the `AGENT.md` role-adoption entry point alongside `.cursorrules` and `.windsurfrules`.
- **Cleanup**: removed the unreferenced `docs/planning/walkthrough.md` delivery artifact so the repo keeps only durable docs, specs, and changelog state.

### Added

- **Factory reset test**: `tests/test_factory_reset.py` — 10 tests covering dry-run safety, all 3 rejection gates (ELEFANTE_PRIVILEGED, --confirm DELETE, --apply), backup creation with content preservation, clean-state idempotency, and double-reset. All tests run against an isolated temp HOME; real user data is never touched.
- **Known Issues tracker**: `docs/debug/README.md` now serves as the root bug-resolution entry point with a BUG-NNN table that links every tracked issue to its compendium post-mortem, verification command, and recurrence count.
- **Runtime compendium citations**: `graph_store.py` error paths now print the exact compendium issue path (e.g., `docs/debug/ops-database-compendium.md Issue #7`) in the error message. `server.py` catch-all appends `docs/debug/README.md -> Known Issues` to unrecognized tool failures. Agents that never read docs still get routed.

---

## [2.2.2] - 2026-03-28

### Summary

Dashboard Scoring Structural Fix — Eliminated the all-scores-100 bug architecturally by extracting a single shared serializer, hardening the installation pipeline, and merging upstream documentation.

### The Problem Solved

Dashboard scores were all stuck at 100 because two independent code paths (MCP server and standalone script) each had inline score-computation that read stale `mem.metadata.score` instead of live-computing from decay + type + engagement. Fixing one path left the other broken. The installation process never generated a snapshot, so fresh installs showed a blank dashboard.

### The Solution

1. **Single serializer** — `src/utils/dashboard_serializer.py` is now the sole source of truth for Memory → dashboard-node conversion with live composite scoring.
2. **MCP server cleaned** — `_refresh_dashboard_snapshot()` replaced ~50 lines of inline node-building with a single import from the shared serializer.
3. **Standalone script cleaned** — `scripts/pipeline/update_dashboard_data.py` removed all duplicate helpers (`_redact_secrets`, `_derive_topic`, `_compute_live_score`, `_is_test_artifact`); imports from shared serializer.
4. **Install hardened** — `scripts/setup/install.py` Step 3a now generates a dashboard snapshot at install time.
5. **Validator hardened** — `scripts/validate_dashboard_snapshot.py` now detects score staleness (>25% at score=100 = FAIL).
6. **Upstream merged** — GitHub origin/main merged cleanly (zero conflicts). Brought in `ELEFANTE_DEVELOPMENT_SKILLS.md` (AI agent guide) and Issue #7 (IBM Bob MCP settings path) in installation-compendium.

### Fixed

- **All dashboard scores stuck at 100** (Issue #9): Root cause was two divergent inline serializers reading stale `mem.metadata.score`. Fixed by extracting `dashboard_serializer.py` as single source of truth. Verified: 74 memories, Score=100: 0, Avg: 75.3, Min: 54, Max: 94.
- **Kuzu lock contention**: `GraphStore.close()` now calls `kuzu.Connection.close()` and `kuzu.Database.close()` APIs. Previously commented out, leaving the OS-level exclusive file lock held indefinitely.
- **Dashboard semantic search broken**: `/api/search` response flattened to match frontend `SearchResult` interface.
- **Dashboard "Untitled" memories**: Backfilled 3 empty-title memories. Improved fallback to extract first 10 words.
- **Purged 200 test memories**: `entity_target_0..99` (duplicated twice) deleted from ChromaDB. Added `entity_target` to `_is_test_artifact()`.
- **No snapshot at install time**: Fresh installs showed blank dashboard. Added Step 3a to `install.py`.

### Added

- `src/utils/dashboard_serializer.py` — shared serializer with `_composite_dashboard_score()`, `compute_live_score()`, `memory_to_dashboard_node()`, `is_test_artifact()`, `_redact_secrets()`.
- `tests/test_dashboard_serializer.py` — unit tests with delta=0 cross-validation between Memory-object and raw-dict scoring paths.
- `tmp/verify_scores.py` — quick diagnostic for score health checks.
- Score staleness detection in `validate_dashboard_snapshot.py`.
- Issue #9 in `docs/debug/ops-dashboard-compendium.md` with Critical Laws 8-9.
- Score Contract section in `docs/technical/dashboard-snapshot-contract.md`.
- `ELEFANTE_DEVELOPMENT_SKILLS.md` — AI agent development guide (merged from upstream).
- Issue #7 (IBM Bob MCP settings) in `docs/debug/ops-installation-compendium.md` (merged from upstream).

### Changed

- **Dashboard score formula**: Composite metric (50% temporal vitality + 25% type weight + 25% engagement) replaces pure exponential-decay. Meaningful spread (range ~54-94) instead of 84% at 100.
- MCP server `_refresh_dashboard_snapshot()` reduced from ~50 lines to a 3-line import loop.
- `scripts/pipeline/update_dashboard_data.py` reduced by ~150 lines (removed all duplicate helper functions).

---

## [2.2.1] - 2026-03-20

### Summary

Native SDD Enforcement — Static markdown protocol replaced with living Elefante mechanisms. Elefante now eats its own dogfood: SDD gates are enforced through DIRECTIVES (unconditional injection), SPECIFICATION memories (authority=1.0, immutable), and a mechanical pre-commit hook.

### The Problem Solved

The SDD protocol (v2.2.0) was documented as a static markdown file — repeating the exact anti-pattern Elefante v1.x → v2.1.0 proved doesn't work. Rules in docs drift. Rules in memories can be outcompeted. Only mechanical enforcement and unconditional injection are reliable.

### The Solution

1. **6 SDD DIRECTIVES** — Injected into every MCP tool response unconditionally: Gate 0 (source-first), Critical Blocker, Gate 2 (leakage scan), Gate 3 (numeric verification), Gate 4 (simulator), Stdout Purity Law.
2. **2 SPECIFICATION memories** — Gate 2 (full 8-surface leakage table) and Gate 3 (exact scoring formulas) stored with authority=1.0, zero decay. Always surface when relevant.
3. **Mechanical pre-commit hook** — `.git/hooks/pre-commit` runs `health_check.py` + `verify_mcp_handshake.py` before every commit. Failure = blocked.
4. **MCP schema fix** — Added `specification` and `directive` to `memory_type` enum in `elefante-MemoryAdd` tool schema (v2.2.0 gap: Python model had these types but MCP schema didn't expose them).
5. **Static doc reframed** — `docs/technical/sdd-development-protocol.md` marked as human reference only. Enforcement is native.
6. **Directive cleanup** — Removed 2 test/garbage directives (`"Filter of"`, hello-world variable name test).

### Changes

- **MODIFIED**: `src/mcp/server.py` — Added `specification` and `directive` to `memory_type` enum in tool schema.
- **NEW**: `.git/hooks/pre-commit` — Mechanical Gate 4 enforcement (health check + MCP handshake).
- **MODIFIED**: `docs/technical/sdd-development-protocol.md` — Reframed as human reference; version 2.2.1.
- **MODIFIED**: `docs/technical/README.md` — Updated SDD doc description.
- **MODIFIED**: `docs/README.md` — Updated SDD doc description.
- **MODIFIED**: `CONTRIBUTING.md` — Replaced SDD blockquote with native enforcement pointer.
- **SEEDED**: 6 new DIRECTIVES in Elefante DirectiveStore.
- **SEEDED**: 2 new SPECIFICATION memories in ChromaDB.
- **CLEANED**: Removed 2 garbage directives from DirectiveStore.

### Impact

SDD self-reporting drift eliminated. Full compliance with Law of Compliance and Native SDD pattern. The meta-irony is closed: Elefante enforces SDD on itself using its own enforcement mechanisms.

---

## [2.2.0] - 2026-03-07

### Summary

Native Spec-Driven Development (SDD) Support — Added `SPECIFICATION` and `DIRECTIVE` as first-class entity and memory types with immutable authority scores to act as the ultimate architectural oracle for AI agents.

### The Problem Solved

Agents executing complex tasks need strict architectural rules (Spec-Driven Development), but placing these rules in standard memories meant they would decay over time or be out-competed by noisy ephemeral contexts.

### The Solution

We implemented the "Pure Second Brain" Option 1 for SDD:
1. **New Schema:** Added `SPECIFICATION` and `DIRECTIVE` to both `EntityType` and `MemoryType` enumerations. Added `GOVERNS` and `ENFORCES` to `RelationshipType`.
2. **Immutable Authority:** The `compute_authority_score` function now intercepts these types and permanently locks their authority score at `1.0`. They completely bypass chronological decay, ensuring they consistently surface at the top of context injection when relevant.
3. Agents can now rely on Elefante to hold the complete, non-decaying canonical specification for a project.

### Changes

- **MODIFIED**: `src/models/entity.py` — Added `SPECIFICATION`, `DIRECTIVE`, `GOVERNS`, `ENFORCES`.
- **MODIFIED**: `src/models/memory.py` — Added `SPECIFICATION`, `DIRECTIVE` with `0.0` decay rates.
- **MODIFIED**: `src/utils/curation.py` — Adjusted `compute_authority_score` to intercept specs/directives for `1.0` authority.
- **MODIFIED**: `src/core/orchestrator.py` — Passed `memory_type` into scoring function.

---

## [2.1.4] - 2026-02-26

### Summary

Critical fix: memory deletion/update no longer poisons the co-activation graph with stale IDs.

### The Problem Solved

When a user deleted or updated a memory, its UUID stayed in the MCP server's `_session_retrieval_history` sliding window. Every subsequent `MemorySearch` or auto-context injection (`_inject_context`) passed these stale IDs to `record_coactivation()`, which then:
1. Ran O(n^2) Kuzu MERGE queries referencing nonexistent memories.
2. Created orphan `CO_ACTIVATED` edges or silently failed, wasting graph I/O.
3. Could cause inconsistent graph state if the deleted memory's Entity node was partially cleaned up.

### The Fix

1. **`src/mcp/server.py` — `_handle_delete_memory()`**: After successful deletion, the deleted memory's UUID is purged from `_session_retrieval_history`. No stale ID ever reaches `record_coactivation()`.
2. **`src/core/orchestrator.py` — `record_coactivation()`**: Added existence-validation guard. Before generating O(n^2) pairs, each ID is checked against ChromaDB via `get_memory()`. Only confirmed-live IDs proceed to the MERGE loop. This is defense-in-depth — even if a stale ID leaks through another path, it gets filtered out here.

### Added

- `scripts/version_counsel.py` — interactive smart version advisor. Analyses staged git diff, classifies the change as MAJOR / MINOR / PATCH, presents a recommendation with a short reason and the semantic versioning table, then asks for confirmation before calling `bump_version.py`. Supports manual override (type `x.y.z` at the prompt).

### Fixed

- `_handle_delete_memory()` now purges the deleted UUID from `_session_retrieval_history` immediately after successful deletion.
- `record_coactivation()` validates memory IDs exist in ChromaDB before running O(n^2) graph MERGE queries. Stale/deleted IDs are silently dropped.

### Changed

- `scripts/ci/bump_version.py` — added `[0, 99]` range validation for each version part (x, y, z). Rejects values outside this range with a clear error message.
- `scripts/version_counsel.py` — same `[0, 99]` guard applied to manual override input at the prompt.
- `CONTRIBUTING.md` — versioning section rewritten: recommends `version_counsel.py` as primary workflow, documents manual bump as secondary, includes example output and full rules.
- VERSION BUMP GATE Directive updated to reference `version_counsel.py`.

---

## [2.1.3] - 2026-02-26

### Summary

Windows clean installation support: all platform-specific bugs fixed, full Windows documentation added, pre-action gate promoted to Directive.

### The Problem Solved

1. **Windows install failures**: `fcntl` (Unix-only) was imported unconditionally, crashing on Windows. `KUZU_DIR` constant was `'kuzu'` instead of `'kuzu_db'`, causing database path mismatch. `install.bat` version parse used `tokens=1,2` (MINOR was always empty). Windows Python Launcher (`py -3.11`) was never tried.
2. **Documentation gap**: No Windows-specific installation path, no Windows command variants in verification steps, no Windows pitfall section in `pitfall-index.md`.
3. **Enforcement gap**: Pre-action gate was a memory (score-dependent retrieval) — now a Directive (unconditional, injected into every tool response).

### The Solution

1. **Code fixes** (already shipped in source):
   - `src/utils/elefante_mode.py`: `sys.platform != "win32"` guard around `import fcntl` and `fcntl.flock` calls.
   - `src/utils/config.py`: `KUZU_DIR = DATA_DIR / "kuzu_db"` (was `"kuzu"`).
   - `install.bat`: `tokens=1,2,3` version parse; `py -3.11` detection before `python`; improved error messages.

2. **Documentation additions**:
   - `docs/technical/installation.md`: Windows Golden Path section, Windows Troubleshooting (6 issues), Windows uninstall commands, version bumped.
   - `docs/pitfall-index.md`: New `## Windows Pitfalls` section (6 entries), category table updated, quick reference table updated.
   - `docs/technical/architecture.md`, `docs/technical/README.md` and 10 other docs: version bumped to 2.1.3.

3. **Behavioral enforcement**:
   - Pre-action gate promoted from memory to Directive: `"MANDATORY PRE-ACTION GATE: Before creating any file, running any install command, or making any system change — you MUST first: (1) search Elefante memory for relevant context, AND (2) read docs/pitfall-index.md for the relevant category."`

### Files Changed

- `src/__init__.py`, `setup.py`, `config.yaml`, `src/dashboard/ui/package.json`, `src/dashboard/ui/package-lock.json` — version bump
- `install.bat` — Python version detection fixes
- `docs/technical/installation.md` — Windows Golden Path + Troubleshooting + Windows uninstall
- `docs/pitfall-index.md` — Windows Pitfalls section + quick reference + `fcntl` entry
- 14 documentation files — version bump to 2.1.3

---

## [2.1.2] - 2026-02-25

### Summary

Passive Co-Activation (Autonomous Graph Maintenance), Smoothed Vector Baselines for precise semantic scoring, and comprehensive E2E Verification fixes ensuring Elefante operates seamlessly as a true, self-optimizing second brain without manual user curation.

### The Problem Solved

1. **Stale Graph Architecture**: Elefante relied on explicit agent-driven tools (`elefanteGraphConnect`) to build relationships, which agents frequently forgot to use, leaving the Kuzu graph sparse and ineffective.
2. **Brittle Heuristic Suppression (Issue 8)**: The `sentence-transformers/gte-base` embedding model naturally compresses cosine similarities. Elefante's hardcoded threshold (0.4) was ruthlessly suppressing highly relevant semantic matches (e.g., scoring exact matches at 0.52 and suppressing 0.38 matches entirely).
3. **Response Bloat (Issue 7) & Agent Actionability (Issue 9)**: Search results flooded the IDE with empty `null` metadata fields, wasting tokens. Furthermore, agents often retrieved context but didn't know what to do with it.
4. **Agent Zero Stateless Bypass**: The compliance gate ("search before write") failed under certain stateless multi-agent workflows, allowing raw unregulated memory dumps.

### The Solution

1. **Autonomous Graph Maintenance**:
   - Session Tracking: The MCP server now maintains a `_session_retrieval_history` sliding window.
   - `record_coactivation`: Automatically generates and reinforces `CO_ACTIVATED` relationships in the Kuzu graph between memories retrieved sequentially within the same context window.
   - The Cognitive Retriever now directly ingests this live graph density (the `strength` property) to boost the `coactivation_score` of related memories during future searches.
2. **Smoothed Vector Baseline**: Implemented a proportional scaling formula (`vector_baseline = similarity * 0.85`) in the cognitive router. This creates a dynamic floor that rescues valid semantic matches from hard suppression.
3. **Slim & Actionable Responses**:
   - `SearchResult` dictionaries now aggressively strip all `null`/`None` metadata fields.
   - Raw JSON payloads rendered to the LLM now include a synthesized `summary` and `suggested_action` header to immediately dictate how the context should be parsed.
4. **Strict Protocol Enforcement**: Hardened the Compliance Gate and injected explicit `NO GUESSING / EXACTLY UNKNOWN.` behavioral rules into `MANDATORY_PROTOCOLS_READ_THIS_FIRST` to prevent agent hallucinations when search queries return empty.

### Changes

- **NEW**: `Autonomous Co-Activation` pipeline spanning `src/mcp/server.py`, `src/core/orchestrator.py`, and `src/core/retrieval.py` powered by a direct Kuzu `MERGE` query.
- **NEW**: `tests/test_autonomous_coactivation.py` suite proving real-time graph edge generation influences routing weights.
- **MODIFIED**: `_apply_cognitive_scoring` mathematically smoothed to fix Issue #8 (Muted Similarity Suppression).
- **MODIFIED**: `src/mcp/server.py` dict rendering optimized to strip `None` values (Fixes Issue #7).
- **MODIFIED**: Context injection headers upgraded for actionability (Fixes Issue #9).
- **FIXED**: Multi-agent compliance gate bypass patched; Agent Zero native E2E test scripts (`e2e_agent_zero.js`) added to formally verify end-to-end frontend graphical rendering.

---

## [2.1.1] - 2026-02-19

### Part 3: Schema Simplification & Archive Cleanup

A major cleanup pass removing dead model abstractions and historical archive content that was adding noise without value.

**Dead code removed from `src/`** (−1,397 lines):

- `src/core/metadata_store.py` — `StandardizedMetadata` layer; unused since v4 schema.
- `src/core/consolidation.py` — background consolidation task; never activated.
- `src/core/llm.py` — LLM client stub; Elefante doesn't connect to LLMs.
- `src/core/graph_executor.py` — delegated graph executor; inlined and unused.
- `src/models/cognitive.py` — v5 cognitive topology models; superseded.
- `src/models/metadata.py` — `StandardizedMetadata` model; superseded by `MemoryMetadata`.
- `src/models/memory.py` — removed `IntentType` enum (8 values, zero usage); removed lingering `RelationshipType` duplicate.
- `src/core/retrieval.py` — removed `MemoryConstellation` dataclass; renamed `importance` → `score` in `MemoryCandidate`.
- `scripts/ingest_inception.py`, `scripts/ingest_protocol.py` — one-time ingest scripts.
- `scripts/utils/repair_graph_topology.py` — one-time migration script.

**Archive cleanup** (−62 docs + deprecated registers, −44 scripts, −12 tests):

- `docs/archive/historical/` — 40+ historical implementation logs, dashboards plans, schema archives.
- `docs/archive/deprecated-registers/` — 7 old neural registers.
- `docs/archive/releases/` — 3 old release notes.
- `docs/archive/technical/` — `memory-schema-v4.md` moved here from `docs/technical/`.
- `scripts/archive/historical/` — 44 one-time migration/debug scripts.
- `tests/archive/` — 12 deprecated test files.

**Renamed**: `importance` → `score` everywhere (vscode-extension `formatter.ts`, retrieval internals) — aligns with behavioral scoring terminology.

---

### Part 2: Dashboard Field Mapping Fixes

Two field name mismatches between ChromaDB storage and dashboard presentation caused all memories to display with wrong metadata:

1. **All topics showed "General"**: The dashboard `topic` field was reading `meta.get("topic")` — a key that does not exist in ChromaDB. The actual field is `category`. This bug existed in two independent code paths: the snapshot builder (`scripts/pipeline/update_dashboard_data.py`) and the live refresh path (`src/mcp/server.py` `_refresh_dashboard_snapshot()`).
2. **All usage counts showed "Never"**: The `/api/graph` endpoint served snapshot data that lacked `access_count` and `last_accessed` fields, defaulting to zero/null in the UI.

### The Solution

1. **Snapshot builder**: Changed `meta.get("topic")` to `meta.get("category")` in `scripts/pipeline/update_dashboard_data.py`.
2. **Live refresh path**: Changed `cm.get("topic")` to `mem.metadata.category` in `src/mcp/server.py` `_refresh_dashboard_snapshot()`.
3. **API hydration fallback**: Added server-side hydration in `src/dashboard/server.py` `get_graph()` that fetches live `access_count`, `last_accessed`, and `last_modified` from the vector store when the snapshot lacks them.

### Changes

- **FIX**: `scripts/pipeline/update_dashboard_data.py` — Read `category` instead of nonexistent `topic` from ChromaDB metadata for dashboard topic derivation.
- **FIX**: `src/mcp/server.py` `_refresh_dashboard_snapshot()` — Read `mem.metadata.category` instead of `cm.get("topic")` for live refresh topic assignment.
- **FIX**: `src/dashboard/server.py` `get_graph()` — Added usage hydration fallback that populates `access_count`, `last_accessed`, `last_modified` from live vector store when snapshot properties lack them.
- **REMOVED**: Deprecated `importance`, `layer`, `sublayer` fields from snapshot builder (removed in schema v4).
- **FIX**: Version unification — bumped all 15 files (`setup.py`, `src/__init__.py`, `config.yaml`, `package.json`, `package-lock.json`, `README.md`, `RELEASES.md`, and 8 docs) from stale 2.0.0/2.1.0 to 2.1.1. Dashboard now reports the correct version.
- **CLEANED**: Removed dead `llm`, `memory`, `consolidation`, `auto_tagging` placeholder sections from `config.yaml`.

---

## [2.1.0] - 2026-02-19

### Summary

Directive System + Behavioral Bootstrap — Always-active behavioral constraints separated from memories, `copilot-instructions.md` formally integrated into the installation process, and the three-key Tool Response Contract documented as first-class architecture.

### The Problem Solved

1. **Behavioral Rules Depended on Retrieval**: Critical rules like "never claim success without user approval" were stored as memories with `surfaces_when` triggers. Keyword-based retrieval is fragile — you cannot enumerate every possible phrasing of a rule that should never be forgotten.
2. **`copilot-instructions.md` Was an Afterthought**: The installer never validated or referenced it. Section 6.1 of installation docs listed it as a "Next Step" rather than a core installation component.
3. **Tool Response Contract Was Undocumented**: The three injected keys (`MANDATORY_PROTOCOLS_READ_THIS_FIRST`, `DIRECTIVES`, `RELEVANT_CONTEXT`) existed in the server code but were only mentioned in internal planning docs — not in any agent-facing or user-facing documentation.

### The Solution

1. **Directive System**: A new `DirectiveStore` class (`src/core/directive_store.py`) stores behavioral constraints in `~/.elefante/data/directives.json`. Directives are injected into every MCP tool response unconditionally — no search, no similarity scores, no keyword matching. They cannot be outcompeted by memories.
2. **Three Directive Tools**: `elefante-DirectiveAdd`, `elefante-DirectiveList`, `elefante-DirectiveRemove`.
3. **Installation Bootstrap Validation**: `scripts/setup/install.py` Step 4a now validates `copilot-instructions.md` exists. The installer warns with an explicit error if it is missing, explaining the behavioral consequence.
4. **Tool Response Contract Documented**: Both `copilot-instructions.md` and `docs/technical/installation.md` now formally document all three injected keys as a first-class agent-facing contract.

### Changes

- **NEW**: `src/core/directive_store.py` — `DirectiveStore` + `Directive` classes. JSON-backed persistent storage at `~/.elefante/data/directives.json`. Module-level singleton `get_directive_store()`.
- **MODIFIED**: `src/mcp/server.py` — Added `elefante-DirectiveAdd`, `elefante-DirectiveList`, `elefante-DirectiveRemove` tools. Added `_inject_directives()` and `_handle_directive_*` methods. Updated `_CONTEXT_SKIP_TOOLS`.
- **MODIFIED**: `scripts/setup/install.py` — Added `verify_copilot_instructions()` function and Step 4a to installer flow.
- **MODIFIED**: `.github/copilot-instructions.md` — Added "Tool Response Contract" section documenting all three injected response keys with their sources, scope, and behavioral rules.
- **MODIFIED**: `docs/technical/installation.md` — Replaced "Next Steps / Section 6.1" with "Behavioral Instruction Architecture": Layer 1 (Bootstrap), Tool Response Contract (three keys), Layer 2 (Directives), Layer 3 (Memories), and installation-to-runtime mapping table.
- **MODIFIED**: `docs/technical/usage.md` — Added `elefante-DirectiveAdd`, `elefante-DirectiveList`, `elefante-DirectiveRemove` documentation under new "Directives" section.
- **IMPACT**:
  - **Tool count**: 17 → 20.
  - `copilot-instructions.md` is now validated by the installer (Step 4a) — missing file produces a clear warning.
  - Behavioral rules that must never be forgotten are separated from the memory system entirely.
  - Three-key Tool Response Contract is documented in both the bootstrap file and the installation guide.

---

## [2.0.0] - 2026-02-18

### Summary

Unified V2 Release — Cohesive product vision across MCP, Intelligence Engine, and Dashboard. Memory curation (19 → 13 high-signal memories), dashboard overhaul with functional Explore tab, and version consolidation eliminating the version multiverse.

### The Problem Solved

1. **Version Multiverse**: Components declared different versions (1.10.0, 1.11.0, 2.1.0, 2.3.0) creating confusion about what "Elefante version" meant.
2. **Memory Noise**: 6 of 19 memories were duplicates, generic checklists, or unimplemented design concepts that diluted retrieval quality.
3. **Broken Explore Tab**: The Nivo Network graph was non-functional — wrong data format, missing dependencies, and no useful visualization.
4. **Dashboard as Screensaver**: The dashboard showed data but didn't help users understand their knowledge system's health or find insights.

### The Solution

1. **Single Version (2.0.0)**: Every file — Python package, config, server, docs, dashboard components — now declares v2.0.0. Historical references in code comments are preserved but all "current version" indicators are unified.
2. **Memory Curation**: Deleted 6 noise memories (duplicates of Operating Laws, generic checklists, unimplemented v5 concepts, overly-niche debugging notes). 13 high-signal memories remain.
3. **Explore Tab Rewrite**:
   - **Topics**: Card grid showing memory distribution by topic (replaced broken Nivo Treemap).
   - **Insights**: Score distribution, type breakdown, topic breakdown, and top memories panel (replaced non-functional calendar heatmap).
   - **Graph**: Pure SVG hub-spoke knowledge graph grouped by topic with hover highlighting (replaced broken Nivo Network).
4. **Dashboard as Product**: Overview tab with health score ring gauge, diagnostic panels, agent impact metrics. Memories tab with semantic search and TanStack Table. Explore tab with three functional sub-views.

### Changes

- **MODIFIED**: `src/__init__.py`, `setup.py`, `config.yaml`, `src/mcp/server.py` — Version 2.0.0.
- **MODIFIED**: `src/dashboard/ui/src/components/ExploreTab.tsx` — 3 sub-views: Topics, Insights, Graph.
- **MODIFIED**: `src/dashboard/ui/src/components/CalendarHeatmap.tsx` — Rewritten as Memory Insights panel (score distribution, type/topic breakdown, top memories).
- **MODIFIED**: `src/dashboard/ui/src/components/KnowledgeGraph.tsx` — Rewritten as pure SVG hub-spoke graph (no Nivo dependency). ResizeObserver for responsive sizing.
- **MODIFIED**: `src/dashboard/ui/src/components/TopicTreemap.tsx` — Rewritten as card grid layout.
- **MODIFIED**: `src/dashboard/ui/src/components/OverviewTab.tsx` — Health gauge + diagnosis + agent impact + stat pills + metric cards.
- **MODIFIED**: `src/dashboard/ui/src/components/HealthGauge.tsx` — SVG ring gauge with animated score.
- **MODIFIED**: All dashboard component version comments unified to v2.0.0.
- **MODIFIED**: All documentation files — version references updated to 2.0.0.
- **DELETED**: 6 noise memories from ChromaDB (IDs: 9ae31791, a3db42e5, cc9ca4f3, 247d89cc, 58bdc18c, 1290ec67).
- **IMPACT**:
  - **Breaking Change**: Version jump from 1.11.0 to 2.0.0 reflects product maturity milestone.
  - **Memory Quality**: Retrieval precision improved by removing noise (31% fewer memories, 100% signal).
  - **Dashboard**: All 3 tabs and all Explore sub-views are functional with zero external visualization dependencies (no D3, no Nivo).

---

## [1.11.0] - 2026-02-17

### Summary

Dashboard Overhaul — Complete rewrite of the dashboard from a physics-based "screensaver" to a functional "knowledge workbench" with tabbed navigation, sortable memory table, and static visualizations.

### The Problem Solved

1. **Physics Instability**: The D3 force-directed graph was unstable, causing nodes to "fly away," flicker, or appear as visual duplicates ("two dots" artifact).
2. **Poor Usability**: The dashboard was a visual novelty with no practical utility for memory management.
3. **No Search**: Users could not find specific memories without visually scanning the graph.

### The Solution

1. **Removed Physics Engine**: Eliminated the unstable D3 force simulation entirely. All visualizations are now static.
2. **3-Tab Architecture**:
   - **Overview**: Health score (freshness, coverage, connectivity) + topic treemap.
   - **Memories**: Sortable/filterable table with semantic search integration.
   - **Explore**: Static knowledge graph using Nivo Network.
3. **Zustand State Management**: Centralized state with derived data selectors.
4. **TanStack Table**: Full-featured table with sorting, filtering, and expandable rows.

### Changes

- **NEW**: `src/dashboard/ui/src/types.ts` - TypeScript interfaces for all data structures.
- **NEW**: `src/dashboard/ui/src/store.ts` - Zustand store with 15+ state slices.
- **NEW**: `src/dashboard/ui/src/hooks/useVisualizationData.ts` - Data transformation hooks.
- **NEW**: `src/dashboard/ui/src/hooks/useSearch.ts` - Semantic search hook with abort controller.
- **NEW**: `src/dashboard/ui/src/components/TabNav.tsx` - Tab navigation component.
- **NEW**: `src/dashboard/ui/src/components/HeaderBar.tsx` - Header with stats display.
- **NEW**: `src/dashboard/ui/src/components/OverviewTab.tsx` - Health score + treemap.
- **NEW**: `src/dashboard/ui/src/components/MemoriesTab.tsx` - Memory list with search.
- **NEW**: `src/dashboard/ui/src/components/MemoryTable.tsx` - TanStack Table implementation.
- **NEW**: `src/dashboard/ui/src/components/ExploreTab.tsx` - Knowledge graph tab.
- **NEW**: `src/dashboard/ui/src/components/TopicTreemap.tsx` - Nivo Treemap visualization.
- **NEW**: `src/dashboard/ui/src/components/KnowledgeGraph.tsx` - Nivo Network visualization.
- **MODIFIED**: `src/dashboard/ui/src/App.tsx` - Complete rewrite with tabbed layout.
- **MODIFIED**: `src/dashboard/ui/package.json` - Added dependencies (zustand, @tanstack/react-table, @nivo/\*).
- **MODIFIED**: `src/dashboard/ui/vite.config.ts` - Added @ path alias.
- **IMPACT**:
  - **Breaking Change**: Old GraphCanvas.tsx is no longer used (kept for reference).
  - **Performance**: Static visualizations eliminate CPU-intensive physics calculations.
  - **Usability**: Users can now search, sort, and filter memories efficiently.

---

## [1.10.0] - 2026-02-09

### Summary

Behavioral Relevance & Simplified Naming — Importance scores are now system-computed based on usage, not user assignment. All tools renamed to `elefante-PascalCase` for consistency.

### The Problem Solved

1. **Importance Rot**: Users rated everything as "important" (8-10), and old decisions stayed "critical" forever even as they became obsolete.
2. **Cognitive Load**: "Layer/Sublayer" taxonomy was jargon-heavy and confusing.
3. **Naming Inconsistency**: Tool names like `elefanteMemoryAdd` were hard to read and inconsistent with standard MCP practices.

### The Solution

1. **Behavioral Relevance Model**: Removed all user-assigned importance. The system now computes a score (0-100) automatically based on:
   - **Recency**: Exponential decay based on memory type (Rules decay slowly, conversations quickly).
   - **Freshness**: Recently accessed memories get a boost.
   - **Reinforcement**: Frequently accessed memories grow stronger.
2. **Simplified Classification**: Removed `Layer` (self/world/intent) and `Sublayer`. Now using only `MemoryType` (fact, decision, etc.) and `Domain`.
3. **New Naming Convention**: All 17 tools now follow the `elefante-ToolName` format (e.g., `elefante-MemorySearch`, `elefante-GraphConnect`).

### Changes

- **MODIFIED**: `src/models/memory.py`
  - Removed `importance`, `layer`, `sublayer` fields from `MemoryMetadata`.
  - Added `score` (system-computed) and `TYPE_DECAY_RATES`.
  - Implemented `calculate_relevance_score()` using the new formula.
- **MODIFIED**: `src/mcp/server.py`
  - Renamed ALL 17 tools to `elefante-X` convention.
  - Updated dispatch logic and handlers for the new naming.
  - Removed `importance`/`layer`/`sublayer` from `elefante-MemoryAdd` schema.
- **MODIFIED**: `README.md`
  - Complete rewrite to explain Behavioral Relevance and document new tool names.
- **IMPACT**:
  - **Breaking Change**: Old tool names (`elefanteMemoryAdd`) will no longer work. Client configuration must be updated.
  - **Data Compatibility**: v1.10.0 starts fresh (or requires migration of old importance values to score).

---

## [1.9.1] - 2026-02-09

### Summary

Tool Consolidation — 24 tools reduced to 17 with zero feature loss. Every tool earns its seat.

### The Problem Solved

24 MCP tools caused decision fatigue for LLMs (~6,000 tokens of schema per message), maintenance burden (each tool = registration + dispatch + handler + docs), and redundancy (3 graph tools did what 1 already did).

### The Solution

**KILLED (3 tools → 0):**

- `elefanteGraphEntityCreate` — redundant, `GraphConnect` already creates entities
- `elefanteGraphRelationshipCreate` — redundant, `GraphConnect` already creates relationships
- `elefanteMemoryMigrateToV3` — one-time admin job, moved to scripts/

**MERGED (5 tools → 2):**

- `elefanteSystemEnable` + `elefanteSystemDisable` → **`elefanteSystem`** with `action: "enable" | "disable"`
- `elefanteMemoryListAll` → absorbed into **`elefanteMemorySearch`** with `list_all: true`
- `elefanteTaskDecompose` → absorbed into **`elefanteTaskCreate`** with optional `subtasks: [...]`
- `elefanteETLStatus` → absorbed into **`elefanteETLProcess`** with `include_stats: true`

### Changes

- **MODIFIED**: `src/mcp/server.py`
  - Removed 3 tool registrations, removed 3 dispatch branches
  - Merged 5 tools into 2 via new parameters
  - Updated `_CONTEXT_SKIP_TOOLS`, `GATED_TOOLS`, pitfall injection
  - `_handle_task_create` now handles inline subtask creation
  - `_handle_etl_process` now returns stats when requested
  - `_handle_search_memories` delegates to `_handle_list_all_memories` when `list_all=true`
  - Version bumped to v1.9.1
- **MODIFIED**: `README.md` — tool table consolidated, version bumped
- **UNCHANGED**: All handler implementations preserved (no backend changes)

### Impact

- **Context window**: ~2,000 fewer tokens per message (7 fewer tool schemas)
- **LLM decision quality**: Fewer choices = better picks
- **Backward compatibility**: Old tool names removed — MCP clients must update

---

## [1.9.0] - 2026-02-09

### Summary

Custodial Memory Tools — Elefante gains the ability to amend and forget memories, closing the gap between stored schema fields and runtime operations.

### The Problem Solved

Elefante stored `deprecated`, `archived`, `supersedes_id`, and `superseded_by_id` fields in its schema, but had **zero runtime tools** to use them. The vector store backend (`update_memory`, `delete_memory`) existed but was not exposed as MCP tools. Agents could only create memories — never correct, deprecate, or delete them. This violated the "Amendment" and "Forgetting" custodial duties described in Weaviate's "Limit in the Loop" framework.

### The Solution

1. **`elefanteMemoryUpdate`** — Amend any memory's content (triggers re-embedding), importance, tags, deprecated/archived status, or supersession chain. When `supersedes_id` is set, the old memory automatically gets `superseded_by_id` back-linked.
2. **`elefanteMemoryDelete`** — Permanently remove a memory with a reason (audit trail). Requires prior `elefanteMemorySearch` (compliance gated).
3. **Search-time filtering** — `elefanteMemorySearch` now excludes `deprecated=true` and `archived=true` memories from results, reporting the excluded count separately.

### Changes

- **MODIFIED**: `src/mcp/server.py`
  - Added `elefanteMemoryUpdate` + `elefanteMemoryDelete` tool registrations with full inputSchema
  - Added both to `GATED_TOOLS` compliance gate set (24 → 26 total tool registrations)
  - Added dispatch routing for both tools
  - Added `_handle_update_memory()` and `_handle_delete_memory()` async handlers
  - Modified search handler to filter deprecated/archived memories with `excluded_deprecated` count in response
- **UNCHANGED**: `src/core/vector_store.py` — backend methods already existed, now surfaced via MCP

### Project Cleanup (same release)

- Removed 5 identical duplicate scripts from `scripts/archive/historical/`
- Archived 2 old memory exports, 3 stale data files, and `install.log` to `data/archive/`
- Moved misplaced `test_end_to_end.py` from `scripts/` to `tests/`
- Archived completed `compliance_gate_plan.md` from `planning/` to `docs/archive/historical/`
- Removed empty `planning/` directory

---

## [1.6.3] - 2025-12-30

### Summary

Neural Web Visualization - Dashboard graph transformed from rigid "Solar System" to organic "Neural Web" layout.

### The Problem Solved

v1.6.2's ring-based layout forced memories into concentric orbits. The exponential node sizing (`r = 8 + importance^2 * 0.4`) made high-importance nodes overwhelmingly large. The result was visually cluttered and didn't represent how a "second brain" thinks.

### The Solution

1. **Linear Sizing**: Changed formula to `r = 10 + importance * 1.5` (max 25px vs. 48px)
2. **Neural Physics**: Removed ring gravity and core locking - nodes float organically based on connections
3. **Status Indicators**: Added visual borders for processing status (emerald=processed, amber=pending)
4. **Recency Pulse**: White pulsing ring for very recent memories (heat > 0.9)
5. **Cleaned Render**: Disabled ring guide backgrounds for cleaner brain visualization

### Changes

- **MODIFIED**: `src/dashboard/ui/src/components/GraphCanvas.tsx`
  - Node radius: Linear scaling replaces power law
  - Physics: Core nodes no longer locked (`fx`/`fy` removed)
  - Ring gravity: Disabled (commented out)
  - Ring guides: Disabled (commented out)
  - Added: Recency pulse ring (white, animated)
  - Added: Processing status border (green/amber dashed)

### Visual Impact

Before: Rigid orbits, giant nodes, cluttered labels
After: Organic clusters, balanced sizes, semantic grouping

---

## [1.6.2] - 2025-12-29

### Summary

Cognitive Visual Enablement - Dashboard now displays cognitive fields (concepts, surfaces_when, authority_score) in the memory inspector sidebar.

### The Problem Solved

v1.6.1 ensured cognitive fields are stored and reconstructed correctly, but users couldn't SEE them in the dashboard. The data existed in ChromaDB and the snapshot, but the UI didn't render it.

### The Solution

Updated `src/dashboard/ui/src/components/GraphCanvas.tsx` to display:

- **Concepts**: Clickable cyan chips showing extracted concepts (search on click)
- **Surfaces When**: Purple bullet list showing when memory surfaces
- **Authority Score**: Progress bar (0-1 scale) with color gradient

### Changes

- **MODIFIED**: `GraphCanvas.tsx` - Added Cognitive Fields section after Tags
- **NEW**: JSON array parser for ChromaDB-stored lists
- **NEW**: Visual design matching existing inspector aesthetic

### Visual Output

When clicking a memory node in the dashboard, the sidebar now shows:

```
Cognitive Fields                              v1.6.2
  Concepts: [elefante] [mcp] [law] [protocol]
  Surfaces When:
    • "when user asks about development rules"
    • "on etiquette or protocol questions"
  Authority Score: [=====-----] 0.850
```

---

## [1.6.1] - 2025-12-29

### Summary

Cognitive Field Standardization - Ensured `concepts`, `surfaces_when`, and `authority_score` persist correctly and are available for V4 Cognitive Retrieval scoring.

### The Problem Solved

V4 Cognitive Retrieval uses concept overlap (0.20 weight) for scoring, but:

- Concepts were sometimes stored in inconsistent formats (JSON, repr(), comma-separated)
- Some memories had missing or malformed cognitive fields
- Dashboard snapshot didn't include these fields

### The Solution

1. **Standardized Storage**: All cognitive fields stored as JSON strings in ChromaDB metadata
2. **Migration Script**: `scripts/migrate_cognitive_fields_v161.py` to fix existing memories
3. **Snapshot Update**: `scripts/pipeline/update_dashboard_data.py` now includes cognitive fields

### Changes

- **NEW**: `scripts/migrate_cognitive_fields_v161.py` - Migrates all memories to v1.6.1 format
- **MODIFIED**: `scripts/pipeline/update_dashboard_data.py` - Added concepts, surfaces_when, authority_score to node properties
- **MIGRATED**: 34 memories (9 updated, 25 already compliant)

---

## [1.6.0] - 2025-12-28

### Summary

Compliance Gate - Enforced search-before-write to ensure agents retrieve context before storing memories.

### The Problem Solved

Agents using Elefante MCP tools often skip memory retrieval entirely:

- Memories are stored without checking for duplicates
- Context is ignored because search is never called
- No mechanical enforcement existed - only "instructions" which agents drift from

### The Solution

**Server-Side Compliance Gate** in `src/mcp/server.py`:

- Session state tracks whether `elefanteMemorySearch` has been called
- Write operations (`elefanteMemoryAdd`, `elefanteGraphEntityCreate`, `elefanteGraphRelationshipCreate`, `elefanteGraphConnect`) are **BLOCKED** if no prior search
- Search handler sets `search_performed=True` and returns a compliance stamp
- Gate resets on session end

**Layered Defense** via `.github/copilot-instructions.md`:

- Injected into every GitHub Copilot request in this repository
- Documents the mandatory search-first protocol
- Defines the compliance stamp format

### Compliance Stamp Format

```
[ELEFANTE] Searched: Found {N} relevant memories
[ELEFANTE] Searched: No relevant memories found
```

### Changes

- **NEW**: `_compliance_state` dict in ElefanteMCPServer (`search_performed`, `search_count`, `search_timestamp`, `last_query`)
- **NEW**: `_check_compliance_gate()` method - returns error if search not performed
- **NEW**: `_reset_compliance_gate()` method - resets session state
- **MODIFIED**: `_handle_search_memories` - sets compliance flag and adds stamp to response
- **MODIFIED**: `_handle_add_memory` - gate check before write
- **MODIFIED**: `_handle_create_entity` - gate check before write
- **MODIFIED**: `_handle_create_relationship` - gate check before write
- **MODIFIED**: `_handle_set_elefante_connection` - gate check before write
- **NEW**: `.github/copilot-instructions.md` - Copilot-injected protocol instructions

### Gated Tools

| Tool                              | Gate Enforced              |
| --------------------------------- | -------------------------- |
| `elefanteMemoryAdd`               | Yes                        |
| `elefanteGraphEntityCreate`       | Yes                        |
| `elefanteGraphRelationshipCreate` | Yes                        |
| `elefanteGraphConnect`            | Yes                        |
| `elefanteMemorySearch`            | No (this unlocks the gate) |
| `elefanteContextGet`              | No (read-only)             |
| `elefanteGraphQuery`              | No (read-only)             |

### Error Response (Gate Blocked)

```json
{
  "success": false,
  "error": " COMPLIANCE GATE: Search required before write operations.",
  "gate_status": "BLOCKED",
  "action_required": "Call elefanteMemorySearch first to check for existing/related memories.",
  "reason": "This prevents duplicate memories and ensures you have full context before adding new knowledge."
}
```

---

## [1.5.0] - 2025-12-28

### Summary

V5 Cognitive Features - Retrieval Explanation, Memory Health, Conflict Detection, Proactive Surfacing.

### The Problem Solved

V4 returns cognitive scores but doesn't explain WHY. Users can't audit the system:

- Why did this memory rank higher than another?
- Which memories are stale or orphaned?
- Are any memories contradicting each other?
- What should surface proactively based on context?

### The Solution

4 new features via 2 consolidated components:

**CognitiveRetriever Extensions** (`src/core/retrieval.py`):

- `RetrievalExplanation` - Full breakdown of 6 signals with reasons
- `ProactiveSurfacer` - Suggests memories based on temporal/domain/concept triggers

**MemoryHealthAnalyzer** (`src/utils/curation.py`):

- `compute_health()` - 4 states: healthy, stale, at_risk, orphan
- `detect_potential_conflict()` - Flags same-domain memories with 60%+ concept overlap

### Property-Based Testing

8 properties verified with Hypothesis (700+ test iterations):

- P1: Explanation completeness (6 signals always present)
- P2: Explanation accuracy (matched concepts correct)
- P3: Health exhaustiveness (exactly 4 states)
- P4: Health determinism (same inputs → same output)
- P5: Conflict symmetry (conflict(a,b) ⇔ conflict(b,a))
- P6: Threshold monotonicity (higher threshold → fewer conflicts)
- P7: Trigger types (exactly 3: temporal, domain, recurring_concept)
- P8: Confidence bounds (always 0.0-1.0)

### Changes

- **NEW**: `RetrievalExplanation` dataclass in retrieval.py
- **NEW**: `ProactiveSuggestion` + `ProactiveSurfacer` in retrieval.py
- **NEW**: `HealthStatus`, `HealthReport`, `ConflictReport`, `MemoryHealthAnalyzer` in curation.py
- **MODIFIED**: `score_candidate()` now returns `(candidate, explanation)` tuple
- **MODIFIED**: Orchestrator attaches explanations to SearchResult
- **NEW**: tests/test_v5_explanation.py (7 tests)
- **NEW**: tests/test_v5_health.py (14 tests)
- **NEW**: tests/test_v5_proactive.py (14 tests)

---

## [1.4.0] - 2025-12-27

### Summary

V4 Cognitive Retrieval Engine - 6-signal composite scoring replaces raw vector similarity.

### The Problem Solved

Raw vector similarity alone is naive. A memory can be semantically similar but:

- Temporally stale (hasn't been accessed in months)
- Low authority (user never reinforced it)
- Disconnected (no graph relationships)

### The Solution

`CognitiveRetriever` in `src/core/retrieval.py` applies 6 weighted signals:

| Signal            | Weight | Source                     |
| ----------------- | ------ | -------------------------- |
| Vector Similarity | 0.35   | ChromaDB cosine distance   |
| Concept Match     | 0.15   | Keyword/concept overlap    |
| Domain Alignment  | 0.10   | Domain field match         |
| Coactivation      | 0.15   | Graph relationship density |
| Authority         | 0.15   | Reinforcement history      |
| Temporal Recency  | 0.10   | Decay-adjusted freshness   |

### Verified Results

- Composite scores differ from vector scores by -0.32 to -0.45
- High-authority, recently-accessed memories rank higher
- Graph-connected memories get coactivation boost

### Changes

- **NEW**: `src/core/retrieval.py` - CognitiveRetriever class
- **MODIFIED**: `src/core/orchestrator.py` - Wired `_apply_cognitive_scoring()`
- **CLEANUP**: Archived 40+ one-off scripts to `scripts/archive/historical/`
- **CLEANUP**: Removed 26 old data exports from `data/`

---

## [1.3.0] - 2025-12-27

### Summary

Embedding model upgrade to `thenlper/gte-base` (768-dim) for improved semantic search quality.

### The Problem Solved

The previous embedding model (`all-MiniLM-L6-v2`, 384-dim) had lower semantic precision:

- Fuzzy queries often missed relevant memories
- Similar concepts had weak similarity scores
- Edge cases (version numbers, acronyms) performed poorly

### The Solution

Rigorous benchmarking of 10 embedding models (1485 queries) identified `thenlper/gte-base` as the optimal choice:

| Model                 | Dimensions | MRR       | Hit@5 | Latency |
| --------------------- | ---------- | --------- | ----- | ------- |
| **thenlper/gte-base** | 768        | **0.337** | 49.8% | ~15ms   |
| all-MiniLM-L6-v2      | 384        | 0.310     | 45.2% | ~8ms    |
| BAAI/bge-base-en-v1.5 | 768        | 0.328     | 48.1% | ~14ms   |

Live testing (35 queries, 24 memories) confirmed:

- **Global Avg Similarity: 0.803** (excellent)
- **Hit Rate: 100%** (all queries returned relevant results)
- **Fuzzy query handling**: "remember that thing about the database lock" → 0.845 similarity

### Changes

#### Configuration Updates

- **`config.yaml`**: `embedding_model: "thenlper/gte-base"`, `embedding_dimension: 768`
- **`src/utils/config.py`**: Updated `VectorStoreConfig` and `EmbeddingsConfig` defaults
- **`.env.example`**: Updated example value
- **`docs/technical/architecture.md`**: Model reference updated

#### Migration Script

- **`scripts/migrate_embeddings_gte_base.py`**: Re-embeds all memories with new model
  - Creates timestamped backup before migration
  - Batch processing with progress indication
  - Verification of count match

#### Documentation Fixes (Ghost Links)

During workspace audit, discovered v2 schema files were archived Dec 11 but documentation still linked to them:

- **`docs/README.md`**: v2 schema → v3/v4/v5 references
- **`docs/technical/README.md`**: Removed dead v2 links
- **`docs/debug/memory-neural-register.md`**: v2 → v3
- **`docs/technical/temporal-memory-decay.md`**: v2 → v3

#### Safeguards Added

- **`docs/pitfall-index.md`**: Added Documentation category with "archive without index update" pitfall
- **`docs/technical/developer-etiquette.md`**: Added LAW 6.5 (mandatory grep-before-archive rule)

#### Test Tooling

- **`scripts/test_embedding_battery.py`**: 35-query test battery across 8 categories
  - Identity, Preferences, Project, Technical, Decisions, Workflow, Fuzzy, Edge

### Migration

**BREAKING**: Existing ChromaDB databases have 384-dim embeddings incompatible with new 768-dim model.

To migrate:

```bash
PYTHONPATH=. .venv/bin/python scripts/migrate_embeddings_gte_base.py
```

The script:

1. Creates backup: `memories_backup_YYYYMMDD_HHMMSS`
2. Re-embeds all memories with `gte-base`
3. Verifies count match

To delete backup after verification:

```bash
python -c "import chromadb; c=chromadb.PersistentClient('~/.elefante/data/chroma'); c.delete_collection('memories_backup_...')"
```

---

## [1.2.0] - 2025-12-27

### Summary

Minor fixes and preparation work for schema/migration operations, plus embedding model benchmarking.

This release focused on reducing migration risk by validating candidate embedding models before shipping an embedding change.

### What Changed

- **Preparation for schema and migration flows** (stability work before larger changes)
- **Embedding model benchmarking** across multiple candidates using repeatable test queries
- **Decision milestone**: `thenlper/gte-base` (768-dim) selected as the best option to ship next

### Notes

- The embedding model upgrade itself is documented in **v1.3.0**.

---

## [Unreleased]

_No unreleased changes._

---

## [1.1.0] - 2025-12-26

### Summary

Transaction-scoped locking for true multi-IDE safety. Fixes the fundamental lock deadlock problem where stale locks from crashed/closed IDEs would block other instances indefinitely.

### The Problem Solved

v1.0.1 used **session-based locking**:

- `elefanteSystemEnable` acquired locks → held indefinitely
- `elefanteSystemDisable` released locks only on explicit call
- Crashed processes left stale locks forever (e.g., PID 4563 from Dec 14 blocking all access on Dec 26)
- Multiple IDEs could never interleave operations

### The Solution

v1.1.0 uses **transaction-scoped locking**:

- Each write operation acquires lock → does work → releases lock (milliseconds)
- Read operations are lock-free
- Stale locks auto-expire after 30 seconds
- Multiple IDEs can interleave operations safely

### Changes

#### Transaction-Scoped Locking (`src/utils/elefante_mode.py`)

- **NEW**: `TransactionLock` class - short-lived, auto-releasing locks
- **NEW**: `write_lock()` context manager for write operations
- **NEW**: `read_lock()` context manager (no-op - reads are lock-free)
- **NEW**: Stale lock detection (dead PID or timeout > 30s)
- **CHANGED**: `is_enabled` always returns `True` (no more enable/disable ceremony)
- **CHANGED**: `enable()`/`disable()` are now no-ops for backward compatibility
- **REMOVED**: Session-based lock files (`chroma.lock`, `kuzu.lock`)
- **ADDED**: Single `write.lock` file with PID/timestamp tracking

#### MCP Server Updates (`src/mcp/server.py`)

- **CHANGED**: Write operations wrapped in `write_lock()`:
  - `_handle_add_memory`
  - `_handle_create_entity`
  - `_handle_create_relationship`
  - `_handle_consolidate_memories`
  - `_handle_set_elefante_connection`
  - `_handle_etl_classify`
  - `_handle_migrate_memories_v3`
- **REMOVED**: Blocking mode check that returned "disabled" response
- **ADDED**: Graceful retry response when lock unavailable

### Migration

No migration needed. v1.1.0 is backward compatible:

- `elefanteSystemEnable` still works (now a no-op that returns success)
- `elefanteSystemDisable` still works (clears resources)
- All existing tool calls work unchanged

### Versioning Logic

Elefante follows [Semantic Versioning](https://semver.org/):

- **MAJOR** (x.0.0): Breaking changes requiring user action
- **MINOR** (1.x.0): New features, backward compatible
- **PATCH** (1.0.x): Bug fixes, documentation

This release is **1.1.0** (minor) because:

- New feature (transaction-scoped locking)
- Backward compatible (existing tools work unchanged)
- No user migration required

---

## [1.0.1] - 2025-12-11

### Summary

Critical update addressing protocol enforcement and multi-IDE safety.

### Changes

#### Auto-Inject Pitfalls (Protocol Enforcement)

- MCP Server now injects mandatory protocols (`MANDATORY_PROTOCOLS_READ_THIS_FIRST`) directly into every tool response
- Context-Aware Warnings for `addMemory` (integrity), `searchMemories` (bias), and graph tools (consistency)
- Updated `ops-ai-behavior-compendium.md` with Issue #6 (Passive Protocol Enforcement Failure)

#### ELEFANTE_MODE (Multi-IDE Safety)

- **Problem**: Multiple IDEs accessing same databases caused crashes/lock conflicts
- **Solution**: Server starts OFF by default, user must explicitly enable

##### New MCP Tools

- `elefanteSystemEnable` - Acquires exclusive locks, enables memory operations
- `elefanteSystemDisable` - Releases locks, cleans up, returns to OFF state
- `elefanteSystemStatusGet` - Shows current mode, lock status, holder info (and stats when enabled)

##### New Files

- `src/utils/elefante_mode.py` - Lock management singleton
- `config.yaml` -> `elefante_mode:` section added

##### Behavior

- When **OFF**: Memory tools return graceful "disabled" response with instructions
- When **ON**: Full functionality with exclusive database access
- Lock files stored in `~/.elefante/locks/` with PID/timestamp tracking
- Safe tools (`elefanteSystemEnable`, `elefanteSystemDisable`, `elefanteSystemStatusGet`, `elefanteDashboardOpen`) always available

##### Usage

```
User: "Enable Elefante"
Agent calls: elefanteSystemEnable -> Acquires locks -> Memory tools now work

User: "Disable Elefante" (before switching IDEs)
Agent calls: elefanteSystemDisable -> Releases locks -> Safe for other IDE
```

---

## [1.0.0] - 2025-12-05

### Summary

First stable production release with comprehensive documentation cleanup.

### Core Features

- **Triple-Layer Memory Architecture**
  - ChromaDB for semantic/vector search
  - Kuzu for knowledge graph relationships
  - Session context for conversation continuity

- **MCP Server with 15 Tools**
  - `addMemory` - Store with intelligent ingestion (NEW/REDUNDANT/RELATED/CONTRADICTORY)
  - `searchMemories` - Hybrid search (semantic + structured + context)
  - `queryGraph` - Execute Cypher queries on knowledge graph
  - `getContext` - Retrieve comprehensive session context
  - `createEntity` - Create nodes in knowledge graph
  - `createRelationship` - Link entities with relationships
  - `getEpisodes` - Browse past sessions with summaries
  - `getSystemStatus` - Mode + lock info + (when enabled) system stats
  - `consolidateMemories` - Merge duplicates & resolve contradictions
  - `listAllMemories` - Export/inspect all memories
  - `getElefanteDashboard` - Launch visual Knowledge Garden UI (optionally refresh)
  - `setElefanteConnection` - Upsert entities + create relationships in one call
  - `migrateMemoriesV3` - Admin schema migration to V3

- **Cognitive Memory Model**
  - Agent-managed enrichment of emotions, intent, entities, relationships (no internal LLM calls)
  - Strategic insight generation
  - ADD/UPDATE/IGNORE action logic

- **Temporal Memory Decay**
  - Memories decay over time
  - Reinforced on access
  - Configurable decay rate

- **Visual Dashboard**
  - React/Vite frontend at http://127.0.0.1:8000
  - Force-directed graph visualization
  - Node inspector with full details

- **Automated Installation**
  - Pre-flight checks for common issues
  - Kuzu 0.11+ compatibility handling
  - IDE auto-configuration (VS Code, Cursor)

### Documentation

- Neural Register architecture (5 master registers)
- Domain compendiums for issue tracking
- Technical reference documentation
- Planning roadmaps

### Known Limitations

- Memory Schema V2 taxonomy (domain/category) requires manual input - auto-classification planned for v1.1.0
- Dashboard UX needs improvement - semantic zoom planned
- Smart UPDATE (merge) not yet implemented

---

## Pre-1.0 Development History

Development prior to v1.0.0 used inflated version numbers during rapid iteration.
These have been consolidated into this baseline release.

| Date       | Internal Label | What Happened                                    |
| ---------- | -------------- | ------------------------------------------------ |
| 2025-11-27 | "v1.1.0"       | Initial repository setup                         |
| 2025-12-02 | "v1.2.0"       | User profile integration                         |
| 2025-12-04 | "v1.2.0"       | Kuzu reserved word fix (`properties` -> `props`) |
| 2025-12-05 | "v1.3.0"       | Documentation cleanup                            |
| 2025-12-06 | **v1.0.0**     | Official baseline release                        |

---

## Migration Notes

### From Pre-1.0 Development

If upgrading from internal development versions:

1. Database schema changed (`properties` -> `props`)
2. Run `python scripts/setup/init_databases.py` to reinitialize
3. Documentation restructured into `technical/`, `debug/`, `planning/`, `archive/`

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
