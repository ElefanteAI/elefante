# PRD / SDD: Task Intelligence Pipeline

> Status: PHASE 0 IN PROGRESS; 30 candidate fixtures frozen; model baseline not run
>
> Owner: planning
>
> Consumer: Elefante developers building and evaluating retrieval
>
> Loading model: routed from workspace/PLANNING.md section 4.2
>
> This stable proposal replaces the earlier retrieval-effectiveness sketch in the same canonical file.

## Question

How can Elefante measurably improve task outcomes by delivering the smallest set
of trusted, task-relevant memories at the workflow stage where they can change
the result?

## Product decision

Persistence is a mechanism, not the outcome. The outcome is better task
performance.

Elefante will treat task intelligence as a closed, inspectable loop:

1. understand the task and its success criteria;
2. retrieve candidate memories;
3. reject stale, contradictory, unsupported, or low-value candidates;
4. compile a bounded Task Brief with provenance;
5. deliver each item at planning, execution, or validation time;
6. measure the task outcome against a no-Brief baseline;
7. learn only from repeated, attributable evidence.

Elefante does not increase a model's intrinsic intelligence. It can improve the
model's effective task performance by improving the information available to it.

## Falsifiable hypothesis

For a defined class of coding tasks, a deterministic Elefante Task Brief will
increase acceptance-test pass rate or reduce retries and corrections without an
unacceptable increase in tokens, latency, privacy exposure, or regressions.

If controlled evaluation does not demonstrate that result, the Task Brief must
not become a default workflow and no public performance claim may be made.

## Source-grounded starting point

The current product already provides useful foundations:

- CognitiveRetriever ranks candidates with vector, concept, co-activation,
  authority, and temporal signals.
- RetrievalExplanation exposes why a candidate surfaced.
- MemoryMetadata carries source reliability, verification, lifecycle,
  conflict, supersession, project, workspace, file, and session fields.
- Kuzu stores explicit relationships and the orchestrator already owns task
  graph operations.
- Access counts and co-activation record retrieval behaviour.

Those signals are not proof that a memory improved a task. Access count measures
exposure, and co-activation measures reuse. Neither is a causal outcome signal.
The Task Intelligence Pipeline must preserve that distinction.

## Scope

The first evaluated scope is coding work that depends on prior project context:

- architectural and implementation decisions;
- requirements and constraints;
- dependency relationships;
- previous failures and safeguards;
- stable user or project preferences.

General personal memory, team synchronization, autonomous self-modification,
and broad claims across every task type are outside the first scope.

## Workflow contract

### 1. Task intake

A benchmark or opted-in client supplies:

- task identifier;
- task statement;
- observable success criteria;
- repository or project scope;
- optional token budget;
- workflow stage: planning, execution, or validation.

The system must reject evaluation tasks without observable success criteria.

### 2. Candidate retrieval

Use the existing retrieval engine as the candidate generator. Do not introduce
new scoring weights before measurement.

Apply deterministic gates in this order:

1. remove archived and deprecated memories;
2. isolate the requested project or repository when that scope is known;
3. surface unresolved conflicts rather than choosing a side silently;
4. retain verified specifications, directives, and explicit constraints first;
5. retain relevant decisions, dependencies, failures, and safeguards second;
6. add supporting context only while the Task Brief remains inside budget;
7. expand the graph by at most one relationship hop using an explicit allowlist;
8. record why every selected and rejected candidate was handled that way.

More context is not automatically better. Token budget is a product constraint.

### 3. Task Brief

The Task Brief is an inspectable context packet, not a free-form summary.

Minimum contract:

~~~json
{
  "task_id": "local identifier",
  "task_summary": "bounded task statement",
  "success_criteria": ["observable condition"],
  "stage": "planning | execution | validation",
  "token_budget": 0,
  "evidence": [
    {
      "memory_id": "uuid",
      "role": "constraint | decision | dependency | failure | safeguard | context",
      "reason_selected": "human-readable explanation",
      "source": "provenance reference",
      "verified": true,
      "conflict_ids": [],
      "retrieval_signals": {}
    }
  ],
  "unresolved_conflicts": [],
  "omitted_candidate_count": 0
}
~~~

