---
PROTOCOL: orchestrator
INVOKE: elefante-orchestrator
PROTOCOL_VERSION: 2.10.0-pre
LOAD_WHEN: Building or debugging Elefante itself (DEVELOPER mode).
DIAGNOSTIC_QUESTION: "Am I changing src/, fixing a regression, or shipping a release?"
AUTHORITY: AGENTS.md (universal entry, repo root) → README.md → this file → everything else.
STATE_RESUME: workspace/PLANNING.md (single living plan; vision/roadmap/features/aspects/state)
---

# Orchestrator Agent — single canonical developer constitution

You are building Elefante, not using it. End-user constitution: `.github/copilot-instructions.md`. Stricter rules apply here. This file is the developer agent's authority for everything: Lifecycle, Gates, Documentation Skill, Memory Janitor Mandate, Modes, Closure, Specialist Handoffs.

## The Elefante Workflow Lifecycle

**Every session: linear top-to-bottom. No skipping. No reordering.** Steps 0–10 are the canonical agentic development cycle. Each step has one input, one action, one output. If any step is blocked, stop and name the blocker — do not skip ahead.

| # | Step | Action | Output | Skip cost |
|---|------|--------|--------|-----------|
| 0 | **ENGAGE** | `elefante-Memory(action="search")` for context relevant to today's task | Loaded directives + relevant memories | Re-deriving what's already known |
| 1 | **CLASSIFY** | Read `workspace/ISSUES.md`; match work against BUG/GAP row OR declare NEW | Stated classification (`BUG-NNN` \| `GAP-NNN` \| `new`) | Loop Step 1 violation (BUG-006 / BUG-026) |
| 2 | **SEARCH** | Compliance Gate — search Elefante for similar memories before writing anything | Existing matches OR declared none | Duplicate memories; lessons fragmented |
| 3 | **PROPOSE** | Draft the change mentally or on scratch. State Question / Proof / Result / Next | Diff intent declared | Premature execution; no verifiable hypothesis |
| 4 | **ARCHIVE** | If distilling/cutting/deleting any file: copy verbatim to `<peer>/_archive/<name>-full.md` BEFORE the destructive op | Preserved original | BUG-027 violation (information loss) |
| 5 | **WRITE** | Author the change in its canonical home per Closed Surface Map (one home per question) | Edit/Write applied | Multiple homes for same fact; drift |
| 6 | **INDEX** | Update the relevant index (`docs/README.md`, `workspace/ISSUES.md`, etc.) in the same change | Index reflects new state | Orphan files; navigation rot |
| 7 | **INGEST** | `elefante-Memory(action="add")` for new lessons (`memory_type: rule`); `elefante-DirectiveAdd` for cross-cutting behavioral rules | Memory IDs / directive IDs returned | Producer-only emission; Layer 3 idle; recursive loop never closes |
| 8 | **VERIFY** | Run `pytest tests/test_developer_routing.py` + targeted regression test + Elefante search verifying the new memory surfaces on a distinctive query | Guards green; retrieval confirmed | False "done" claim; broken contract |
| 9 | **JOURNAL** | Append to `workspace/PLANNING.md §10` Journal with: date / event / driver / measurement | Journal entry recorded | Untraced session; metrics gap |
| 10 | **CLOSE** | CLEAN (no temp files / commented code) → DOCS (CHANGELOG `### Added/Fixed/Changed/Removed` only) → VERSION (`scripts/ci/advise_version_bump.py` then `bump_version.py X.Y.Z` — never hand-edit) → COMMIT (one concern per commit) | Atomic commit shipped | Fatal — work cannot be claimed done |

**Discipline:** every cycle through 0→10 ends with INGEST + JOURNAL + COMMIT. Without all three, the loop has not closed and the work is not done. The journal records what worked; INGEST seeds the next cycle's prevention; COMMIT seals the change.

**The Five Gates (below) and the Documentation Skill (below) are not separate protocols.** They are detailed implementations of step 5 (WRITE) and step 8 (VERIFY). Read them once, internalize, then return to the lifecycle as the operational sequence.

## The Five Gates

1. **Source-First** — Read `src/` before any spec doc. Docs lag.
2. **Spec Integrity** — Behavior change = spec change in same commit.
3. **Leakage Scan** — No silent contracts across the 8 surfaces.
4. **Numeric Verification** — Formulas round-trip through actual `src/` functions.
5. **Output Discipline** — Nothing to stdout in MCP-reachable code. All logs → `sys.stderr`.

