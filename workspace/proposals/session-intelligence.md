# PRD: Session Intelligence - Privacy-Respecting Invocation Telemetry

> **Status**: DRAFT — reconciled with v2.12.2; no implementation or release commitment
>
> **Owner**: Elefante dev team
>
> **Date**: 2026-04-17
>
> **Scope**: Local-first session and invocation telemetry so Elefante can answer
> when it was called, by which client, and what happened. Helpfulness remains
> unknown unless a separate controlled Task Intelligence evaluation supplies
> outcome evidence. Raw chat transcripts are not stored by default.

---

## Question This Spec Answers

How can Elefante tell, per session and per client, when it was invoked and how
it was used without violating user privacy, while linking to controlled outcome
evidence when that evidence exists?

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
| Transport/write provenance | The daemon or stdio process records bounded tool, instance, session, cwd, and transport context on new writes | This is write provenance, not an invocation-event or conversation lifecycle |
| Client attribution | Installed bridges provide a normalized host id; HTTP can also use client metadata | No maintained per-call event store or aggregate usage report exists |
| Per-call token stats | Computed by `SessionTokenLedger` and returned as `TOKEN_STATS` | Not persisted; lost on restart |
| Retrieval history | Last 20 retrieved memory IDs persisted for 7 days | Too thin to reconstruct real invocation history |
| Co-activation | Persisted in Kuzu and already useful as a reuse proxy | Does not answer query-level provenance |
| Retrieval effectiveness | Evaluation infrastructure exists in [`retrieval-effectiveness.md`](retrieval-effectiveness.md) | Product lift remains unproven; per-retrieval outcomes are not persisted |
| Privacy | No Elefante product telemetry; the optional distiller has a secrets scrubber | Direct memory writes are not a general-purpose secret scrubber; invocation metadata is not persisted |

This feature request exists because the current system cannot answer session-level product questions with confidence.

---

## 3. Core Requirement

Elefante must gain a privacy-respecting session-intelligence layer that can answer, locally and truthfully:

1. **Who called Elefante** - client or IDE name when available.
2. **When Elefante was called** - session lifecycle plus per-tool invocation timestamps.
3. **What happened** - tool name, result shape, latency, token cost, retrieval count.
4. **Whether a valid evaluation linked it to an outcome** - otherwise usefulness remains unknown.
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

It should not be forced into semantic memory records.

It should not overload the Kuzu graph with high-volume event noise.

### Preferred Storage Surface

Use a dedicated local telemetry store for event-style data.

Preferred implementation:

- `~/.elefante/data/session_intelligence.db`

Reason:

- time-window aggregates are first-class
- retention pruning is cheap
- daily and weekly rollups are easy
- session events are not semantic memory and should not pollute the configured
  vector store

Fallback if the team rejects a dedicated store:

- append-only JSONL with a maintained rollup pipeline

Hard rule:

Do **not** store this in a way that makes weekly statistics or retention enforcement painful.

---

## 6. What Must Exist

### 6.1 Canonical Session Lifecycle

Transport session ids and memory-level optional `session_id` fields are not a
complete conversation lifecycle. Session Intelligence needs a bounded local
record that is explicit about what the runtime can and cannot observe.

The MCP server should create:

- a `session_id` when the conversation or transport lifecycle begins
- an `invocation_id` for every tool call

If a client supplies its own session identifier, Elefante may record it as `client_session_id`, but Elefante still owns the canonical local session record.

### 6.2 Client Attribution

Reuse the normalized host provenance already captured by the daemon/bridge;
do not create a second naming system.

Minimum field:

- `client_name` = canonical id from `scripts/setup/host_selection.py`, or `unknown`

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

### 6.4 Retrieval diagnostics and outcome evidence

Invocation telemetry must not convert exposure into usefulness. Retrieval,
access-count increase, co-activation, repetition, or agent acknowledgement are
diagnostic observations only; none proves that a memory improved the task.

Operational diagnostics may include:

- unanswered query count;
- result count and selected/delivered memory IDs;
- same-session reuse or co-activation;
- explicit user or agent feedback, labeled as feedback rather than fact.

