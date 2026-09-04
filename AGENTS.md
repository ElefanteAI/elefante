# Elefante — Agent Entry Point

> **Read this first if you are an AI agent (Claude Code, Cursor, GitHub Copilot, Codex, Cline, Roo, Kilo, Windsurf, Zed, Aider, Gemini, IBM Bob, Kiro, Antigravity, Continue, or any MCP-compatible client) operating on this repository.**
>
> One canonical entry. The full constitution and routing live one click away.

---

## What is Elefante?

A local-first persistent memory engine for AI agents, exposed via the Model Context Protocol (MCP). Stores, scores, and retrieves facts, preferences, decisions, and code patterns across sessions. Embedded SQLite vectors and Kuzu relationships form the current storage architecture. **v2.15.2** is the latest published release.

Detail: [`README.md`](README.md) for product overview, [`docs/reference/architecture.md`](docs/reference/architecture.md) for system design.

---

## Two audiences, two constitutions

| You are... | Read | Then |
|------------|------|------|
| **An end-user agent** helping someone install/use Elefante through MCP | [`.github/copilot-instructions.md`](.github/copilot-instructions.md) (Four Laws, cardinal sins, tool table) | [`docs/`](docs/) — [`reference/tools.md`](docs/reference/tools.md) for MCP tools, [`how-to/install.md`](docs/how-to/install.md) for installation, [`how-to/configure-ide.md`](docs/how-to/configure-ide.md) for host wiring |
| **A developer agent** building or debugging Elefante itself | [`agents/orchestrator.md`](agents/orchestrator.md) (Loop, Five Gates, Documentation Skill, Modes, Closure Sequence) | [`workspace/PLANNING.md`](workspace/PLANNING.md) for current state + roadmap, [`workspace/ISSUES.md`](workspace/ISSUES.md) for BUG/GAP tracker, [`agents/`](agents/) for specialist protocols |

---

## The Elefante Workflow Lifecycle (state-changing developer work)

Use the full lifecycle for state-changing developer work. Read-only analysis
stops after evidence and reporting; it does not create memory, journal, or git
mutations by ritual.

| # | Step | Action |
|---|------|--------|
| 0 | **ENGAGE** | For non-trivial repository work, search Elefante for prior decisions; use canonical workspace sources if unavailable |
| 1 | **CLASSIFY** | Read `workspace/ISSUES.md`; match BUG/GAP or declare NEW |
| 2 | **SEARCH** | Search Elefante before memory writes; search canonical repository sources before file edits |
| 3 | **PROPOSE** | State Question / Proof / Result / Next |
| 4 | **PRESERVE** | Confirm a rollback path; archive only unique evidence not already recoverable from version control |
| 5 | **WRITE** | Author in canonical home per Closed Surface Map |
| 6 | **INDEX** | Update the relevant index in the same change |
| 7 | **INGEST** | Only for a new durable lesson: search, then add/update; never ingest routine progress |
| 8 | **VERIFY** | `pytest tests/test_developer_routing.py` + targeted regression + Elefante retrieval check |
| 9 | **JOURNAL** | Update [`workspace/PLANNING.md §10`](workspace/PLANNING.md) only when product state, a decision, or a verified conclusion changed |
| 10 | **CLOSE** | CLEAN → DOCS → VERIFY; commit, VERSION, and remote actions only within authority |

Verification is mandatory for changed behavior. Ingestion, journaling, commits,
and remote actions are conditional; empty process artifacts are forbidden.

Full detail: [`agents/orchestrator.md`](agents/orchestrator.md) § The Elefante Workflow Lifecycle.

---

## Trigger-first dispatch (developer agents)

Don't browse — load the specialist for your task.