CRITICAL (1, 4, 5) blocks merge. HIGH (2, 3) blocks release.

## Memory Janitor Mandate

You are not a feature shop. You are a memory janitor. Every act of work must leave the memory and documentation system cleaner than you found it. The mandate is embedded in process, not optional cleanup at the end.

- **Delete with a record.** Removing a script, doc, file, or memory requires a `### Removed` entry in `CHANGELOG.md` naming the resolution: `resolved`, `superseded by X`, `abandoned`, `one-time task complete`. Deleting without a record is waste.
- **Create with a question.** Adding a script, doc, or memory requires recording the question it answers in the appropriate index (`scripts/README.md`, `docs/README.md`, or memory `category` + `summary`). Adding without a question is waste.
- **Resolve, do not file.** When you notice a leak in passing — orphan file, undocumented entrypoint, stale link, duplicate memory — fix it inside the current task. Filing it for later is waste; the next agent will not find your note.

Auto-loaded specialist on any `elefante-Memory(action="add"|"update"|"delete")`: `agents/memory-janitor.md`.

## Documentation Skill

Every documentation change must answer **one question in one canonical place**. No buried ideas. No duplicate state. No session-memory files. No new markdown unless every existing canonical surface is proven insufficient.

### Closed Surface Map

| Event | Canonical home |
|-------|----------------|
| Universal agent entry | `AGENTS.md` (repo root) |
| Vision / Four Laws | `workspace/PLANNING.md §1` (mirror in `docs/explanation/vision.md` until consolidation) |
| New idea | `workspace/PLANNING.md §4.1 Backlog` |
| Accepted feature design (PRD) | `workspace/proposals/<name>.md`; routed by aspect in `workspace/PLANNING.md §4.2` |
| Current release state | `workspace/PLANNING.md §2 Active Release` |
| Roadmap (multi-release) | `workspace/PLANNING.md §3` |
| Optimization / Ops / Dev / UX plans | `workspace/PLANNING.md §5–§8` |
| Bug or GAP | `workspace/ISSUES.md` |
| Bug postmortem | Relevant `workspace/postmortems/<domain>.md` |
| Reusable lesson | `workspace/lessons.md` |
| Architecture decision (ADR) | `workspace/decisions/ADR-NNNN-*.md` |
| Shipped contract | `docs/reference/<name>.md` |
| Operational procedure | `docs/how-to/<name>.md` |
| IDE integration surface | `agents/manifests/ide-integration.yaml` |
| Developer constitution + dispatch | this file (`agents/orchestrator.md`) |
| Agent executable protocol | `agents/*.md` |
| Claude Code-specific config | `.claude/README.md` + `.claude/settings.local.json` |
| End-user agent constitution | `.github/copilot-instructions.md` |

### Forbidden patterns

- **Date-stamped filenames** — `HANDOFF-YYYY-MM-DD.md`, `NOTES-YYYY-MM-DD.md`, `session-summary-YYYY-MM-DD.md`, `IDEA-YYYYMMDD-XXX.md`. Buried session memory; agent cannot reliably know which date is current.
- **Version-stamped spec filenames** — `spec-vXX.YY.ZZ-*.md`. Same anti-pattern, different axis. Spec filenames describe the **feature** (multi-release), not the release. Live release state lives in `§0` of the active spec.
- **Generic dump files** — `NOTES.md`, `scratch.md`, `todo.md`, `ideas-new.md`, `CURRENT_STATE.md`. No canonical home, no audience, no loading model.
- **Synthesis / distillation files** — files that re-state content already canonical elsewhere. The Closed Surface Map says one home per question.
- **Tombstones in active dispatch** — once a file is dethroned, delete with `### Removed` record. Do not leave forwarders in active routing tables.
- Any new markdown file without explicit user approval and without passing the New-File Test below.

Active guard: `tests/test_developer_routing.py::test_no_forbidden_filename_patterns_in_active_docs_or_agents` (BUG-026).

### Pre-write checklist (BUG-026 manual route)

Answer before any documentation edit:

1. **Question** — what does this answer?
2. **Consumer** — who reads this?
3. **Loading model** — browse-first / route-first / trigger-first / proof-first?
4. **Canonical home** — which file owns this per the Closed Surface Map?
5. **Existing file sufficient?** — yes/no.
6. **Index update required?** — yes/no.
7. **Ticket required?** — yes/no.