A usefulness claim requires an opted-in task trace with observable success
criteria, selected and delivered memory IDs, and a valid control/treatment or
repeated ablation result. Without that evidence, the stored outcome is
`unknown`. This proposal must reuse the Task Intelligence evaluation contract
rather than inventing a weaker telemetry-derived score.

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

### 6.7 Released Source provenance prerequisite

The daemon now captures a bounded Source tuple for new writes. Legacy
provenance apply remains an explicitly authorized support operation, and the
session-metrics pipeline remains unbuilt (see
[`../postmortems/memory.md`](../postmortems/memory.md#issue-15)).

**Released Source tuple, captured with safe fallbacks on new memory writes:**

| Field | Purpose | Source |
| ----- | ------- | ------ |
| `source.tool` | Bounded host id or `unknown-*` fallback | Bridge environment or MCP client/header context |
| `source.instance_id` | Bounded connection/process identity or fallback | Bridge environment, MCP session id, or server-process id |
| `source.session_id` | Transport session identity; not yet a conversation lifecycle | MCP session id, or `stdio` fallback |
| `source.cwd` | Bounded working-directory context when supplied | Bridge environment or request header |
| `WRITTEN_BY.observed_at` | Write-link instant, independent of memory creation time | Daemon clock |

**Graph shape:** a memory's graph Entity is linked by `WRITTEN_BY` to a Source
node. Source nodes are deduplicated on `(tool, instance_id, session_id)`—one
Source node per observed connection identity, not one per write.

**Writer contract:** the released customer daemon is the durable-store writer.
It composes Source context from transport-owned headers/environment plus `cwd`
and stamps new memory writes. Direct source-mode stdio remains a developer
compatibility path and records its own process identity.

**Boundary:** Source provenance answers who wrote a memory; it does not prove
which retrieval helped a later task. Session Intelligence may join to this
identity, but it must not reinterpret write provenance as outcome evidence.

**Current proof boundary:** new writes receive fallbacks when a host does not
provide identity. Therefore `unknown-*` is valid provenance, not proof of a
known client. Host-specific attribution remains only as strong as the bridge or
handshake evidence.

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

### Phase 2 - Link Diagnostics to Outcome Evidence

Ship unanswered-query tracking and connect eligible invocations to the
controlled Task Intelligence outcome contract. Keep reuse and access signals
labeled as diagnostics, not usefulness proxies.

Success for Phase 2:

- Elefante can distinguish frequent retrieval from retrieval with valid outcome
  evidence, and reports all other usefulness as `unknown`.

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

1. Review this PRD against [`docs/explanation/vision.md`](../../docs/explanation/vision.md) and confirm the feature improves task outcomes rather than adding vanity analytics.
2. Choose and document the local event store.
3. Implement Phase 1 first: session IDs, client attribution, per-call event logging, retention.
4. Extend the already planned retrieval-effectiveness work instead of building a second usefulness system.
5. Add regression coverage for privacy rules, retention pruning, and client attribution fallbacks.
6. Add one maintained inspection path so developers can use the data without reading raw files.

---

## 12. Why This Belongs In Elefante

Elefante claims to maximize signal per token.

That claim becomes testable only when the system can distinguish diagnostics
from controlled outcome evidence. It should eventually answer:

- which retrievals have evidence of improving an outcome
- which retrievals added context without improving the measured outcome
- which clients or workflows show reuse, and which show measured outcome lift
- which sessions are blind spots

Until Elefante can measure those things locally and privately, product value
remains unproven rather than inferred from activity.

---

## 13. Related Bugs And Specs

- Closes at the data layer: **GAP-025** — [`../postmortems/memory.md`](../postmortems/memory.md#issue-15).
- Prerequisite: [`ide-integration-surface.md`](ide-integration-surface.md) daemon ownership and Source tuple.
- Paired product work: [`retrieval-effectiveness.md`](retrieval-effectiveness.md); Session Intelligence consumes that signal rather than duplicating it.
- Governed by: [`../../docs/explanation/vision.md`](../../docs/explanation/vision.md) Four Laws and Non-Goals.
