# PRD: Session Intelligence - Developer Value, Workflow, and Token Finance

> **Status**: DEVELOPMENT VERTICAL SLICE IMPLEMENTED — DVC-0 was frozen under
> explicit owner authorization for opt-in local development evidence; the
> fresh-store DVC-1 foundation, DVC-2 evidence path, bounded DVC-3 join, and the
> Value Baseline/task-pair portion of DVC-4 are implemented. Schema upgrades,
> natural R5 evidence, installed capability, release, and public claims remain
> open.
>
> **Owner**: Elefante dev team
>
> **Date**: 2026-04-17
>
> **Last updated**: 2026-08-27
>
> **Scope**: Local-first session and invocation telemetry so Elefante can answer
> when it was called, by which client, what happened, and what the observed
> workflow-time, token, and cost result means against the user's pre-registered
> value and quality contract. Helpfulness remains unknown unless controlled Task
> Intelligence evidence supplies an outcome. Raw prompts, responses,
> transcripts, hidden reasoning, and keystroke activity are not stored by
> default.

---

## Question This Spec Answers

How can Elefante locally turn observable AI usage, durable user context, and
valid outcome evidence into proof that a developer delivered more accepted
value in the same total workflow time, or the same accepted value in less time,
without surveillance, false precision, or a second usefulness system?

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
- Did Elefante reduce the complete path to an accepted result, or only make one
  response faster?
- What did the user define as valuable before the result was visible?

That is a real product gap.

It matters because Elefante's core thesis is not raw storage. It is signal quality. If Elefante cannot measure invocation context and downstream usefulness, it cannot prove whether a retrieval increased useful signal or just created noise.

---

## 2. Honest Assessment: Current Elefante Reality

The released and installed customer product has partial building blocks, but no
Session Intelligence capability. This development branch now contains the
explicit opt-in local value-evidence slice described in §11.1; it is not wired
into normal customer-host operation.

| Surface | Current State | Gap |
| ------- | ------------- | --- |
| Transport/write provenance | The daemon or stdio process records bounded tool, instance, session, cwd, and transport context on new writes | This is write provenance, not an invocation-event or conversation lifecycle |
| Client attribution | Installed bridges provide a normalized host id; HTTP can also use client metadata. The development slice can store bounded local client metadata when explicitly enabled | No normal customer-host producer or aggregate usage report exists |
| Per-call token stats | Computed by `SessionTokenLedger` and returned as `TOKEN_STATS` | Not persisted; lost on restart |
| Provider usage and money | No general provider-usage ingest or versioned rate-card contract exists | Exact model tokens and dollar cost are normally unknown |
| Retrieval history | Last 20 retrieved memory IDs persisted for 7 days | Too thin to reconstruct real invocation history |
| Co-activation | Persisted in Kuzu and already useful as a reuse proxy | Does not answer query-level provenance |
| Retrieval effectiveness | The maintained Codex evaluator can emit metadata-only attempt evidence, and the existing summary CLI can render a read-only Value Baseline or matched-task Signal Card | No automatic normal-host workflow producer, naturally eligible R5 pair, or representative product lift exists |
| Privacy | No Elefante product telemetry; the development store is explicit opt-in, local, metadata-only, inspectable, and deletable | Direct memory writes are not a general-purpose secret scrubber; the development slice is not installed or customer-enabled |

The remaining feature work exists because the released product still cannot
answer session-level product questions with confidence, and the development
slice has not yet earned a field or product claim.

---

## 3. Core Requirement

Elefante must gain a privacy-respecting session-intelligence layer that can answer, locally and truthfully:

1. **Who called Elefante** - client or IDE name when available.
2. **When Elefante was called** - session lifecycle plus per-tool invocation timestamps.
3. **What happened** - tool name, result shape, latency, token cost, retrieval count.
4. **Whether a valid evaluation linked it to an outcome** - otherwise usefulness remains unknown.
5. **What the accepted outcome was worth** - using a pre-registered, inspectable
   task-value contract rather than a model-invented score.
6. **How long the full workflow took** - distinct from one model run or one MCP
   invocation.
7. **What failed to help** - unanswered queries, dead-weight retrievals, retries,
   corrections, and rework.

This must remain local-first and privacy-bounded.

### 3.1 Curated product thesis: a local token-financial companion

