# PRD / SDD: Task Intelligence Pipeline

> Status: V2 SHADOW + 3 BLACK-BOX CANARIES IMPLEMENTED; NO EFFECTIVENESS LIFT PROVEN
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

The frozen v1 profile uses the existing retrieval engine. The opt-in v2 profile
adds a deterministic pre-filter over the task's pre-fix repository snapshot,
then uses the existing semantic model for reranking. The profiles and outcome
files remain separate so v1 can be reproduced exactly.

V2 source candidates retain file, line, heading, and symbol lineage; normalize
common plural forms; diversify files; and exclude demo, historical archive,
build, dependency, and benchmark material. Snapshot source is labelled observed
and unverified: current code proves what exists, not that buggy code is correct.

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
      "role": "constraint | decision | dependency | failure | safeguard | implementation | context",
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

The historical Phase 0 record is complete, but it is not promotion-ready. Its
implementation-coupled acceptance tests remain diagnostic evidence only. The
frozen evaluator is `gpt-5.6-terra`, low reasoning,
through `codex-cli 0.147.0-alpha.1.2` and the `task-intelligence-v1` prompt
profile. The 18-task calibration baseline ran once under a 10.8 million total
input-token ceiling and a 1.8 million uncached-input ceiling. It passed 6 of 18
tasks (33.3 percent), using 4,971,429 input tokens, of which 4,329,216 were
cached, plus 54,096 output tokens. The local metadata-only outcomes remain
gitignored. This one-repetition calibration result establishes headroom and
compute cost; it is not promotion evidence.

### Phase 1: Deterministic Task Brief generator

- Build an internal service over the existing retriever and graph.
- Add contract tests for lifecycle filtering, project isolation, conflict
  surfacing, graph-hop limits, provenance, and token budget.
- Generate Briefs in shadow mode only.
- Do not add or change the public MCP surface in this phase.

Exit: identical inputs produce an equivalent ordered Brief and no memory is
mutated.

Phase 1 is complete in shadow mode. `src/core/task_intelligence.py` provides a
pure deterministic compiler and a read-only service over the current hybrid
retriever and one-hop graph. It excludes deprecated, archived, superseded,
low-reliability, low-score, cross-project, and cross-workspace evidence;
surfaces stored conflicts without choosing a winner; retains provenance; and
enforces the frozen per-stage and eight-item limits. Shadow search disables
temporal reinforcement, so generating a Brief does not increment access counts
or mutate memory. There is no public MCP method and no automatic injection.

The answer-isolated evaluation path creates local embeddings only from context
files at each task's pre-fix commit. It uses the current local GTE embedding
model and CognitiveRetriever, forbids model-hub network access, and scans the
resulting corpus for acceptance-answer markers before generating a Brief.

### Phase 2: Controlled evaluation

- Execute randomized paired baseline and treatment runs.
- Produce a local evaluation report with task-level evidence.
- Review every regression and every context-caused failure.

Exit: promotion gate passes, or the design returns to Phase 1.

Phase 2 stopped after the first paired repetition on all 12 holdout tasks. The
committed evaluator at `fa04f2b` ran 24 model trials with seed `20260805`.
Baseline and Task Brief each passed 1 of 12 tasks (8.3 percent): zero pass-rate
lift with a paired 95 percent interval of `[0, 0]`. Treatment used 16.3 percent
fewer total input tokens and finished 1.9 percent faster, but uncached input
rose 2.9 percent. The cost gate passed; the effectiveness and promotion gates
failed.

The remaining 24 pairs (48 model trials) were not run because the preliminary
result showed no correctness signal. The inspected holdout is now diagnostic
evidence and must not be reused as fresh promotion evidence after tuning.
Iteration returns to Phase 1 and calibration tasks only. Before another final
evaluation, freeze a new answer-isolated holdout.

Observed Briefs frequently surfaced broad documentation instead of precise
task-local implementation evidence. The next revision must:

1. retrieve source-grounded implementation evidence, not documentation alone;
2. retain heading and file-path context so fragments remain meaningful;
3. require lexical, path, or dependency relevance and abstain when evidence is
   too weak;