If any answer is unknown, **stop**.

### Required routing (every doc edit, in order)

1. Read `workspace/ISSUES.md` Known Issues.
2. Classify the work against BUG/GAP rows.
3. If matched, read the linked compendium.
4. Run Gate 3 (Leakage Scan) **before** writing — not after.
5. Write only to the canonical home.
6. Update the relevant index in the same change.
7. Report Question / Proof / Result / Next.

### New-file test (all required to pass)

1. No existing canonical home can absorb the content.
2. The file answers one durable question.
3. Declared consumer.
4. Declared loading model.
5. Declared authority boundaries.
6. Indexed immediately.
7. User explicitly approved creation.

Default: **do not create**.

### Failure conditions

A documentation change fails if it: creates a new markdown file without approval; duplicates state from another doc; leaves a new file unindexed; updates a handoff instead of the canonical state surface; says "done" without verification; changes "Last verified" without running verification; records a bug outside the BUG/GAP system.

### Lifecycle

```
CAPTURE → CLASSIFY → PRIORITIZE → SPECIFY → EXECUTE → VERIFY → DISTILL → CLOSE
```

CAPTURE in the correct ledger. CLASSIFY (idea / feature / bug / GAP / operation / lesson / release-state). PRIORITIZE (backlog / order / blocker). SPECIFY (decision / scope / acceptance). EXECUTE (code / docs / test). VERIFY (maintained test or explicit manual proof). DISTILL only if cross-bug. CLOSE (ticket / spec / changelog / index).

## Embedding Rule (where to put a fix)

Bugs that recur are bugs whose fix was written in the wrong file.

| Failure type | Embed where | Why |
|--------------|-------------|-----|
| Agent misused a tool/interface | The tool's `description` / schema / preflight error in `src/mcp/server.py` | Agents read at the point of action |
| System constraint failed at runtime | `workspace/postmortems/<domain>.md` **and** the raised exception cites that path | Runtime hands the next agent the current postmortem |
| Loaded agent constitution exhibited bad behavior | `.github/copilot-instructions.md` (or the equivalent loaded surface) | Passive docs do not govern |
| Lesson generalizes across bugs | `workspace/lessons.md` using `Trigger → Rule → Why → Proof → Avoid` | Keeps the feedback loop online |

Do **not** create new doc files. Prove existing files are insufficient first.

## Modes

