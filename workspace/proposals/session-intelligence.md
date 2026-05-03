# PRD: Session Intelligence - Privacy-Respecting Invocation Telemetry

> **Status**: DRAFT - Feature request
>
> **Owner**: Elefante dev team
>
> **Date**: 2026-04-17
>
> **Scope**: Local-first session and invocation telemetry so Elefante can answer when it was called, by which client, what happened, and whether it helped, without storing raw chat transcripts by default

---

## Question This Spec Answers

How can Elefante tell, per session and per client, when it was invoked, how it was used, and whether it helped, without violating user privacy?

---

## 1. Problem Statement

Elefante already knows memories, scores, co-activation history, and some per-call token costs.

Elefante does **not** currently know enough about a session to answer the questions the product owner now needs answered:

- When was Elefante invoked in chat session X?
- Which IDE or MCP client called Elefante most this week?
- Which tools were used, how often, and for how long?
- Which retrievals actually helped downstream instead of just consuming tokens?
- Which queries returned nothing?

That is a real product gap.

It matters because Elefante's core thesis is not raw storage. It is signal quality. If Elefante cannot measure invocation context and downstream usefulness, it cannot prove whether a retrieval increased useful signal or just created noise.

---

## 2. Honest Assessment: Current Elefante Reality

The current system has partial building blocks, but not a real session-intelligence layer.

| Surface | Current State | Gap |
| ------- | ------------- | --- |
| MCP session identity | `session_id` exists as an optional tool argument | Elefante does not generate session IDs on its own |
| Client attribution | Not captured in the MCP server | Cannot tell VS Code from Cursor, Bob, Antigravity, or another client |
| Per-call token stats | Computed by `SessionTokenLedger` and returned as `TOKEN_STATS` | Not persisted; lost on restart |
| Retrieval history | Last 20 retrieved memory IDs persisted for 7 days | Too thin to reconstruct real invocation history |
| Co-activation | Persisted in Kuzu and already useful as a reuse proxy | Does not answer query-level provenance |
| Retrieval effectiveness | Planned in `spec-retrieval-effectiveness.md` | Still missing per-retrieval logs, unanswered-query logs, and usefulness surfacing |
| Privacy | No remote telemetry, rotating logs, secrets scrubber in the distiller | Direct `MemoryAdd` calls are not scrubbed and raw session invocation metadata is not structured |

This feature request exists because the current system cannot answer session-level product questions with confidence.

---

## 3. Core Requirement

Elefante must gain a privacy-respecting session-intelligence layer that can answer, locally and truthfully:

1. **Who called Elefante** - client or IDE name when available.
2. **When Elefante was called** - session lifecycle plus per-tool invocation timestamps.
3. **What happened** - tool name, result shape, latency, token cost, retrieval count.
4. **Whether it helped** - downstream reuse or reinforcement signal, not just raw retrieval count.
5. **What failed to help** - unanswered queries and dead-weight retrievals.

This must remain local-first and privacy-bounded.

---

## 4. Non-Negotiable Privacy Contract

This feature is only acceptable if it stays inside these guardrails.

### 4.1 Local-First Only

- No remote telemetry.
- No SaaS analytics endpoint.
- No silent network egress.

### 4.2 No Raw Transcript Storage By Default

The goal is invocation intelligence, not transcript warehousing.

Default event payloads must store metadata, not chat logs.

Allowed by default:

- `session_id`
- `invocation_id`
- `client_name`
- `tool_name`
- `timestamp`
- `duration_ms`
- `result_count`
- `returned_memory_ids`
- `signal_ratio`
- `query_hash`

Disallowed by default:

- full raw prompts
- full tool arguments containing arbitrary user content
- copied chat transcripts
- full memory content duplicated into telemetry

### 4.3 Redaction Before Persistence

If the system stores any query preview for debugging, it must:

- run the existing privacy scrubber first
- truncate aggressively
- expire on a short retention window

### 4.4 Bounded Retention

Suggested defaults:

- detailed invocation events: 30 days
- session summaries: 90 days
- aggregate daily stats: 365 days

Retention must be automatic, documented, and testable.

---

## 5. Product Decision

This feature should ship as **Session Intelligence**, a local event layer dedicated to session and invocation analytics.

It should not be forced into ChromaDB semantic memory records.

It should not overload the Kuzu graph with high-volume event noise.

### Preferred Storage Surface

Use a dedicated local telemetry store for event-style data.

Preferred implementation:

- `~/.elefante/data/session_intelligence.db`

Reason:

- time-window aggregates are first-class
- retention pruning is cheap
- daily and weekly rollups are easy
- session events are not semantic memory and should not pollute ChromaDB

Fallback if the team rejects a dedicated store:

