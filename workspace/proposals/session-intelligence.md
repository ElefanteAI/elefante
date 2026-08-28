# PRD: Session Intelligence - Privacy-Respecting Invocation Telemetry

> **Status**: IMPLEMENTED IN DEVELOPMENT (opt-in, unreleased) — the local
> metadata-only ledger, provider-usage ingress, rate cards, Signal Cards,
> aggregate enterprise hypotheses, data controls, and dashboard surface are
> guarded. No release, provider integration, or customer usage claim follows.
>
> **Owner**: Elefante dev team
>
> **Date**: 2026-04-17
>
> **Scope**: Local-first session and invocation telemetry so Elefante can answer
> when it was called, by which client, what happened, and what the observed
> token/cost result means in the user's own goals and constraints. Helpfulness
> remains unknown unless controlled Task Intelligence evidence supplies an
> outcome. Raw prompts, responses, transcripts, and hidden reasoning are not
> stored by default.

---

## Question This Spec Answers

How can Elefante locally turn observable AI usage, durable user context, and
valid outcome evidence into useful token-financial signals without surveillance,
false precision, or a second usefulness system?

## Development implementation

- `src/session_intelligence/ledger.py` owns the consent-gated SQLite schema,
  actual-versus-estimated provenance, retention, export/delete controls,
  versioned rate cards, Signal Cards, and aggregate training hypotheses.
- `POST /events/usage` on the loopback daemon accepts one bounded metadata-only
  event. It refuses to create a ledger before explicit consent.
- `scripts/pipeline/session_intelligence.py` is the user/operator boundary for
  consent, provider event and outcome ingest, rate cards, Signal Cards,
  enterprise reports, export, prune, snapshot, and exact-confirmation deletion.
- The dashboard reads `session_intelligence_snapshot.json`; it never opens the
  ledger. Missing snapshots render the feature as off, not as zero usage.
- Raw prompts, transcripts, responses, arbitrary tool arguments, hidden
  reasoning, employee ranking, and sensitive-trait inference are rejected or
  absent by schema.

The implementation is a development product surface, not a published v2.12.3
capability. Provider hosts must explicitly post their actual usage metadata,
and cost remains `UNKNOWN` without a matching versioned local rate card.

---

## 1. Problem Statement

Elefante already knows memories, scores, co-activation history, and some per-call
heuristic token estimates.

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
| Client attribution | Installed bridges provide a normalized host id; Session Intelligence events persist the bounded client name when explicitly enabled | Hosts that do not emit an event remain unobserved |
| Per-call token stats | Legacy `SessionTokenLedger` estimates remain ephemeral; the new opt-in ledger persists typed actual or estimated usage without mixing them | Estimates are never relabelled provider-actual |
| Provider usage and money | The loopback usage endpoint and versioned rate-card authority are implemented in development | Exact money remains unknown unless the host supplies provider-actual usage and the exact rate card exists |
| Retrieval history | Last 20 retrieved memory IDs persisted for 7 days | Too thin to reconstruct real invocation history |
| Co-activation | Persisted in Kuzu and already useful as a reuse proxy | Does not answer query-level provenance |
| Retrieval effectiveness | Evaluation infrastructure exists in [`retrieval-effectiveness.md`](retrieval-effectiveness.md) | Product lift remains unproven; per-retrieval outcomes are not persisted |
| Privacy | No Elefante product telemetry; Session Intelligence is local, metadata-only, consent-gated, bounded, and deletable | A configured host still controls whether it submits an eligible event; no remote telemetry exists |

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

### 3.1 Curated product thesis: a local token-financial companion

Elefante should help a user understand the economics of working with AI in the
user's own context. It can combine what the user explicitly wants preserved
(goals, quality floors, privacy constraints, budgets, preferred workflows, and
decisions) with locally observable usage events and valid outcome evidence.

The product output is not a token counter. It is a decision signal such as:

- the same accepted result used fewer observed tokens;
- a more expensive path produced enough additional accepted value to justify
  the spend;
- repeated retries consumed cost without improving the outcome;
- a recurring workflow pattern suggests a training or adoption intervention;
- the available usage, rate, or outcome evidence is insufficient, so cost or
  value remains `unknown`.