Elefante should help a user understand the economics of working with AI in the
user's own context. It can combine what the user explicitly wants preserved
(goals, quality floors, privacy constraints, budgets, preferred workflows, and
decisions) with locally observable usage events and valid outcome evidence.

The product output is not a token counter. It is a decision signal such as:

- the same accepted result used fewer observed tokens;
- the same accepted result took less total workflow time;
- a better accepted result was delivered without taking more total workflow
  time;
- a more expensive path produced enough additional accepted value to justify
  the spend, but is labeled a quality-first trade rather than productivity when
  it also took more total workflow time;
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
| Usage facts | Host, model/provider when observable, timestamps, calls, retries, corrections, invocation latency, workflow elapsed time, optional active-developer time, actual or estimated tokens, and versioned rate context | Session Intelligence local event store | That activity, retrieval volume, or a fast response proves developer value |
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
- accepted task value per total workflow time is the developer-productivity
  outcome view;
- accepted task value per total token is the Task Intelligence resource-
  efficiency view;
- token-financial intelligence is the user-facing interpretation that joins
  usage, money when knowable, outcome, and durable user context.

Provenance is typed as well. Memory-source provenance identifies who or what
wrote durable knowledge; usage provenance identifies the host/provider and
measurement source for an event; evidence provenance identifies the task and
comparison behind an outcome; build provenance identifies the executing
artifact. One provenance class must never be presented as proof of another.

Core derived metrics may include accepted value per workflow hour, accepted
outcomes per million total tokens, cost per accepted outcome, retry/correction
spend, budget adherence, and change in accepted value at comparable time or
cost. They are calculated only across comparable tasks and only when their
required inputs exist. A failed outcome retains its full observed time and cost
and contributes zero accepted value.

Exact money requires provider-actual usage plus a versioned, dated rate card
for the correct model, currency, and cached/uncached/output categories. Without
both, dollar cost is `unknown`. Cached input is a subset of input and is never
counted twice.

### 3.4 Developer value and workflow-time contract

Elefante's strict developer-productivity claim is:

> With trust and quality floors preserved, treatment delivers more accepted
> value in the same or less total workflow time, or the same accepted value in
> less total workflow time.

That statement is narrower than "the answer was faster" and more useful than a
generic quality score. It is evaluated only on a frozen matched task. It never
compares unrelated projects, developers, or task difficulty.

#### Pre-registered task-value contract

Before control or treatment starts, Task Intelligence freezes and hashes:

For a naturally arising task, the auditable order is deliberate: observe the
exact user task, freeze this contract, then start either arm. A contract dated
before the task existed would be a benchmark-authored hypothesis rather than
evidence that the task arose independently.

| Field | Contract |
| --- | --- |
| Goal and task class | The exact outcome the user needs and the comparable task class; neither can be rewritten after a result is seen. |
| Hard quality floors | Correctness, relevance, decision usefulness, hallucination control, privacy, authority, and any task-specific safety or maintainability requirement. |
| Value units | Observable, non-overlapping deliverables with a binary criterion and evidence source. A simple task defaults to one accepted unit. |
| Weights | Each unit defaults to weight `1`. A different business weight must be explicitly user-asserted before the run; Elefante does not infer monetary or strategic importance. |
| Time boundary | The exact start and stop event for the complete workflow, including retries, corrections, tools, waits, and rework until acceptance or stop. |
| Resource boundary | Provider-actual input and output usage for every observed attempt, plus any pre-registered time or token budget. |

If the task is not accepted or any hard quality floor fails, accepted workflow
value is zero. Otherwise:

```text
accepted_workflow_value = sum(passed value-unit weights)
accepted_value_per_workflow_hour = accepted_workflow_value / workflow_elapsed_hours
accepted_value_per_total_token = accepted_workflow_value / total_input_plus_output_tokens
```

The raw unit results, weights, clocks, and resource totals are always reported
beside the derived rates. There is no universal cross-task productivity score
and no hidden weighted composite.

#### Three clocks that must not be confused

| Clock | Meaning | Claim boundary |
| --- | --- | --- |
| `invocation_duration_ms` | One Elefante call or one model run | Diagnostic only; it cannot prove a faster developer workflow. |
| `workflow_elapsed_ms` | Frozen start to accepted result or terminal stop, including retries, corrections, tool work, waits, and rework | Required for the strict developer-productivity claim. |
| `active_developer_time_ms` | Consented host-actual or explicit user-timed human effort | Optional; otherwise `unknown`. Never infer it from keystrokes, inactivity, or surveillance proxies. |