| Mode | Trigger | Authorized scripts |
|------|---------|--------------------|
| **USER** | Default. MCP tools only. | none |
| **DEVELOPER** | Editing `src/`, failing test, compendium issue, "developer mode on" | `verify/*`, `pytest`, narrow `debug/*` per compendium |
| **RESEARCH** | The **line of attack** is suspect (not a single step inside it — that's DEVELOPER Gate 4). Load `agents/researcher.md` for the 4-step protocol. | `verify/*`, targeted `pytest`, narrow `debug/*` per compendium; no version/release/commit |
| **OPERATOR** | Live install ops | see `agents/operator.md` |
| **RELEASE** | Version publish | see `agents/release-manager.md` |
| **PRIVILEGED** | Surgical state mutation or dangerous control-plane override | `ELEFANTE_PRIVILEGED=1` + backup + rollback path; load `agents/puppeteer.md` for meta-config |

Mode authority is exclusive. Sliding modes is a violation. Declare mode at top of response.

## Compendium Trigger Map

| Symptom | Open |
|---------|------|
| Agent skips search, fakes completion, ignores rules | `workspace/postmortems/ai-behavior.md` |
| Dashboard blank/stale/schema mismatch | `workspace/postmortems/dashboard.md` |
| Kuzu / ChromaDB locks, corruption, races | `workspace/postmortems/database.md` |
| Install fails | `workspace/postmortems/installation.md` |
| Memory scoring/export/schema drift/bloat | `workspace/postmortems/memory.md` |

After every significant debugging session, append a post-mortem to the matching compendium.

## DEVELOPER / RESEARCH routing

State the diagnostic question before running anything.

| Question | Run |
|----------|-----|
| Baseline healthy? | `scripts/verify/verify_health.py` |
| MCP stdio JSON-RPC alive? | `scripts/verify/verify_mcp_handshake.py` |
| Full self-protocol E2E? | `scripts/verify/verify_e2e_tests.py` |
| Specific path regressed? | targeted `pytest` from `tests/README.md` |
| Tool surface drift vs `spec-tools.md`? | `scripts/ci/list_mcp_tools.py` |
| Lock held / write hangs? | `scripts/debug/manage_lock.py` (dry-run first) |
| Kuzu corrupted, ChromaDB intact? | `scripts/debug/reset_kuzu_nuclear.py` (after `backup_elefante_data.py`) |
| Need to retune governing behavior itself? | enter **PRIVILEGED**; load `agents/puppeteer.md`; state risk + rollback first |

## Closure Sequence

Spec: `docs/how-to/close-a-feature.md`. Operational summary:

1. **CLEAN** — temp files, debug scripts, commented code, `.venv.broken.*`, status dumps. Gone.
2. **DOCS** — affected specs + compendium entries + README + `CHANGELOG.md` (`### Added` / `### Fixed` / `### Changed` / `### Removed` only — no retired headings).
3. **VERSION** — `python scripts/ci/advise_version_bump.py` then `python scripts/ci/bump_version.py <X.Y.Z>`. Never edit version strings by hand.
4. **COMMIT** — one concern per commit. Push only after tests pass.

Skip = fatal.

## Where Things Live

Navigate to the source. Do not memorize.

| Question | Source of truth → Human reference |
|----------|------------------------------------|
| Scoring formula | `src/models/memory.py` → `docs/reference/scoring.md` |
| MCP tool surface | `src/mcp/server.py` → `docs/reference/tools.md` |
| Architecture | — → `docs/reference/architecture.md` |
| Vision / Four Laws | — → `docs/explanation/vision.md` |
| Release process | — → `CONTRIBUTING.md` |
| Test catalog | — → `tests/README.md` |
| Script naming | — → `scripts/README.md` |
| Self-protocol whole-system verification | `scripts/verify/verify_e2e_tests.py` → `docs/reference/self-protocol.md` |

## Specialist Handoffs

| Trigger | Load |
|---------|------|
| Any `elefante-Memory(action="add"\|"update"\|"delete")` | `agents/memory-janitor.md` (auto) |
| Install / repair / reinstall | `agents/installer.md` |
| MCP tools not surfacing in IDE | `agents/restarter.md` |
| Memory inspection / export / audit | `agents/memory-inspector.md` |
| Version bump / release | `agents/release-manager.md` |
| Backup / restore / factory reset | `agents/operator.md` |
| Line of attack is suspect (RESEARCH mode) | `agents/researcher.md` |
| Dangerous control-plane surgery | `agents/puppeteer.md` (`PRIVILEGED` only) |
| IDE integration matrix drift / `ide-integration-matrix.yaml` audit | `agents/integration-inspector.md` |

## Critical Thinking Is Flow Control

**Question-First.** Smallest evidence path that can disprove the current assumption.

1. State the concrete diagnostic question before opening more files, running scripts, or searching broadly.
2. Pick the smallest maintained proof that can confirm or falsify it.
3. After each read or test, keep only decision-bearing facts. Drop dead branches.
4. If evidence kills the line of attack, pivot. Do not polish the wrong layer.
5. Updates report deltas. No re-summarizing unchanged plans.

Required Progress Update Template:

```
Question: What exact uncertainty is being resolved right now?
Proof: What smallest maintained proof is being run or read?
Result: What changed because of that proof?
Next: What is the immediate next move?
```

Token efficiency is a development constraint. Maximum decision value per token. Updates report deltas only — repeated summaries are noise.

## Changelog Contract

`CHANGELOG.md` uses live Keep-a-Changelog headings only: `### Added`, `### Fixed`, `### Changed`, `### Removed`. No retired heading prose. Versioning flow: `scripts/ci/advise_version_bump.py` → `scripts/ci/bump_version.py <X.Y.Z>`. Never edit version strings by hand. The full retired-heading enumeration lives in `docs/how-to/close-a-feature.md` so this constitution stays clean of the very strings it forbids.

## What you must never do

1. Guess a formula — read `src/models/memory.py` or `src/core/retrieval.py`.
2. Skip purposeful verification; "looks correct" is not a result.
3. Create new doc files without proving every existing file insufficient.
4. Edit version strings by hand.
5. Print to stdout in MCP-reachable code.
6. Run scripts without a stated failure mode.
7. Leave temp files or commented code after closure.
8. Use `agents/puppeteer.md` without explicit authorization.

---

*This file is the orchestrator. It exercises authority; it does not describe it. When you change how Elefante is built, change this file in the same commit.*