This is an **early product and commercial hypothesis**, not yet a complete
business model. The product-value hypothesis is local personal intelligence.
The commercial hypothesis is paid organizational deployment/support plus
optional adoption or training services based on a customer-controlled,
purpose-specific aggregate signal bundle; it does not change the current free
personal-project message. Buyer, pricing, willingness to pay, support cost, and
legal operating model remain unvalidated.

### 3.2 Three planes, one answer

Do not build a second semantic-memory engine or usefulness score, and do not
create an invocation-event store outside Session Intelligence.

| Plane | Owns | Canonical surface | Must not claim |
| --- | --- | --- | --- |
| Durable meaning | User goals, preferences, constraints, budgets, decisions, and verified lessons | Governed semantic Memory plus Kuzu relationships | That an event is a durable user preference |
| Usage facts | Host, model/provider when observable, timestamps, calls, retries, latency, actual or estimated tokens, and versioned rate context | Session Intelligence local event store | That activity or retrieval volume proves value |
| Outcome evidence | Accepted result, explicit feedback, task criterion, control/treatment evidence, and causal status | Existing Task Intelligence ledger and evaluator | That correlation, reuse, or agent acknowledgement proves lift |

A token-financial answer may join all three planes, but each field keeps its
source, evidence class, time window, and uncertainty. Missing data stays
`unknown`; the system never fills a gap with an estimate presented as fact.

### 3.3 Evidence classes and metric discipline

Every reported number must carry one evidence class:

1. **Provider actual** — usage fields returned by the model provider or host.
2. **Local measured** — exact bytes, calls, latency, or other runtime facts
   observed by Elefante.
3. **Local estimated** — Elefante's heuristic token estimate, labeled as such.
4. **User asserted** — an explicit goal, rating, acceptance, or business value.
5. **Causally evaluated** — a valid frozen comparison or repeated ablation under
   the Task Intelligence contract.

The metric vocabulary is deliberately non-interchangeable:

- `signal_ratio` is the payload share of one Elefante response and is only a
  transport-efficiency diagnostic;
- accepted task value per total token is the Task Intelligence outcome metric;
- token-financial intelligence is the user-facing interpretation that joins
  usage, money when knowable, outcome, and durable user context.

Provenance is typed as well. Memory-source provenance identifies who or what
wrote durable knowledge; usage provenance identifies the host/provider and
measurement source for an event; evidence provenance identifies the task and
comparison behind an outcome; build provenance identifies the executing
artifact. One provenance class must never be presented as proof of another.

Core derived metrics may include accepted outcomes per million total tokens,
cost per accepted outcome, retry/correction spend, budget adherence, and change
in accepted value at a comparable cost. They are calculated only across
comparable tasks and only when their required inputs exist. A failed outcome
retains its full observed cost and contributes zero accepted value.

Exact money requires provider-actual usage plus a versioned, dated rate card
for the correct model, currency, and cached/uncached/output categories. Without
both, dollar cost is `unknown`. Cached input is a subset of input and is never
counted twice.

### 3.4 Signal output contract

The smallest useful output is a **signal card**, not raw telemetry. It contains:

- scope and time window;
- observed baseline and candidate;
- financial effect, with actual/estimated status;
- quality or accepted-outcome effect;
- context explaining why this matters to this user;
- evidence class, provenance, and material unknowns;
- one reversible recommendation or training opportunity.