A slower Recall call may still be a workflow improvement when it prevents a
retry, wrong implementation, source re-read, or correction. Conversely, a fast
Recall response that leads to more rework is not a win.

#### Matched-pair decision classes

Let `V` be accepted workflow value and `T` be total workflow elapsed time.

| Result | Required matched-pair evidence | What Elefante may say |
| --- | --- | --- |
| **Developer-value lift** | `V_treatment > V_control` and `T_treatment <= T_control` | More accepted value in the same or less time. |
| **Workflow-time lift** | `V_treatment == V_control` and `T_treatment < T_control` | The same accepted value in less time. |
| **Quality-first trade** | `V_treatment > V_control` and `T_treatment > T_control`, with explicit user acceptance | Better result for more time; useful when chosen, but not a productivity claim. |
| **Token-only lift** | Value and workflow time do not regress, and accepted value per total token improves | Better token economics; not automatically a time or product-value claim. |
| **No lift / harm** | Value regresses, a hard floor fails, or equal value takes more total workflow time | Reject the claim and retain the full observed spend. |
| **Inconclusive** | Value, clock, attribution, comparability, or usage evidence is missing | Report `unknown`; do not estimate the missing proof. |

Every result also reports accepted value per total token. A productivity result
with worse token economics is flagged as a resource regression and cannot become
Elefante's overall efficiency claim unless a pre-registered user budget and the
Task Intelligence decision rule explicitly permit the trade. Speed may be
sacrificed for a better result, but that result stays labeled **quality-first
trade** rather than being renamed productivity.

### 3.5 Signal output contract

The smallest useful output is a **signal card**, not raw telemetry. It contains:

- scope and time window;
- observed baseline and candidate;
- accepted value units and hard-floor result;
- workflow-time effect and decision class;
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

### 3.6 Anti-overfit and anti-surveillance rules

- Optimize accepted value per total token, never token reduction alone.
- Optimize the complete workflow, never one response's latency in isolation.
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

### 3.7 User grooming loop

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
- Outcome-backed recommendations may propose: capture a missing decision, amend
  stale context, merge a duplicate, narrow scope, mark a contradiction, preserve
  a repeatedly useful memory, or archive dead weight. No recommendation mutates
  semantic Memory until the user explicitly accepts it and the normal
  search-before-write contract passes.
- A later eligible task must re-evaluate the curated change. The act of accepting
  a recommendation is not itself proof that the memory improved work.

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
- `workflow_id` and the hashed task-value contract reference for an opted-in
  measured task
- `client_name`
- `tool_name`
- `timestamp`
- `duration_ms`
- `workflow_elapsed_ms`, terminal status, retries, corrections, and bounded
  rework-event counts
- `active_developer_time_ms` only from an explicitly enabled host-actual or
  user-timed source; otherwise it is absent, not inferred
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
dedicated to session and invocation analytics. The bounded development slice
implements that separation locally and only when explicitly enabled. Semantic
Memory remains the authority for durable user meaning, and Task Intelligence
remains the authority for outcome evidence.

It should not be forced into semantic memory records.

It should not overload the Kuzu graph with high-volume event noise.

### Preferred Storage Surface

Use a dedicated local telemetry store for event-style data.

The bounded development slice uses the preferred implementation:

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
- `workflow_id` when the call belongs to an opted-in measured task
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

### 6.4 Developer workflow measurement

An opted-in measured task needs one `WorkflowRun` that joins all attempts and
tool events from the frozen start boundary through acceptance or terminal stop.
It records:

- `workflow_id` and `task_value_contract_hash`;
- `condition` (`control` or `treatment`) and matched-comparison identity;
- monotonic `started_at`, `finished_at`, and `workflow_elapsed_ms`;
- terminal state (`accepted`, `failed`, `stopped`, or `unknown`);
- retry, correction, and rework counts using pre-registered event definitions;
- optional `active_developer_time_ms` and its measurement source;
- links to provider-usage events and the Task Intelligence outcome, not copied
  prompt, response, source-diff, or memory bodies.