Every evidence item must retain its memory identifier and provenance. A Brief
must never present generated synthesis as if it were stored evidence.

### 4. Delivery timing

- Planning receives requirements, constraints, decisions, and known blockers.
- Execution receives file, dependency, pattern, and prior-failure evidence.
- Validation receives success criteria, safeguards, and relevant regressions.

Phase 1 may generate all three packets in shadow mode. Automatic injection is
not authorized until controlled evaluation passes.

### 5. Outcome record

The evaluation layer records metadata, not raw transcripts:

- task and evaluation identifiers;
- baseline or Task Brief condition;
- model, version, tool configuration, and run seed when supported;
- memory identifiers delivered;
- acceptance-test result;
- retries or recovery turns;
- human corrections;
- input and output token counts;
- wall-clock duration;
- explicit failure category.

Outcome records remain local and use bounded retention. Raw prompts, responses,
secrets, and full memory bodies are not duplicated into outcome telemetry.

## Measurement protocol

### Benchmark construction

1. Select at least 30 real, reproducible coding tasks from at least three task
   classes.
2. Freeze repository inputs, test commands, and success criteria before running.
3. Separate calibration tasks from a holdout set.
4. Prevent benchmark answers or expected patches from entering retrieval memory.
5. Run at least three paired repetitions per condition when model
   nondeterminism is present.

### Controlled comparison

For each task, keep the model, model version, tools, repository state, system
instructions, and limits equal.

- Control: current workflow without a Task Brief.
- Treatment: identical workflow with the deterministic Task Brief.
- Run order: randomized within each pair.

An LLM judge may provide diagnostics but cannot be the primary success measure.
Maintained tests or explicit human acceptance determine task success.

### Metrics

Primary:

- acceptance-test pass rate.

Secondary:

- retries or recovery turns;
- human corrections;
- total tokens;
- time to accepted result;
- task failures caused by stale or contradictory context;
- selected context per successful task.

### Promotion gate

Default injection is allowed only when the holdout evaluation shows either:

- at least a 10 percentage-point pass-rate improvement; or
- at least a 20 percent reduction in retries or corrections with non-inferior
  pass rate;

and the paired 95 percent confidence interval for the chosen improvement
excludes zero.

There must also be no material privacy, contradiction, latency, token, or
regression failure. If the dataset is too small for credible confidence, the
result remains exploratory.

## Delivery phases

### Phase 0: Benchmark contract

- Choose the initial task class.
- Freeze fixtures, acceptance commands, metrics, and promotion thresholds.
- Add a leakage check proving expected answers are absent from memory.
- Produce a baseline report before changing retrieval.

Exit: benchmark is reproducible and baseline results are stored.

Current Phase 0 evidence (2026-08-05):

- `benchmarks/task_intelligence/tasks.json` freezes 30 real historical tasks:
  ten installation/distribution, ten dashboard-data-integrity, and ten
  runtime-safety/trust tasks.
- Each task pins its pre-fix commit, fix commit, exact pytest acceptance node,
  success criterion, and answer-isolated context paths from the pre-fix tree.
- Calibration contains 18 tasks and holdout contains 12. Tasks from the same
  fix commit cannot cross the split boundary.
- The first budget is 1,500 estimated tokens total: 450 planning, 750
  execution, and 300 validation; at most eight evidence items and one graph
  hop. This is a benchmark limit, not a product default.
- `scripts/ci/verify_task_intelligence_benchmark.py` verifies commit ancestry,
  executable acceptance nodes, context availability, split isolation, the SDD
  thresholds, memory-export answer leakage, and metadata-only outcome records.