- append-only JSONL with a maintained rollup pipeline

Hard rule:

Do **not** store this in a way that makes weekly statistics or retention enforcement painful.

---

## 6. What Must Exist

### 6.1 Server-Generated Session Lifecycle

Elefante must stop depending on the client to provide `session_id`.

The MCP server should create:

- a `session_id` when the conversation or transport lifecycle begins
- an `invocation_id` for every tool call

If a client supplies its own session identifier, Elefante may record it as `client_session_id`, but Elefante still owns the canonical local session record.

### 6.2 Client Attribution

Capture client identity from the MCP handshake or request context when available.

Minimum field:

- `client_name` = `vscode`, `cursor`, `bob`, `antigravity`, `openclaw`, `claude_desktop`, or `unknown`

This must be normalized, not free-form.

### 6.3 Invocation Event Log

Every tool call should append a local event with at least:

- `invocation_id`
- `session_id`
- `client_name`
- `tool_name`
- `started_at`
- `finished_at`
- `duration_ms`
- `status` (`success`, `error`, `ignored`, `blocked`)
- `result_count`
- `output_tokens`
- `overhead_tokens`
- `signal_ratio`

For retrieval-bearing calls, also record:

- `query_hash`
- `mode`
- `returned_memory_ids`
- `top_score`

### 6.4 Retrieval Usefulness Signals

This feature must not stop at invocation counts.

It must measure whether a retrieval mattered.

Minimum acceptable proxy set:

- retrieval followed by same-session co-activation
- retrieval followed by reinforcement or access_count increase inside the same session
- unanswered query count
- dead-weight retrieval count (`retrieved often`, `never reused`)

Optional later signal:

- explicit agent acknowledgement that a retrieved memory was useful

### 6.5 Session Summary Surface

Elefante must be able to answer, for one session:

- when the session started and ended
- which client used it
- which tools were called and how many times
- which memories were retrieved
- which retrievals led to reuse
- which queries returned nothing
- token overhead vs payload for the session

### 6.6 Weekly and Daily Aggregate Stats

Elefante must be able to answer, at minimum:

- which client called it most this week
- tool-call counts by client
- average signal ratio by tool
- unanswered-query totals by day
- dead-weight memories surfaced this week

### 6.7 Source / Origin Schema (Multi-Instance Writes) — Closes GAP-025