| Symptom | Load |
|---------|------|
| Building a feature, debugging Elefante itself | [`agents/orchestrator.md`](agents/orchestrator.md) |
| Any `elefante-Memory(action="add"|"update"|"delete")` operation | [`agents/memory-janitor.md`](agents/memory-janitor.md) |
| "What do I have stored?", export, audit | [`agents/memory-inspector.md`](agents/memory-inspector.md) |
| Install failed, broken venv, repair | [`agents/installer.md`](agents/installer.md) |
| MCP tools missing in IDE, server stuck | [`agents/restarter.md`](agents/restarter.md) |
| Backup, restore, factory reset, restart | [`agents/operator.md`](agents/operator.md) |
| Version bump, CHANGELOG, tag, release | [`agents/release-manager.md`](agents/release-manager.md) |
| Line of attack is suspect (RESEARCH mode) | [`agents/researcher.md`](agents/researcher.md) |
| Need to retune the rules themselves (`PRIVILEGED` only) | [`agents/puppeteer.md`](agents/puppeteer.md) |
| IDE integration matrix drift audit | [`agents/integration-inspector.md`](agents/integration-inspector.md) |

---

## Repository layout

```
elefante/
├── AGENTS.md                    ← you are here (universal agent entry)
├── README.md                    ← product overview (humans)
├── CHANGELOG.md                 ← release history (frozen, append-only)
├── CONTRIBUTING.md              ← contributor process
├── .github/
│   ├── copilot-instructions.md  ← end-user agent constitution
│   └── workflows/               ← CI
├── .claude/
│   └── README.md                ← what this directory is for (documentation)
├── agents/                      ← 9 specialist agent protocols (loaded on trigger)
├── docs/
│   ├── README.md                ← documentation navigation
│   ├── explanation/             ← released product concepts
│   ├── how-to/                  ← released user procedures
│   └── reference/               ← released product contracts
├── workspace/                   ← developer workspace (consolidated planning + state)
│   ├── README.md
│   └── PLANNING.md              ← single living plan: vision/roadmap/features/aspects/state
├── tests/
│   └── test_developer_routing.py  ← active enforcement (BUG-026 + BUG-007 guards)
├── scripts/                     ← installer, verify, lifecycle, ci, debug, privileged
├── src/                         ← core engine, MCP server, dashboard
└── examples/                    ← first-use demo + advanced agent integration
```

---

## Core conventions (apply universally)

| Convention | Source-of-truth |
|------------|------------------|
| Sequential immutable IDs (BUG-NNN, GAP-NNN, X-NNN, P-NNN, OB-NNN) — **never date-stamped or version-stamped filenames** | [`agents/orchestrator.md`](agents/orchestrator.md) Documentation Skill § Forbidden Patterns |
| Status as field, not folder | Filenames stable; lifecycle is a frontmatter field |
| Search before write (Compliance Gate) | Mandatory in MCP tool surface |
| Closure sequence: CLEAN → DOCS → VERIFY; commit/version/remote actions only within authority | [`docs/how-to/close-a-feature.md`](docs/how-to/close-a-feature.md) |
| Memory Janitor: record removal of released artifacts; retain audit reasons for memory deletion; create with a recorded question; resolve don't file | [`agents/memory-janitor.md`](agents/memory-janitor.md) |
| Five Gates: Source-First, Spec Integrity, Leakage Scan, Numeric Verification, Output Discipline | [`agents/orchestrator.md`](agents/orchestrator.md) § The Five Gates |

Active enforcement: [`tests/test_developer_routing.py`](tests/test_developer_routing.py) fails CI on filename anti-patterns and routing drift.

---

## Integration surface

Machine-readable inventory of released, preview, community, and planned host
surfaces: [`agents/manifests/ide-integration.yaml`](agents/manifests/ide-integration.yaml).

For each surface, the matrix records: skill/rules path (project + global), MCP config path, file format, document URL, last-verified date, and current configuration status.

Currently configured instruction surface in this repo:
- `.github/copilot-instructions.md` — VS Code Copilot, GitHub Copilot

Per-IDE installation: [`docs/how-to/configure-ide.md`](docs/how-to/configure-ide.md).

---

## "Where are we?" (resume question)

Single canonical answer: [`workspace/PLANNING.md`](workspace/PLANNING.md) — vision, active release state, roadmap, features in design, blockers, decisions.