- Local outcome files and temporary benchmark worktrees are gitignored. Raw
  prompts, responses, memory bodies, and transcripts are not valid outcome
  fields.

Phase 0 is not complete. The model/version/tool configuration and evaluation
compute budget are not yet frozen, and the no-Brief agent baseline has not run.
No Task Brief generator, automatic injection, public MCP change, or product
performance claim is authorized by this fixture work.

### Phase 1: Deterministic Task Brief generator

- Build an internal service over the existing retriever and graph.
- Add contract tests for lifecycle filtering, project isolation, conflict
  surfacing, graph-hop limits, provenance, and token budget.
- Generate Briefs in shadow mode only.
- Do not add or change the public MCP surface in this phase.

Exit: identical inputs produce an equivalent ordered Brief and no memory is
mutated.

### Phase 2: Controlled evaluation

- Execute randomized paired baseline and treatment runs.
- Produce a local evaluation report with task-level evidence.
- Review every regression and every context-caused failure.

Exit: promotion gate passes, or the design returns to Phase 1.

### Phase 3: Opt-in workflow pilot

- Select the smallest compatible client integration.
- Require explicit opt-in.
- Expose the Brief and provenance before injection.
- Provide an immediate disable and rollback path.
- Measure real tasks without storing raw transcripts.

Exit: pilot confirms benchmark lift without new trust or workflow failures.

### Phase 4: Utility learning

This phase is not authorized by this SDD. It requires a separate design review.

Only after sufficient attributable outcomes may Elefante adjust per-memory
utility. One task cannot promote, demote, merge, or delete a memory. Learned
weights must be bounded, explainable, reversible, and tested against a frozen
baseline.

## Failure modes and required controls

| Failure | Required control |
|---|---|
| Too much context degrades reasoning | hard token budget and omission report |
| Stale memory overrides current code | lifecycle filter, provenance, and current-source validation |
| Conflicting memories are silently resolved | explicit conflict section; no automatic winner |
| Evaluation answers leak into memory | pre-run leakage scan and isolated benchmark store |
| Model variation is mistaken for product lift | paired repetitions and randomized order |
| Frequently retrieved is mistaken for helpful | task outcome is primary; access count is not |
| Feedback corrupts trusted memory | no automatic mutation before Phase 4 |
| Telemetry captures private content | metadata-only local records with bounded retention |
| One workflow improves while another regresses | task-class reporting; no global claim |

## Spec-driven implementation procedure

1. Freeze this SDD and record unresolved decisions.
2. Perform a source and leakage-surface audit before choosing interfaces.
3. Decide the internal Task Brief and outcome-record schemas.
4. Write contract tests before the generator.
5. Build the deterministic generator without public API changes.
6. Establish the no-Brief baseline.
7. Run shadow-mode Brief generation and inspect provenance and conflicts.
8. Run the paired holdout evaluation.
9. Publish the evidence internally and make a go, revise, or stop decision.
10. Only after promotion approval, specify the smallest opt-in client surface.
11. Update released user documentation only when functionality actually ships.
12. Make public performance claims only when linked to a maintained evaluation.

## Acceptance for this SDD

The design is ready for implementation planning when:

- one initial task class and at least 30 candidate tasks are identified;
- every task has an executable or explicit acceptance criterion;
- the Task Brief schema and budget policy are approved;
- the benchmark leakage scan exists;
- control and treatment runs can use identical environments;
- privacy and rollback paths are testable;
- implementation ownership and compute budget are assigned.

Until those conditions are met, status remains design-only and the website must
not market Task Intelligence as a shipped capability.

## Relationship to Session Intelligence

Session Intelligence may provide local invocation and outcome metadata later.
It must not duplicate the Task Brief evidence contract or become a remote
analytics system. The Task Intelligence evaluation can start with an isolated
benchmark event store and integrate with Session Intelligence only after both
schemas are reviewed together.
