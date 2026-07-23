# Elefante Vision

> Last updated: 2026-07-22 · Current version: v2.10.0

---

## The Thesis (Read This First)

Elefante is a **Full Signal Injection** layer for AI agents.

Every AI agent runs on the same physics: a finite context window where every token either raises the probability of a correct answer or dilutes it. Most workflows lose by injecting noise — restated history, irrelevant retrievals, polite filler, stale assumptions. Elefante wins by injecting only the tokens with the highest decision-value at the moment of action.

**The product is one sentence:** Elefante maximizes signal-per-token in the agent's context window.

Everything else in this document — memory, scoring, dashboards, MCP tools — is a *mechanism* in service of that single thesis. If a feature does not measurably improve signal density, it does not belong in Elefante.

---

## What Is Elefante

Elefante is a **local-first persistent memory engine for AI agents**, and it exists to execute the Full Signal Injection thesis above.

Every AI coding session starts from zero. The agent doesn't remember your preferences, your architecture decisions, or the bug you both fixed last Tuesday. You re-explain, it re-discovers, and you both waste time — every wasted token is a probability tax on the next answer.

Elefante fixes this. It gives your AI agent a **second brain** — a persistent, searchable memory that:

- **Remembers** facts, preferences, decisions, code patterns, and tasks across sessions
- **Retrieves** the right context at the right moment using hybrid search (vectors + knowledge graph)
- **Learns** what matters from your behavior, not from labels you assign
- **Injects** the highest-signal memories into every interaction automatically — and *suppresses the rest*

It runs locally on your machine. No cloud. No API keys for memory. Your data stays yours.

### Universal Agent Contract

Elefante is for developers who move between Claude, Codex, Gemini, Grok, Agent Zero, OpenClaw, and the next agent host — not for one editor's captive ecosystem. The product contract is one local memory authority per user, exposed through the transport each host can actually use: native local HTTP for capable clients and a compatibility bridge for stdio-only clients. The runtime, not a collection of editor plugins, owns storage, concurrency, provenance, and upgrades.

No host is marketed as supported until its installation, reconnect, concurrent-write, uninstall, and upgrade path are verified. “MCP-compatible” is compatibility evidence, not a promise of a polished integration.

### How It Works (Today and Next)

Today Elefante runs as an MCP server, usually connected through stdio. When an agent works, Elefante injects relevant memories from its dual storage system (ChromaDB by default for semantic search, Kuzu for the knowledge graph). A local SQLite semantic-store backend is available as an explicit fresh-store opt-in; existing ChromaDB data is never converted without a separately authorized migration. Every memory has a system-computed relevance score based on recency, freshness, and how often it's been useful. Memories that matter rise to the top. Memories that don't, decay naturally. The active product roadmap replaces per-client database ownership with one local daemon, native local HTTP, and a bridge for stdio-only hosts so multiple tools can share the same trustworthy memory authority.

### The Four Laws

These are non-negotiable and define everything Elefante does. Law 4 is the governing thesis; Laws 1–3 are the mechanisms that make Law 4 achievable.

1. **Continuity** — A session is never new; it is a continuation. *(Without continuity, every retrieval starts from zero signal.)*
2. **Compliance** — Search before writing. Ignorance is a choice, not a constraint. *(Without compliance, the agent generates noise where signal already exists.)*
3. **Grounding** — If it's not in the brain or the workspace, it's UNKNOWN. No hallucination. *(Without grounding, injected tokens carry false signal — worse than no signal.)*
4. **Full Signal Injection (Efficiency)** — Every token Elefante injects must measurably raise the probability of a correct answer. Memory that doesn't improve the response is noise, not context. **Quality per token is the only metric.** This law disqualifies any feature, retrieval, or response token that cannot defend its presence on signal-density grounds.

---

## Where We Are

**Shipped and working:**