The current Task Intelligence `duration_ms` measures a bounded evaluation run.
It may seed `workflow_elapsed_ms` only when the frozen workflow starts and ends
at those exact run boundaries. Otherwise it remains invocation/run latency and
the full workflow clock is `unknown`.

### 6.5 Retrieval diagnostics and outcome evidence

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

### 6.6 Session Summary Surface

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
- accepted value units and hard-quality-floor result when a valid Task
  Intelligence contract exists
- invocation latency, full workflow elapsed time, and active-developer time as
  separate fields with separate provenance
- the matched-pair decision class or `inconclusive`

### 6.7 Weekly and Daily Aggregate Stats

Elefante must be able to answer, at minimum:

- which client called it most this week
- tool-call counts by client
- average signal ratio by tool
- unanswered-query totals by day
- dead-weight memories surfaced this week
- retry and correction spend
- accepted workflow value per comparable workflow hour, when the task contracts
  and clocks are valid
- accepted outcomes per million comparable total tokens, when valid outcome
  evidence exists
- cost per accepted outcome, when provider usage and rate provenance exist
- user-approved training opportunities derived from repeated patterns and
  presented with their evidence and uncertainty

### 6.8 Released Source provenance prerequisite

The daemon now captures a bounded Source tuple for new writes. Legacy
provenance apply remains an explicitly authorized support operation. The
automatic normal-host session-metrics pipeline remains unbuilt; the bounded
opt-in development store in §11.1 is a separate producer path (see
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

| Entity | Purpose and authority | Default retention | User deletion path |
| ------ | ------- | --- | --- |
| `SessionRecord` | Session Intelligence owns one local conversation lifecycle with start, end, client, and aggregate counters | 90 days | Session delete or full Session Intelligence reset |
| `InvocationEvent` | Session Intelligence owns one MCP tool call with timing, status, and token/usage provenance | 30 days | Session delete or full reset; rollups are recomputed or invalidated |
| `WorkflowRun` | Session Intelligence owns one opted-in task boundary joining all attempts, tools, waits, corrections, terminal state, and elapsed time | 90 days | Workflow/session delete or full reset |
| `RetrievalOutcome` | Session Intelligence stores diagnostic delivery references tied to an invocation; Task Intelligence remains outcome authority | 30 days | Invocation/session delete or full reset |
| `DailyUsageRollup` | Session Intelligence owns pre-aggregated daily facts for cheap dashboard reporting | 365 days | Date-range delete or full reset |
| `RateCardSnapshot` | Session Intelligence owns optional dated pricing inputs with provider, model, currency, source, and effective date | 365 days when referenced | Delete with dependent financial rollups or full reset; never leave a cost without its rate provenance |
| `TaskValueContractRef` | Task Intelligence owns the hashed value contract and outcome; Session Intelligence stores only the foreign reference | Existing Task Intelligence 30-day ledger retention | Retract/delete through the Task Intelligence control and remove the Session reference |
| `SignalCard` | Derived explainable view across current authorized records; never another ledger or user profile | Not persisted by default | Disappears when source records are deleted or expire |

Minimal fields should be stable and versioned. The event log must be append-first, not update-heavy.
`SignalCard` is a derived, explainable view across these records and governed
Memory; it must not become another source-of-truth ledger or persisted user
profile.

---

## 9. Delivery Phases

### Phase 0 - Freeze The Purpose And Measurement Contract

Before entering any implementation slice or expanding its data purpose, freeze:

- the data inventory and evidence classes;
- the pre-registered task-value contract, hard quality floors, value-unit rules,
  and matched-pair decision classes;
- invocation, workflow-elapsed, and optional active-developer clocks with exact
  source and `unknown` behavior;
- user/enterprise purposes, consent or other legal authority, and role mapping;
- actual-versus-estimated usage semantics;
- retention, access, correction, export, reset, and deletion behavior;
- the Signal Card schema and anti-overfit controls; and
- synthetic fixtures for every metric and privacy regression.

Success for Phase 0:

- every stored field has a purpose, provenance, retention rule, and deletion
  path; legal/privacy review and user acceptance criteria are recorded before
  real telemetry is persisted; synthetic fixtures prove that value, time,
  token, and claim classifications fail closed.

### Phase 1 - Capture What Happened

Ship the session lifecycle, client attribution, invocation events, opted-in
workflow boundary, usage adapters, and retention policy.

Success for Phase 1:

- Elefante can answer when it was called, by which client, which tools ran, and
  the complete elapsed time for an explicitly bounded workflow without
  pretending that active developer time is known.

### Phase 2 - Link Diagnostics to Outcome Evidence

Ship unanswered-query tracking and connect eligible invocations to the
controlled Task Intelligence outcome contract. Keep reuse and access signals
labeled as diagnostics, not usefulness proxies.

Success for Phase 2:

- Elefante can distinguish frequent retrieval from retrieval with valid outcome
  evidence, computes accepted workflow value only from a frozen contract, and
  reports all other usefulness as `unknown`.

### Phase 3 - Surface It Cleanly

Expose the data through one or more of:

- dashboard snapshot fields
- a dedicated developer report
- a targeted MCP inspection tool if the team decides the surface is worth it

Success for Phase 3:

- a user or developer can audit one session or one week without reading raw
  logs, and can see why a result is developer-value lift, workflow-time lift,
  quality-first trade, token-only lift, no lift/harm, or inconclusive.

### Phase 4 - Earn A Product Claim

Run the existing Task Intelligence R5 path only on naturally arising eligible
tasks whose decision-changing memories predate the task. Hold the environment
constant, preserve all attempts and spend, and aggregate only comparable task
classes.

Success for Phase 4:

- a representative multi-task result meets the strict developer-productivity
  rule, has no trust or quality regression, preserves the token-financial gate,
  and passes a positive task-clustered lower bound. One task remains a local
  signal and cannot authorize a product or website claim.

### Milestone fact-review gate

Before Phase 0 acceptance and before entering each later phase, re-check the
facts that authorize the next decision:

1. canonical objective, task class, and user authority;
2. exact branch, source SHA, dirty paths, relevant test state, and released
   versus development identity;
3. data inventory, consent, retention, deletion, and rollback contracts;
4. task eligibility, pre-existing memory, preregistration, matched conditions,
   evidence provenance, and complete observed spend; and
5. public claim wording against the evidence actually available.

If any fact changed or cannot be proven, mark it `unknown`, revise the decision,
and stop the milestone rather than carrying the old conclusion forward.

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
15. A task-value contract freezes goal, hard quality floors, value units,
    weights, evidence sources, and workflow boundaries before either arm runs.
16. An unaccepted task or failed hard floor has zero accepted workflow value and
    retains all observed time and token cost.
17. Invocation duration, full workflow elapsed time, and optional active-
    developer time remain separate; missing active time is `unknown`.
18. Every comparison resolves to developer-value lift, workflow-time lift,
    quality-first trade, token-only lift, no lift/harm, or inconclusive using the
    §3.4 rules.
19. First use presents a truthful Value Baseline Card: what Elefante knows, what
    it does not know, the user's value contract, and whether evidence is pending,
    local-only, or representative. It never fabricates savings for an empty or
    unmeasured store.
20. Any incremental-learning recommendation cites its source events and outcome
    evidence, searches for an equivalent memory, and requires explicit user
    acceptance before semantic Memory changes.
21. A matched control/treatment trial changes only Elefante availability and the
    resulting Recall context; all attempts, retries, corrections, waits, and
    provider usage are counted.
22. One naturally arising task can produce only a local signal. A product or
    website claim requires representative independent task classes, a positive
    task-clustered lower bound, and no trust, quality, time, or token-financial
    regression hidden by aggregation.

### Definition of done

**Phase 0 acceptance contract:** this PRD, Task Intelligence, the living plan,
and GAP-055 must use the same value, clock, decision-class, privacy, and claim
vocabulary; documentation guards and synthetic fixtures must fail closed; and
every proposed field must have a purpose, provenance source, retention rule,
and deletion path. Phase 0 does not authorize general or background telemetry
persistence.

The owner explicitly authorized completion of one bounded value-evidence
vertical slice under DVC-0 on 2026-08-27; that decision is recorded in
[`PLANNING.md` §10](../PLANNING.md). It does not substitute for formal
legal/privacy review, enable background collection, authorize installation, or
approve a customer/public claim.

**The developer-value capability is done** only when Phases 1-4 and their user
stories pass in the installed customer artifact, the user can inspect and delete
the evidence, a normal host workflow produces the same report as the maintained
verifier, and representative evidence satisfies criterion 22. Passing unit
tests, storing events, or producing one favorable demo is not done.

---

## 11. Requested Development Work

This work extends the current three planes. It does not create a fourth value
engine, a second outcome ledger, or a second semantic profile.

| Task | Depends on | Deliverable | Done when |
| --- | --- | --- | --- |
| **DVC-0 — Contract and fixture freeze** | None | Final field inventory, task-value schema, clock definitions, decision table, Signal Card schema, consent/retention/deletion matrix, and synthetic examples | Phase 0 Definition of Done passes and the owner explicitly accepts the contract before real event writes. |
| **DVC-1 — Local event and control foundation** | DVC-0 | Versioned `session_intelligence.db`, migrations, append-first Session/Invocation/Workflow records, retention pruning, inspect/export/reset/delete controls | Fresh and upgraded disposable stores pass schema, retention, corruption, rollback, and no-network tests; no raw transcript or hidden reasoning is persisted. |
| **DVC-2 — Exact clocks and usage adapters** | DVC-1 | Monotonic invocation/workflow clocks, retry/correction/rework events, provider-actual usage producers, estimated fallback, and rate-card provenance | Every attempt reconciles from producer evidence rather than a trusted label; cached input is not double counted; active developer time is sourced or `unknown`; response latency cannot satisfy a workflow-time assertion. |
| **DVC-3 — Task Intelligence value join** | DVC-0, DVC-2 | Hashed value contract plus an opaque trace reference and application-level, provenance-verified join from WorkflowRun to the existing metadata-only Task Intelligence trace, delivered-memory IDs, declared-use events, and outcome | Control/treatment comparability, Recall supply, delivery/use attribution, quality floors, value units, elapsed time, tokens, and terminal status fail closed; no prompt, response, memory body, or source diff enters either ledger. |
| **DVC-4 — Explainable Signal Cards** | DVC-3 | Value Baseline, session, task-pair, and weekly cards plus one maintained live-trial producer/loader/CLI path | Every card reproduces verifier math from the same real record path, names its decision class, distinguishes local signal from representative evidence, and exposes no unsupported money or productivity claim. |
| **DVC-5 — Governed incremental learning** | DVC-3, DVC-4 | User accept/correct/reject flow for capture, amend, merge, narrow, conflict, preserve, and archive recommendations | Search-before-write, explicit consent, provenance, rollback, and later-task reevaluation are tested; raw events never auto-promote into semantic Memory. |
| **DVC-6 — Maintained inspection experience** | DVC-1, DVC-4, DVC-5 | One supported dashboard/report/MCP inspection path for evidence, controls, and learning decisions | A developer can understand one task and one week without raw logs, exercise access/export/delete, and reproduce the decision from source fields. |
| **DVC-7 — Natural field proof and claim gate** | DVC-1 through DVC-6 | R5 trials on independent naturally arising tasks and a claim-review artifact | The seven-part R5 guard plus workflow-value extension passes, representative evidence meets Phase 4, and public copy remains unchanged until separately authorized. |

### 11.1 Implemented value-evidence vertical slice — 2026-08-27

The first end-to-end development slice reuses the existing Task Intelligence
outcome authority and maintained evaluator/reporting path:

1. the evaluator emits a metadata-only Codex attempt event and accepts one
   complete provider usage event as `provider-actual`; absent, malformed, or
   multiple usage events become `unknown` rather than being summed;
2. an explicitly enabled local `session_intelligence.db` records a frozen value
   contract, separate monotonic invocation and workflow clocks, retry,
   correction and rework events, provider/local usage provenance, retention,
   and inspect/export/delete/reset controls;
3. WorkflowRun stores only an opaque Task Intelligence trace ID plus exact
   provenance digest. The derived join verifies delivery, declared use,
   quality floors, value units, terminal outcome, clocks, attempts, and tokens
   against the source ledger;
4. the existing summary CLI opens both ledgers read-only and renders either an
   honest empty-store Value Baseline Card or one non-persisted matched-pair
   Signal Card; and
5. the card classifies developer-value lift, workflow-time lift, quality-first
   trade, token-only lift, no lift/harm, or inconclusive while always blocking a
   representative or public claim from one task.

This closes one **development vertical slice**, not all of DVC-1 through DVC-4.
Schema upgrade coverage, normal-host automatic workflow boundaries, session and
weekly cards, installed-artifact controls, and the DVC-5 through DVC-7 learning,
inspection, field-proof, and claim gates remain open. The current synthetic
fixtures prove the protocol and fail-closed behavior only; no naturally arising
eligible R5 task was entered.

### 11.2 User stories

1. **US-DV-01 — Honest first-use value.** As a new developer, I can see one
   Value Baseline Card that states what Elefante knows, what is unknown, the
   quality/value contract for my next real task, and the evidence needed for a
   claim. **Acceptance:** a clean store says `evidence pending`; an existing
   eligible store shows only governed relevant context; neither invents savings.
2. **US-DV-02 — Cross-session decision continuity.** As a returning developer,
   I want a pre-existing decision-changing memory delivered before planning so I
   do not repeat investigation or violate an earlier constraint. **Acceptance:**
   Recall supplies the bounded memory, cites its source/currentness, and the
   matched outcome records whether it changed accepted value, time, retries, and
   tokens.
3. **US-DV-03 — Same task, fair comparison.** As a product owner, I can compare
   a control and treatment with the exact same question, rubric, source, model,
   reasoning, tools, and environment. **Acceptance:** any drift, missing attempt,
   unsupplied Recall, or post-run rubric change makes the result inconclusive.
4. **US-DV-04 — Accuracy over response speed.** As a developer, I can accept a
   slower Elefante call when it prevents wrong work or retries. **Acceptance:**
   the card shows invocation latency and full workflow time separately; higher
   value with higher total time is a quality-first trade, never mislabeled as
   productivity.
5. **US-DV-05 — Safe abstention.** As a developer, I want Elefante to stay quiet
   when no memory applies. **Acceptance:** `no_match`, `blocked`, or unavailable
   context receives no causal credit, spends are counted, and no false value
   claim appears.
6. **US-DV-06 — Inspectable economics.** As a developer, I can see input, cached
   input, output, Recall-context, retries, corrections, elapsed time, and money
   only when usage/rate provenance supports it. **Acceptance:** all fields name
   their evidence class, cached/Recall subsets are not double counted, and
   missing provider data remains `unknown`.
7. **US-DV-07 — Smarter memory management.** As a developer, I receive a bounded
   recommendation to capture, amend, merge, narrow, conflict-mark, preserve, or
   archive a memory based on repeated evidence. **Acceptance:** I can accept,
   correct, or reject it; no semantic write occurs without my explicit action;
   its benefit is tested only on a later eligible task.
8. **US-DV-08 — Local control and deletion.** As a user, I can inspect, export,
   reset, and delete usage evidence and curated memories within their separate
   contracts. **Acceptance:** deletion and retention are regression-tested,
   recoverable where promised, and produce no silent network egress.
9. **US-DV-09 — Aggregate team insight without employee scoring.** As an
   authorized team owner, I can view purpose-bound aggregate workflow patterns
   and training opportunities. **Acceptance:** the report is opt-in,
   aggregate-first, suppresses unsafe small groups, and cannot rank or profile
   individuals.
10. **US-DV-10 — Evidence-gated marketing.** As the product owner, I can see
    exactly which wording current evidence permits. **Acceptance:** one-task,
    estimated-cost, or incomplete-time evidence is labeled local/inconclusive;
    only Phase 4 evidence can propose a productivity claim, and publishing still
    requires separate website/release authorization.

---

## 12. Why This Belongs In Elefante

Elefante's released identity is local, governed continuity for agents. Its
development outcome is stricter: help a developer deliver more accepted value
in the same total workflow time, or the same value in less time, while using
tokens intelligently. Token finance is an operating discipline and evidence
view, not the product's identity.

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
- Completes the design layer, not implementation or lift: **GAP-055** —
  [`../ISSUES.md`](../ISSUES.md).
- Prerequisite: [`ide-integration-surface.md`](ide-integration-surface.md) daemon ownership and Source tuple.
- Paired product work: [`retrieval-effectiveness.md`](retrieval-effectiveness.md); Session Intelligence consumes that signal rather than duplicating it.
- Governed by: [`../../docs/explanation/vision.md`](../../docs/explanation/vision.md) Four Laws and Non-Goals.