All of § 6.1–§ 6.6 assume Elefante can attribute every write to a specific client, project, and session. Today it cannot — there is no origin metadata captured on writes (see [`../debug/ops-memory-compendium.md`](../debug/ops-memory-compendium.md) Issue #15 / GAP-025). Session Intelligence is therefore blocked at the data layer until this schema lands.

**Required Source tuple, captured on every memory-affecting write:**

| Field | Purpose | Source |
| ----- | ------- | ------ |
| `source.tool` | Normalized client name, matching the matrix id in [`../technical/ide-integration-matrix.yaml`](../technical/ide-integration-matrix.yaml): `claude-code`, `vscode-copilot`, `cursor`, `bob`, `kiro`, `gemini-cli`, `codex-cli`, `zed`, ... | MCP handshake client envelope |
| `source.instance_id` | UUID per IDE window/process. Lets Session Intelligence distinguish two concurrently open IDEs of the same tool | Generated by daemon at MCP connection open |
| `source.session_id` | Canonical server-generated session id per § 6.1 | Session lifecycle (§ 6.1) |
| `source.cwd` | Working directory active at the moment of the write. Lets per-project reuse analysis exist at all | Captured on each invocation |
| `source.matrix_version` | Version of the integration matrix the client was installed against. Lets drift audit correlate stale-install writes with known matrix changes | Stamped at install time, read from the IDE-side config emitted by the installer |
| `source.timestamp_utc` | Write instant, independent of the memory's own `created_at` | Daemon clock |

**Graph shape:** `(:Memory)-[:WRITTEN_BY]->(:Source)`. Source nodes are deduplicated on the `(tool, instance_id, session_id)` tuple — one Source node per live connection, not one per write.

**Writer contract:** the daemon (see [`spec-ide-integration-surface.md`](spec-ide-integration-surface.md) § 4.2 and § 7.1) is the only writer. It composes the Source tuple from the handshake envelope plus per-invocation `cwd`, and stamps it onto every memory-affecting call. Agent-side tool arguments never fabricate `source.*` — the daemon overwrites with ground truth.

**Why this sits in session-intelligence, not only in the IDE-integration spec:** the tuple is the join key between the invocation event log (§ 6.3), the retrieval usefulness signals (§ 6.4), and the session summary (§ 6.5). Without the Source schema, none of the session-intelligence questions can be answered per-client or per-project. § 6.7 is therefore a hard prerequisite for the rest of § 6, not a nice-to-have annotation.

**Acceptance (mirrors § 10 additions):** every memory written after the closure date has a non-null `source.tool` and `source.instance_id`; no row in the store is anonymous; two concurrently open IDEs produce two distinct `source.instance_id` values with no Kuzu lock contention.

---

## 7. Non-Goals

- Not full chat transcript capture.
- Not keystroke analytics.
- Not user surveillance.
- Not cross-device fingerprinting.
- Not a remote analytics product.
- Not ranking or profiling users.
- Not a new semantic memory type.
- Not a major UI rewrite.

This is a focused observability layer for Elefante's own usefulness, not a behavior-mining system.

---

## 8. Proposed Data Model

The exact schema is an implementation detail, but the product contract needs these entities.

| Entity | Purpose |
| ------ | ------- |
| `SessionRecord` | One local conversation lifecycle with start, end, client, and aggregate counters |
| `InvocationEvent` | One MCP tool call with timing, status, and token cost |
| `RetrievalOutcome` | One retrieval-bearing result set tied to an invocation |
| `DailyUsageRollup` | Pre-aggregated daily stats for cheap dashboard reporting |

Minimal fields should be stable and versioned. The event log must be append-first, not update-heavy.

---

## 9. Delivery Phases

### Phase 1 - Capture What Happened

Ship the session lifecycle, client attribution, invocation events, and retention policy.

Success for Phase 1:

- Elefante can answer when it was called, by which client, and which tools ran.

### Phase 2 - Measure Whether It Helped

Ship usefulness proxies and unanswered-query tracking.

Success for Phase 2:

- Elefante can distinguish frequent retrieval from useful retrieval.

### Phase 3 - Surface It Cleanly

Expose the data through one or more of:

- dashboard snapshot fields
- a dedicated developer report
- a targeted MCP inspection tool if the team decides the surface is worth it

Success for Phase 3:

- a developer can audit one session or one week without reading raw logs.

---

## 10. Acceptance Criteria

This feature is only done when all of the following are true:

1. A developer can answer: "When was Elefante invoked in session X?" from maintained data, not guesswork.
2. A developer can answer: "Which IDE called Elefante most this week?"
3. A developer can answer: "How many retrievals led to same-session reuse?"
4. A developer can answer: "Which queries returned nothing this week?"
5. Raw prompt text is **not** stored by default.
6. No remote telemetry path exists.
7. Retention pruning is automatic and regression-tested.
8. Privacy boundaries are documented in the user-facing and developer-facing docs when the feature ships.

---

## 11. Requested Development Work

This is the concrete request to the Elefante dev team.

1. Review this PRD against `spec-vision.md` Law 4 and confirm the feature improves signal quality rather than adding vanity analytics.
2. Choose and document the local event store.
3. Implement Phase 1 first: session IDs, client attribution, per-call event logging, retention.
4. Extend the already planned retrieval-effectiveness work instead of building a second usefulness system.
5. Add regression coverage for privacy rules, retention pruning, and client attribution fallbacks.
6. Add one maintained inspection path so developers can use the data without reading raw files.

---

## 12. Why This Belongs In Elefante

Elefante claims to maximize signal per token.

That claim becomes stronger, not weaker, when the system can answer:

- which retrievals helped
- which retrievals wasted context
- which clients or workflows produce useful reuse
- which sessions are blind spots

If Elefante cannot measure those things locally and privately, the product remains partially blind to its own value.

---

## 13. Related Bugs And Specs

- Closes at the data layer: **GAP-025** — multi-instance write origin tracking — post-mortem in [`../debug/ops-memory-compendium.md`](../debug/ops-memory-compendium.md) Issue #15.
- Prerequisite (transport + schema): [`spec-ide-integration-surface.md`](spec-ide-integration-surface.md) § 4.2 singleton daemon, § 7.1 daemon ownership, § 9 Source tuple. Session Intelligence cannot ship § 6.1–§ 6.6 until Phase A of the IDE-integration surface spec is live.
- Paired product work: [`spec-retrieval-effectiveness.md`](spec-retrieval-effectiveness.md) — the per-retrieval reuse signal this spec cites in § 6.4 is owned there; Session Intelligence consumes the per-memory effectiveness signal rather than duplicating it.
- Governed by: [`spec-vision.md`](spec-vision.md) Four Laws (privacy contract in § 4 is a concrete expression of Law 2 Compliance and Law 4 Signal Injection — the point is to measure, not surveil).
- Intake: [`spec-vision.md`](spec-vision.md) ideas backlog. Session Intelligence was accepted into active planning after it cleared the Non-Goals filter in [`spec-vision.md`](spec-vision.md).