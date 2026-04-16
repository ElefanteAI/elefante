# Elefante Vision

> Last updated: 2026-04-15 · Current version: v2.7.1

---

## What Is Elefante

Elefante is a **local-first persistent memory engine for AI agents**.

Every AI coding session starts from zero. The agent doesn't remember your preferences, your architecture decisions, or the bug you both fixed last Tuesday. You re-explain, it re-discovers, and you both waste time.

Elefante fixes this. It gives your AI agent a **second brain** — a persistent, searchable memory that:

- **Remembers** facts, preferences, decisions, code patterns, and tasks across sessions
- **Retrieves** the right context at the right moment using hybrid search (vectors + knowledge graph)
- **Learns** what matters from your behavior, not from labels you assign
- **Injects** relevant memories into every interaction automatically

It runs locally on your machine. No cloud. No API keys for memory. Your data stays yours.

### How It Works (One Paragraph)

Elefante runs as an MCP server that your IDE connects to via stdio. When your agent works, Elefante intercepts tool calls and injects relevant memories from its dual storage system (ChromaDB for semantic search, Kuzu for knowledge graph). Every memory has a system-computed relevance score based on recency, freshness, and how often it's been useful. Memories that matter rise to the top. Memories that don't, decay naturally. The agent can store new knowledge, search existing knowledge, manage tasks, and build a knowledge graph — all through 20 MCP tools and 2 prompts.

### The Four Laws

These are non-negotiable and define everything Elefante does:

1. **Continuity** — A session is never new; it is a continuation.
2. **Compliance** — Search before writing. Ignorance is a choice, not a constraint.
3. **Grounding** — If it's not in the brain or the workspace, it's UNKNOWN. No hallucination.
4. **Efficiency** — Every token Elefante injects must earn its place. Memory that doesn't improve the response is noise, not context. Quality per token is the metric.

---

## Where We Are

**Shipped and working:**

| Capability | What It Does |
| ---------- | ------------ |
| 21 MCP tools | Memory CRUD, graph queries, tasks, ETL, directives, context injection |
| Dual storage | ChromaDB (semantic vectors) + Kuzu (knowledge graph) |
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

---

## What This Document Is Not

This is not a spec, a roadmap with dates, or an implementation guide. It's the **single source of truth for what Elefante is, where it's going, and what ideas exist**. For implementation details of shipped features, see `docs/technical/`. For detailed specs of unbuilt features, see the files referenced in each idea above.