| Capability | What It Does |
| ---------- | ------------ |
| 16 MCP tools | Memory CRUD, graph queries, tasks, ETL, directives, context injection |
| Dual storage | ChromaDB by default (semantic vectors; SQLite fresh-store opt-in) + Kuzu (knowledge graph) |
| Behavioral scoring | System-computed relevance (0-100) with type-based decay rates |
| 5-signal cognitive retrieval | Vector similarity, concept overlap, co-activation, authority, temporal |
| Compliance gate | Mechanical search-before-write enforcement |
| Agent-driven ETL | Classification without internal LLM calls — the agent's own LLM does the work |
| Autonomous co-activation | Passive graph wiring between memories retrieved together |
| Context injection | Top memories surfaced automatically in every tool response |
| Response compression | Null-stripped, token-efficient payloads with behavioral directives |
| Token intelligence | Per-call TOKEN_STATS (output tokens, overhead, signal ratio), type-proportional budgets, density warnings |
| Dashboard | React + SVG: health scores, memory table, knowledge graph visualization |
| Session distiller | Scan, parse, and ingest knowledge from VS Code chat logs |
| Runtime baseline bootstrap | Built-in directives and required specification memories are available on first use |
| One-click install | `./install.sh` (macOS/Linux) or `install.bat` (Windows) |

---

## The Vision

### 1. The Cognitive Loop

Elefante's endgame is not storage — it's **intelligent context injection at the moment of action**.

The model: **Intercept → Process → Contextualize → Enhance**

1. The agent receives a task or query
2. Elefante intercepts and searches its brain for relevant context
3. High-density relevancy (rules, facts, pitfalls, preferences) is injected
4. A "blind" answer becomes an **Elefante Enhanced Answer** — grounded in history, identity, and truth

Today this happens reactively (agent calls tools). The vision is for it to happen **proactively** — Elefante surfaces what you need before you ask.

### 2. Importance Emerges from Behavior

Nobody assigns importance. Nobody rates memories 1-10. Importance **emerges** from how memories are used:

- Memories that are retrieved frequently grow stronger (reinforcement)
- Memories that aren't accessed decay naturally (type-based half-lives)
- Memories used together form organic clusters (co-activation)

The system discovers what matters. The user just works.

### 3. Memory Has a Lifecycle

Not all knowledge ages the same way:

| Type | Half-Life | Why |
| ---- | --------- | --- |
| Specification / Directive | ∞ | Architecture and rules don't decay |
| Preference | ~347 days | Stable but can shift |
| Decision / Fact | ~139 days | Get revisited over time |
| Insight | ~87 days | Validated or forgotten |
| Note | ~46 days | Transient context |
| Conversation | ~28 days | Ephemeral |

This is already implemented. The vision is to make this lifecycle **visible and actionable** through health indicators.

### 4. Local-First, Always

No cloud dependency. No subscription for memory. The second brain runs on your machine, backed by local files. You can back it up, move it, factory reset it. It's yours.

---

## Ideas Backlog

Everything below emerged during development and represents where Elefante could go. Organized by theme, roughly prioritized within each theme.

### A. Memory Intelligence

**Memory Health Score** — Every memory gets a health indicator: healthy, stale (90+ days untouched), at-risk (contradicted/superseded), or orphan (no graph connections). Dashboard shows health visually with actionable prompts ("Review this memory", "Resolve conflict", "Connect or archive").
*Status: Designed in detail. Not built.*

**Potential Conflict Detection** — Automatically flag memories with high concept overlap and opposing patterns. Soft detection only — system suggests, user confirms or dismisses. Never auto-assert contradiction.
*Status: Designed. Not built.*

**Smart Update (Merge)** — When new information relates to an existing memory, merge instead of duplicating. Track version history of how a memory evolved over time.
*Status: Concept only.*

### B. Proactive Retrieval

**Proactive Memory Surfacing** — The system suggests relevant memories without the user searching. Triggers: file opened (surface memories tagged with that file), error in terminal (surface memories matching error pattern), conversation keyword match via `surfaces_when` field.
*Status: Designed. `surfaces_when` field exists in schema. Surfacing logic not built.*

**Retrieval Explanation (UI)** — Search results include WHY they were retrieved — breakdown of vector similarity, concept overlap, co-activation, authority, and temporal signals. Backend returns this data. Dashboard doesn't display it yet.
*Status: Backend done (v2.1). Frontend display not built.*

### C. Dashboard & Visualization

**Usage Intelligence** — Surface whether memories are actually being used. Backend tracks `access_count` and `last_accessed` already. Missing: `last_accessed` in dashboard snapshot, frontend components for "never retrieved" analysis, "most retrieved" ranking, usage-based health metrics. Detailed PRD exists.
*Status: Backend 80% done. Snapshot pipeline needs 1 field. Frontend 0%.*

**Dashboard UX Improvements** — Color nodes by memory type or domain. Show only high-relevance nodes by default. Health indicators on graph nodes. Rich tooltips on signal hubs (topic, ring, knowledge_type) showing cognitive purpose, retrieval triggers, authority weight, sample concepts, and cluster health summary.
*Status: Designed. Not built.*