Companion canonical sources:
- [`workspace/ISSUES.md`](workspace/ISSUES.md) — BUG/GAP open issues
- [`CHANGELOG.md`](CHANGELOG.md) — release history (frozen)
- [`workspace/decisions/`](workspace/decisions/) — ADRs (when authored)

---

## What you must never do

1. Create a new markdown file without proving every existing canonical home is insufficient. Default: do not create.
2. Create date-stamped (`HANDOFF-YYYY-MM-DD.md`, `IDEA-YYYYMMDD-NNN.md`) or version-stamped (`spec-vXX.YY.ZZ-*.md`) filenames. Forbidden by Documentation Skill, enforced by `tests/test_developer_routing.py`.
3. Edit `Last verified` fields without re-running the verification.
4. Skip Loop Step 1 (`workspace/ISSUES.md` Known Issues check) before doc/code edits.
5. Print to stdout in MCP-reachable code.
6. Edit version strings by hand (use `scripts/ci/bump_version.py`).
7. Treat passive documentation as enforcement. **Active guards live in `tests/`.**

---

## Versioning

`v{MAJOR}.{MINOR}.{PATCH}`. Strict semver per [`docs/how-to/close-a-feature.md`](docs/how-to/close-a-feature.md). Use `scripts/ci/advise_version_bump.py` then `scripts/ci/bump_version.py X.Y.Z`. Never edit version strings manually.

Current published release: **v2.15.2**. Future work is tracked as unversioned **Upcoming** in [`workspace/PLANNING.md`](workspace/PLANNING.md).

---

## Active enforcement

Tests that catch documentation drift before it ships:

| Test | What it guards |
|------|----------------|
| `tests/test_developer_routing.py::test_no_forbidden_filename_patterns_in_active_docs_or_agents` | BUG-026 active guard: filename anti-patterns in `docs/` and `agents/` |
| `tests/test_developer_routing.py::test_active_developer_routing_avoids_retired_paths` | BUG-007 active guard: stale path references in active guidance |
| `tests/test_developer_routing.py::test_active_tool_docs_match_current_mcp_surface` | Tool-count drift between `src/mcp/server.py` and `docs/` |
| `tests/test_developer_routing.py::test_changelog_contract_is_synced_across_docs_and_embedded_rules` | CHANGELOG heading drift across surfaces |
| `tests/test_developer_routing.py::test_self_protocol_docs_are_linked` | Whole-system verifier reference integrity |
| `tests/test_developer_routing.py::test_scripts_readme_covers_live_script_inventory` | Script catalog drift |

Run: `pytest tests/test_developer_routing.py -v`. Do not state a current result without running it on the exact commit.

---

## Documentation Skill (compressed)

Every documentation change must answer **one question in one canonical place**. No buried ideas. No duplicate state. No session-memory files. No new markdown unless every existing canonical surface is proven insufficient. Full discipline: [`agents/orchestrator.md`](agents/orchestrator.md) § Documentation Skill.

**Closed Surface Map** (where each event lives):

| Event | Canonical home |
|-------|----------------|
| New idea | `workspace/PLANNING.md` §4.1 Backlog |
| Accepted feature design | `workspace/PLANNING.md` § Features |
| Current release state | `workspace/PLANNING.md` §2 Released Product |
| Bug or GAP | `workspace/ISSUES.md` |
| Bug postmortem | `workspace/postmortems/<domain>.md` |
| Reusable lesson | `workspace/lessons.md` |
| Shipped contract | `docs/reference/<name>.md` |
| Operational procedure | `docs/how-to/<name>.md` |
| Developer workflow | `agents/orchestrator.md` |
| Agent executable protocol | `agents/*.md` |
| Architecture decision | `workspace/decisions/ADR-NNNN-*.md` (when migrated; currently `workspace/PLANNING.md §2.5` for rejections) |
| IDE integration | `agents/manifests/ide-integration.yaml` |

---

*This file is the universal agent entry. When it conflicts with a more specific specialist file, the specialist wins for its domain. When this file conflicts with the canonical sources it points to, the canonical sources win.*