The Recall response reductions recorded in
[`retrieval-effectiveness.md` §15.1](retrieval-effectiveness.md#151-ordered-development-packages)
are the motivating example: a no-match response, multilingual context response,
and pathological escaped response became smaller while the positive and
negative quality controls remained green. Those measurements remain canonical
in that evidence section. They are not average customer savings, provider
billing, a universal target, or the permanent metric schema.

### 3.5 Anti-overfit and anti-surveillance rules

- Optimize accepted value per total token, never token reduction alone.
- Compare like with like: task, source state, model, reasoning, tools, success
  criteria, timeout, and approval policy must remain fixed or the comparison is
  labeled observational.
- Keep actual provider usage separate from Elefante estimates.
- Preserve abstention as a successful low-cost outcome when no memory applies.
- Do not infer individual competence, productivity, intent, health, or other
  sensitive traits from token behavior.
- Do not rank employees or use these signals for employment, compensation,
  discipline, credit, insurance, or similarly consequential decisions.
- Training suggestions are hypotheses for the user or team to accept, reject,
  or correct; they are not automated judgments.

### 3.6 User grooming loop

The companion improves through explicit curation, not silent profiling:

```text
Observe local event → derive bounded Signal Card → user accepts/corrects/rejects
→ search existing Memory → add or amend one durable insight when directed
→ use that governed context in a later eligible question
```

- Raw usage events never become semantic memories automatically.
- An accepted pattern stores the smallest durable meaning, its source window,
  evidence class, and material uncertainty—not the underlying transcript.
- A correction amends or supersedes the equivalent memory instead of creating a
  competing profile fact.
- A rejected suggestion remains feedback about that signal; it is not retained
  as a belief about the user.
- The user can inspect, correct, archive, export, or delete the durable result.
- Future retrieval must still pass relevance, privacy, scope, conflict, and
  current-source gates; user grooming does not authorize unconditional injection.

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
- `estimated_output_tokens`
- `estimated_overhead_tokens`
- `estimated_signal_ratio`
- a keyed, install-local `query_fingerprint` when repeated-query detection is
  necessary; never a plain low-entropy hash
- provider/model identifiers and provider-actual usage only when the host
  supplies them and the user has enabled that purpose
- a versioned rate-card identifier and calculated cost only when their source,
  currency, and effective date are known

Disallowed by default:

- full raw prompts
- full tool arguments containing arbitrary user content
- copied chat transcripts
- full memory content duplicated into telemetry
- model hidden reasoning or chain-of-thought
- inferred employee-performance or sensitive-trait profiles
- data copied to Elefante, an employer, or a training provider without a
  separate explicit export action and disclosed purpose

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

“Always local” is an authority and data-location promise, not infinite
retention. Detailed events expire under the schedule above. Only explicitly
curated, reusable meaning may persist as governed Memory, with its own lifecycle
and user controls.

### 4.5 Legal and consent launch gate

This section is a product-design gate, not a jurisdiction-specific legal
conclusion. Local storage lowers transfer and breach exposure; it does not make
personal information ownerless or exempt every collection and use.

Before a pilot persists real user or employee usage, the operator must:

1. identify each purpose and data field before collection;
2. document the applicable legal authority and obtain meaningful, granular
   consent where consent is the authority;
3. prohibit secondary training, benchmarking, sales, or company disclosure
   without a compatible purpose or fresh authority;
4. provide inspect, correct, export, reset, and delete controls;
5. enforce purpose-bound retention and secure deletion;
6. apply encryption, least privilege, auditability, and backup/restore controls
   appropriate to the sensitivity;
7. define whether Elefante, the customer, and any training provider act as
   controller, processor, or another applicable role; and
8. complete jurisdiction-specific privacy and employment review before any
   enterprise or workforce pilot; and
9. ingest provider usage only through documented, contract-permitted interfaces;
   never scrape hidden model internals or imply that a local measurement transfers
   ownership of provider or user data.

The Canadian baseline is the Office of the Privacy Commissioner's
[PIPEDA fair information principles](https://www.priv.gc.ca/en/privacy-topics/privacy-laws-in-canada/the-personal-information-protection-and-electronic-documents-act-pipeda/p_principle/)
and its
[privacy principles for generative AI](https://www.priv.gc.ca/en/privacy-topics/technology/artificial-intelligence/gd_principles_ai),
which emphasize identified purposes, legal authority or meaningful consent,
necessity, proportionality, transparency, limited use/retention, safeguards,
and access/correction. For EU users, the
[GDPR](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679)
and the EDPB's
[data-protection-by-design guidance](https://www.edpb.europa.eu/documents/guideline/guidelines-42019-on-article-25-data-protection-by-design-and-by-default_en)
require a valid basis, purpose limitation, minimization, transparency, and
privacy-protective defaults. Applicable law and provider contracts still need
qualified review for each launch market and data flow.

---

## 5. Product Decision

This feature should ship as **Session Intelligence**, a local event layer
dedicated to session and invocation analytics. Semantic Memory remains the
authority for durable user meaning, and Task Intelligence remains the authority
for outcome evidence.

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
- `estimated_input_tokens`
- `estimated_output_tokens`
- `estimated_overhead_tokens`
- `estimated_signal_ratio`

When supplied by the host under an enabled purpose, the event may also record:

- `provider`
- `model`
- `provider_input_tokens`
- `provider_cached_input_tokens`
- `provider_output_tokens`
- `usage_source`
- `rate_card_id`
- `currency`
- `calculated_cost`

For retrieval-bearing calls, also record:

- `query_fingerprint`
- `mode`
- `returned_memory_ids`
- `top_score`

`query_hash` is retired from the proposed contract: a plain hash can be guessed
for low-entropy prompts. Repeated-query analysis uses the keyed local
fingerprint or omits the field.

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
- provider-actual usage versus local estimates
- calculated cost only when usage and rate-card provenance are complete
- accepted outcome or `unknown`, never inferred from activity

### 6.6 Weekly and Daily Aggregate Stats

Elefante must be able to answer, at minimum:

- which client called it most this week
- tool-call counts by client
- average signal ratio by tool
- unanswered-query totals by day
- dead-weight memories surfaced this week
- retry and correction spend
- accepted outcomes per million comparable total tokens, when valid outcome
  evidence exists
- cost per accepted outcome, when provider usage and rate provenance exist
- user-approved training opportunities derived from repeated patterns and
  presented with their evidence and uncertainty

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
- Not employee productivity monitoring or consequential people decisions.
- Not a provider billing authority.
- Not raw prompt, response, or hidden-reasoning capture.
- Not an unconsented data-export or model-training pipeline.
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
| `RateCardSnapshot` | Optional dated pricing inputs with provider, model, currency, and source |

Minimal fields should be stable and versioned. The event log must be append-first, not update-heavy.
`SignalCard` is a derived, explainable view across these records and governed
Memory; it must not become another source-of-truth ledger or persisted user
profile.

---

## 9. Delivery Phases

### Phase 0 - Freeze The Purpose And Measurement Contract

Before implementation, freeze:

- the data inventory and evidence classes;
- user/enterprise purposes, consent or other legal authority, and role mapping;
- actual-versus-estimated usage semantics;
- retention, access, correction, export, reset, and deletion behavior;
- the Signal Card schema and anti-overfit controls; and
- synthetic fixtures for every metric and privacy regression.

Success for Phase 0:

- every stored field has a purpose, provenance, retention rule, and deletion
  path; legal/privacy review and user acceptance criteria are recorded before
  real telemetry is persisted.

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

- a user or developer can audit one session or one week without reading raw
  logs.

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
9. Every number distinguishes provider actual, local measured, local estimated,
   user asserted, or causally evaluated evidence.
10. Dollar cost is `unknown` unless provider usage and a current sourced rate
    card are both present.
11. Token savings cannot pass acceptance when accepted value regresses.
12. A user can inspect, correct, export, reset, and delete the local profile and
    event history within the documented limits.
13. Enterprise reporting is opt-in, purpose-bound, aggregate-first, and cannot
    rank individual employees.
14. The motivating Recall measurements remain a fixture and evidence example,
    not a customer claim or an optimized-to target.

---

## 11. Requested Development Work

This is the concrete request to the Elefante dev team.

1. Review this PRD against [`docs/explanation/vision.md`](../../docs/explanation/vision.md) and confirm the feature improves task outcomes rather than adding vanity analytics.
2. Complete and accept Phase 0 before persisting real usage.
3. Choose and document the local event store.
4. Implement Phase 1: session IDs, client attribution, per-call event logging,
   retention, and user controls.
5. Extend the already planned retrieval-effectiveness work instead of building a second usefulness system.
6. Add regression coverage for privacy, consent state, evidence labels,
   retention, deletion, and client attribution fallbacks.
7. Add one maintained inspection path so users and developers can understand
   the data without reading raw files.

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

The longer-term commercial opportunity is not to sell a user's raw interaction
history. It is to help the user cultivate a local AI companion that understands
their goals and usage economics, then—only when the user or customer chooses—to
turn a minimal aggregate signal bundle into targeted adoption or training. That
commercial hypothesis must earn validation without weakening the local trust
boundary.

---

## 13. Related Bugs And Specs

- Closes at the data layer: **GAP-025** — [`../postmortems/memory.md`](../postmortems/memory.md#issue-15).
- Prerequisite: [`ide-integration-surface.md`](ide-integration-surface.md) daemon ownership and Source tuple.
- Paired product work: [`retrieval-effectiveness.md`](retrieval-effectiveness.md); Session Intelligence consumes that signal rather than duplicating it.
- Governed by: [`../../docs/explanation/vision.md`](../../docs/explanation/vision.md) Four Laws and Non-Goals.