### D. Session Distiller Expansion

**Live Mode** — Background file watcher that auto-distills new chat logs as they appear. `distill all --auto` command. Progress bars for batch operations.
*Status: Designed in task spec. Not built.*

**Team Sync API** — Share distilled knowledge across team members. Dashboard metric for distiller throughput. Export functionality.
*Status: Concept in task spec. Not built.*

### E. Multi-Modal & Platform

**Multi-Modal Memory** — Image memory support. Audio transcription integration. Store and retrieve non-text knowledge.
*Status: Concept only.*

**Cross-IDE Support** — Currently works via MCP stdio with any MCP-compatible client. Constitution is symlinked for VS Code, Cursor, and Windsurf. Bob-IDE has no documented constitution injection path.
*Status: MCP protocol works universally. Per-IDE setup varies.*

**Agent Zero Integration** — Elefante runs as Agent Zero's persistent memory layer instead of its FAISS store, so behavioral directives and project memories survive across Agent Zero sessions and inject under the same Full Signal Injection rules used everywhere else. Spec: [`integrations/agent-zero.md`](integrations/agent-zero.md).
*Status: Target documented. Not built.*

### F. Distribution Packaging

**Branded macOS DMG Installer** — A `.dmg` disk image published as a GitHub Release asset alongside the existing zip bundles. Opens to a branded Finder window with the Elefante logo as the volume icon, a README, and a link to www.elefante.ai. Contains the full installer bundle (`install.sh` + payload). No Applications symlink — Elefante is not a `.app`; the user runs `install.sh` from the mounted volume or copies the folder first. The DMG is compressed (UDZO/zlib-9). **Distribution requirement:** DMGs uploaded to GitHub Releases must be signed with a Developer ID Application certificate, notarized via `notarytool`, and stapled via `xcrun stapler`. Unsigned DMGs are blocked by macOS Gatekeeper on download and must not be published. The CI workflow gates DMG upload behind `APPLE_DEVELOPER_ID` secret presence. Requires: Apple Developer Program membership ($99/yr), Developer ID certificate, App-Specific Password for `notarytool`.
*Status: Build script done (`scripts/ci/build_dmg.py`). CI wired with signing gate. Signing credentials not yet configured — DMG will not upload to releases until secrets are set.*

**Branded Windows EXE Installer** — A self-extracting installer (NSIS or WiX) published as a GitHub Release asset. Bundles `install.bat` + payload. Branded with Elefante logo and www.elefante.ai. Runs `install.bat` post-extraction.
*Status: Not built.*

**Manual Fallback Path** — For users who prefer not to use packaged installers: clone the repo, ask your AI agent to read the README first. Elefante will handle it from there. This path must always remain functional and documented.
*Status: Shipped. `install.sh` / `install.bat` from source.*

---

## Non-Goals (Anti-Divagation Anchor)

Elefante is **not** the following, and any proposal that drifts toward these must be rejected at the spec level — not after the code is written.

1. **Not a generic AI platform.** No model hosting, no agent runtime, no "orchestration framework." Other projects own those layers; Elefante injects signal into whichever runtime the user already chose.
2. **Not a chat product.** Elefante never owns the conversation surface. It augments it.
3. **Not a SaaS memory store.** Local-first is a law, not a phase. Cloud sync, if it ever ships, is a transport — never the source of truth.
4. **Not an observability product first.** Debugging dashboards, replay, and trace consoles are *outputs* of Full Signal Injection (the system already knows which memories drove which answers); they are never the thesis. If a debugging feature does not also raise signal density at injection time, it is out of scope.
5. **Not a feature-count race.** Elefante does not compete on number of MCP tools, number of memory types, or number of integrations. It competes on signal-per-token. Every new tool must remove more noise than it adds.
6. **Not a prompting framework.** Elefante does not generate prompts, rewrite prompts, or teach "prompt engineering." It injects grounded context.

When in doubt: re-read the Thesis section and Law 4. If a proposal cannot be defended in those terms, it does not ship — regardless of how interesting, monetizable, or technically elegant it appears.

---

## What This Document Is Not

This is not a spec, a roadmap with dates, or an implementation guide. It's the **single source of truth for what Elefante is, where it's going, and what ideas exist**. For implementation details of shipped features, see `docs/reference/` and `docs/how-to/`. For detailed specs of unbuilt features, see the files referenced in each idea above.