4. prove lift on calibration before consuming a new holdout.

No public MCP method, automatic injection, client pilot, website claim, or
performance claim is authorized by this result.

### Phase 1 v2 audit and pilot (2026-08-06)

V2 fixes the observed retrieval mechanism defects: source-grounded candidates,
heading/symbol lineage, per-file diversity, independent relevance signals,
explicit roles, unresolved-conflict exclusion, graph relationship allowlisting,
and abstention when evidence cannot justify an action. A maintained calibration
audit reached a historical changed implementation file in the top ten for
18/18 calibration tasks. This is navigation evidence only, not outcome proof.

One paired calibration pilot on `install-host-routing-003` failed acceptance in
both conditions. Treatment used 244,365 input tokens in 64,077 ms; control used
448,324 input tokens in 92,263 ms. Lower cost did not improve correctness.

Adversarial review found the governing benchmark defect: the task asked for
host-family isolation, while its hidden test required an undisclosed new module,
exact function names, and exact constants. Review of all 30 tasks found similar
private-API, source-substring, exact-message, or arbitrary-threshold coupling in
many tests. A behaviorally correct alternative can fail, so the historical
manifest is now explicitly diagnostic-only and cannot satisfy promotion.

The next benchmark revision must use black-box CLI/API/filesystem/browser
assertions, explicit observable contracts, exact rollback refs, and an
independent adversarial review bound to the hidden-test SHA-256. It also needs
enough validated tasks for credible confidence. `--require-promotion-ready`
fails closed until those contracts exist. No additional holdout or model runs
are justified before that repair.

### Black-box causal canaries (2026-08-06)

Three replacement fixtures now test observable installer dry-run containment,
dashboard CORS boundaries, and restore archive integrity. Each fixture fails at
its pinned base ref and passes at its pinned known-good ref; its reviewed digest
is bound into the manifest. The remaining 27 historical tasks are still
ineligible, so the benchmark remains diagnostic-only.

The repaired canaries did not prove Task Intelligence effectiveness. CORS tied
at 3/3 passes in both conditions. Restore still failed after the disclosed
golden-path memory ID was confirmed in the treatment Brief. The current source
retrieval diagnostic reaches a historical repair path in 16/18 calibration
tasks, but this is navigation evidence only.

The evaluator now fails closed when the Codex CLI exits without a measurable
attempt, isolates inherited configuration, uses short temporary workspaces,
and records unavailable retry/correction measurements as `null`. The frozen
seed controls pair order only; it does not seed model generation.

No further paired run is justified until the benchmark can distinguish the
causal stages: valid task and judge, relevant retrieval, selection, delivery,
agent use, correct execution, and acceptance. The next iteration adds this
failure observability and enough independently reviewed black-box tasks before
opening a fresh holdout.

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
- every promotion task has a reviewed black-box acceptance contract and its
  exact pre-change and known-good commit refs;
- the Task Brief schema and budget policy are approved;
- the benchmark leakage scan exists;
- control and treatment runs can use identical environments;
- privacy and rollback paths are testable;
- implementation ownership and compute budget are assigned.

Until those conditions are met, status remains design-only and the website must
not market Task Intelligence as a shipped capability.

## Exact rollback

- V1 remains the default Task Brief profile.
- Pass `--brief-profile v1` to reproduce the frozen evaluator.
- V2 uses `__brief-v2` outcome filenames and separate disposable worktrees.
- Reverting the Task Intelligence v2 commit removes the shadow revision; no
  live memory, public MCP method, customer installation, or release is mutated.
- Historical outcome records and commits are immutable. Never rewrite them to
  make a later design appear successful.

## Relationship to Session Intelligence

Session Intelligence may provide local invocation and outcome metadata later.
It must not duplicate the Task Brief evidence contract or become a remote
analytics system. The Task Intelligence evaluation can start with an isolated
benchmark event store and integrate with Session Intelligence only after both
schemas are reviewed together.
