# North Star / Implementation PRD: Task Intelligence

> Status: NORTH STAR — METRIC ALIGNED; FIRST BOUNDED FEASIBILITY EXPERIMENT
> COMPLETE (`STOP`)
>
> Product state: governed Recall, Task Brief v2, evaluation, and a metadata-only
> outcome ledger exist in unreleased development. Representative task lift is
> not proven.
>
> Canonical role: this file owns the Task Intelligence objective, the immediate
> experiment, its evidence gates, and the boundary to later product work.
>
> Task 032 implementation baseline: `7c705ca03371771be68460afb270fe0998f30231`.
> Current reconciliation line: `agent/task-intelligence-reconcile-v2123`;
> verify its exact HEAD before work.
> Published customer release: v2.12.3. The active development source also
> declares 2.12.3; provenance and release channel—not semantic version alone—
> keep its extra surfaces unreleased. This document authorizes neither remote
> merge nor release.

## 0. Resume contract — do not restart the debate

A future developer starts here, not from the conversation that produced this
PRD.

- The objective is accepted: maximize accepted task quality per total token on
  eligible memory-dependent tasks.
- The existing infrastructure is not the missing proof. Do not rebuild Recall,
  Task Brief v2, governance, the evaluator, or the outcome ledger.
- Do not rerun the consumed holdout, task 031, or the historical 20/30-task
  audits as if they were new evidence.
- Do not implement Memory Identity, Project Truth, Task Capsule, a state schema,
  or automatic injection first. They are conditional future mechanisms.
- Do not choose a repair before the first failed causal stage is reproduced.
- Do not spend model tokens before model-free judge, eligibility, retrieval,
  selection, delivery, determinism, and no-mutation checks pass.
- Do not create another PRD or handoff file. Current state belongs in
  [`../PLANNING.md`](../PLANNING.md); defects belong in
  [`../ISSUES.md`](../ISSUES.md).
- Task 032 completed the bounded path through §10. Its local verdict is `STOP`;
  do not rerun it, weaken its judge, or treat it as product evidence.
- The replacement-task screen in §14 exposed a reproducible answer-selection
  failure and a positive-control overcorrection. The bounded repair and first
  real question result are recorded there; do not restart the task-032 path.

If new evidence contradicts this contract, update this canonical PRD and its
planning index in the same change. Do not silently route around it.

## 1. North Star

> **For an eligible memory-dependent task, Elefante must maximize accepted task
> quality per total token by supplying the smallest safe set of applicable
> durable memories.**

A task may be a question, decision, plan, code change, or validation action.
Persistence, retrieval, lower token use, and agent acknowledgement are not the
outcome. They are mechanisms or diagnostics.

The current measurable quality proxy is black-box task acceptance: one accepted
outcome contributes one unit of value; a failed outcome contributes zero. Total
tokens are input tokens, including cached input, plus output tokens. The paired
report compares only the same frozen tasks and reports accepted outcomes per
million total tokens; it is not a universal score for comparing unrelated task
difficulty. Paired fields include complete pairs only; `observed_total_tokens`
also exposes every completed run, including unpaired work that caused an early
stop.

Priority order:

1. privacy, user authority, scope correctness, and recoverability;
2. accepted task value per total token;
3. retries, corrections, latency, and other outcome diagnostics;
4. retrieval and delivery diagnostics.

A cheaper failure remains zero value. With accepted value preserved, fewer total
tokens are a real improvement; with accepted value increased, extra tokens are
justified only when the paired value-per-token result improves. No efficiency
result compensates for a trust violation.

## 2. Current truth

The development baseline already contains:

- read-only `elefante-Recall`;
- one `TaskBriefCompiler` with v1 and v2 profiles;
- governance, source-currentness, conflict, secret, scope, provenance, and
  token-budget gates;
- a default-off Task Intelligence lifecycle;
- a metadata-only delivery/use/outcome ledger;
- a paired black-box evaluator and sealed-memory preflight.

Do not build another compiler, public tool, ledger, store, or prompt framework.

The evidence boundary is equally important:

- the first holdout tied at 1/12 versus 1/12: zero correctness lift;
- later runs produced lower input cost without repeatable correctness lift;
- one task produced a local 2/3 treatment versus 0/3 control signal but failed
  the latency gate and did not establish cross-task benefit;
- one schema-v3 sealed-memory evaluation recorded retrieval, selection, and
  delivery as complete while acceptance failed and agent use remained `unknown`;
- task 032 selected and delivered its intended memory in 3/3 treatments, but
  treatment passed 0/3 and the source-only control passed 0/2 before the
  pre-registered early `STOP`; every preserved patch missed the same required
  public Recall tool;
- a post-`STOP` live inventory found only five durable records: one synthetic
  test fact, two unverified related specifications, and two contradictory
  records. The user-declared canonical mission was absent, and Recall returned
  `no_match` when asked for a different eligible memory-task pair;
- the installed Recall proof proves the pipeline, not that Elefante improves diverse tasks.

Therefore, “add more context” is rejected. “Implement Memory Identity first” is
also not yet justified: no preserved outcome proves that state identity or scope
resolution was the first causal failure. A later real fresh-session question did
produce a one-task local correctness signal after capture policy and selection
were corrected; it is not representative evidence.

## 3. Completed decision

The first evidence-led causal repair vertical is complete. Do not implement the
full Project Intelligence Control Plane and do not promote the tested memory
component.

The vertical asks one question:

> On one independently reviewed real task, what is the first stage that prevents
> durable memory from improving the accepted result, and does the smallest repair
> to that stage produce a repeatable local improvement?

Only one causal chain is in scope:

~~~text
explicit user-directed durable decision
  -> governed capture
  -> eligible pre-existing memory
  -> eligible task
  -> candidate retrieval
  -> governed selection
  -> delivery
  -> agent application
  -> behavioral acceptance
~~~

The model-free first failure was an evaluator `SELECTION_MISS`: a real ranked,
unlocked memory was silently rewritten as triggered and locked. The smallest
repair preserves source governance and applies a separate reviewed evaluation
overlay. After that repair, retrieval, selection, and delivery passed, while
model execution failed at application/acceptance. The selected installation
architecture memory did not supply the task-local evidence required to add the
public Recall MCP surface.

## 4. Experiment scope

### In scope

- one new, real, memory-dependent task;
- one pre-existing durable memory that can materially help that task;
- model-free validation and stage diagnosis before any paid run;
- one smallest repair to the first reproducible failed stage;
- deterministic regression tests for that repair;
- at most three frozen paired runs;
- preserved task-level evidence and immediate rollback.

### Out of scope

- persistent schema or migration;
- automatic memory creation, rewriting, reinforcement, or deletion;
- a new MCP tool or public response field;
- a second compiler, evaluator, or usefulness ledger;
- broad Session Intelligence, Project Truth, Task Capsule, Candidate State
  Delta, Project Mode, team sync, or cloud services;
- a new holdout, product claim, website change, version, merge, or release.

[`memory-identity.md`](memory-identity.md) remains a deferred design reference.
Its schema work activates only if the experiment traces the first failure to
state/scope ambiguity and a read-only resolver improves the frozen task.

## 5. E0 — Freeze one eligible task

Task 032 is frozen and consumed. Do not use task 031, task 032, or any consumed
holdout as new evidence.

| Bound field | Frozen value |
|---|---|
| Task | `install-codex-recall-routing-black-box-032` |
| Base | `788e8aedd830297c628325696906e50d896f8715` |
| Known good | `7c705ca03371771be68460afb270fe0998f30231` |
| Memory | `f3482775-83b7-47b5-9cbb-d54da9d8bc73` |
| Judge digest | `bd641d73bc34494e08228e508e793a69547a19862fe17712b1c71eeded74e9bc` |
| Fixture digest | `d278f31026c363d56fc559bd0bbf3f0945093e8405e2c8680e5c49f906655931` |
| Model | `gpt-5.6-sol`, reasoning `max` |
| Seed / ceiling | `20260805`; three treatment repeats and at most three controls |

The black-box judge runs documented setup and uninstall commands in an isolated
home, preserves the user's instruction bytes, checks host registration, and
lists the real stdio MCP surface. Base fails and known good passes. The sealed
fixture preserves the live record's actual governance metadata and carries a
separate reviewed evaluation overlay; it does not mutate the live store.

The task is eligible only when:

1. a durable memory existed before the task;
2. the memory is useful but does not contain the expected answer or patch;
3. the task has a black-box acceptance check;
4. the judge fails on the exact base and passes on the known-good reference;
5. the task and judge expose every required convention without requiring one
   historical implementation shape;
6. control and treatment start from equivalent clean state;
7. current source, tools, model, limits, and mandatory user policy can remain
   identical across conditions;
8. the expected memory-to-outcome path survives an adversarial review.

Before code changes, bind these values in the existing benchmark contract:

- task ID, repository, exact base SHA, and known-good SHA;
- acceptance command and test digest;
- observable success condition;
- durable memory ID, creation time, content digest, and sanitized fixture;
- expected useful information, without copying the answer;
- model, reasoning level, tools, timeout, token cap, repetition count, and pair
  order seed;
- maximum three pairs and one repair iteration.

For a replacement task, every condition still applies. If no task passes, stop.
The blocker is missing causal evidence, not missing architecture.

## 6. E1 — Locate the first failed stage without a model run

Use existing code and preserved artifacts first. Generate the current v2 Task
Brief twice and require byte-identical output. Record:

| Stage | Required evidence | Failure classification |
|---|---|---|
| Judge | base fails; known-good passes; exact digest bound | `JUDGE_INVALID` |
| Eligibility | real prior memory and causal path approved | `TASK_INELIGIBLE` |
| Retrieval | intended memory is among candidates | `RETRIEVAL_MISS` |
| Selection | intended memory survives governance and is selected | `SELECTION_MISS` |
| Delivery | selected ID and bounded content reach treatment | `DELIVERY_MISS` |
| Application | agent behavior changes in the intended direction | `APPLICATION_MISS` |
| Acceptance | black-box contract passes | `ACCEPTANCE_FAIL` |

Stop at the first failed stage. Do not tune ranking, add scope machinery, or run
more repetitions to compensate for an invalid earlier stage.

### Task 032 result

- Judge: base rejected; known good accepted; exact digest bound.
- Eligibility: one prior durable customer-installation memory; no answer or
  patch embedded in the fixture.
- Retrieval: intended memory present.
- Initial selection: failed because the evaluator invented trigger/lock
  metadata instead of preserving the live ranked/unlocked record.
- Repaired selection: intended memory selected first; deterministic.
- Delivery: intended memory reached all three treatments within a 1,500-token
  Brief; live memory and product state remained unchanged.
- Application/acceptance: failed. All five measured patches changed installer
  or guidance files but omitted `elefante-Recall` from the MCP server.

## 7. E2 — Implement only the demonstrated repair

Task 032 used the `SELECTION_MISS` route. Fixture schema v2 now preserves exact
source governance and represents reviewed evaluation adjudication separately.
Schema v1 behavior remains unchanged. This is evaluator correctness, not a
product ranking or runtime-delivery change.

### Common contract

Every allowed repair must:

- reuse `TaskBriefCompiler`, Task Brief v2, the existing evaluator, and the
  existing outcome record;
- be deterministic and read-only through retrieval, selection, and delivery;
- preserve memory IDs, provenance, governance, conflict, and token limits;
- preserve exact current behavior when disabled;
- default off;
- add no persistent schema in this experiment.

### Repair routing

| First failure | Smallest allowed repair | Primary files |
|---|---|---|
| `RETRIEVAL_MISS` | Correct candidate generation for the reproduced query; no selector rewrite | `src/core/retrieval.py`, existing retrieval tests |
| `SELECTION_MISS` caused by ordinary relevance/budget | Correct the existing v2 selector at the failing gate | `src/core/task_intelligence.py`, `tests/test_task_intelligence.py` |
| `SELECTION_MISS` caused by state/scope ambiguity | Add the evaluation-only read-only resolver in §8 | `src/core/task_intelligence.py`, new focused resolver tests |
| `DELIVERY_MISS` | Repair the existing Task Brief/evaluator handoff | `scripts/ci/run_task_intelligence_evaluation.py`, evaluator tests |
| `APPLICATION_MISS` | Improve evidence rendering inside the existing Task Brief only if an ablation proves the representation caused the miss | `src/core/task_intelligence.py`, focused rendering tests |
| `JUDGE_INVALID` or `TASK_INELIGIBLE` | Fix or reject the task; no product code | benchmark contract and verifier only |

Do not combine repairs. If two stages fail, repair the earlier stage and rerun
model-free preflight before evaluating the next.

## 8. Conditional resolver contract

This section applies **only** when E1 proves a state/scope selection failure.

### No-schema input

Use a sealed evaluation overlay keyed by existing memory ID. Do not alter the
live memory or `MemoryMetadata`.

~~~json
{
  "memory_id": "existing-uuid",
  "subject": "bounded subject",
  "predicate": "bounded predicate",
  "assertion_role": "governing | observed | supporting",
  "scope": {"dimension": "normalized value"},
  "normalized_value": "reviewed value",
  "supersedes": []
}
~~~

Only scope dimensions required by the frozen task are allowed. No universal
scope taxonomy is designed in this experiment.

### Pure output

~~~json
{
  "status": "READY | REQUIRES_SCOPE | UNRESOLVED_CONFLICT",
  "applicable_memory_ids": [],
  "excluded": [{"memory_id": "...", "reason": "..."}],
  "conflicts": []
}
~~~

### Resolution rules

1. Apply existing lifecycle, authority, and privacy gates first.
2. Match the task scope; exact values outrank wildcards.
3. Group state assertions by `project + subject + predicate + normalized scope`.
4. A governing assertion defines intent; an observed assertion can support or
   contradict it but cannot silently replace it.
5. Incompatible active governing values at the same exact key return
   `UNRESOLVED_CONFLICT`.
6. Missing scope needed to choose between incompatible claims returns
   `REQUIRES_SCOPE`.
7. Supporting history cannot define governing state.
8. Resolution does not mutate memory, graph, access, co-activation, ranking, or
   the overlay.

### Code interface

Add a pure `TaskStateResolver` beside the existing compiler in
`src/core/task_intelligence.py`. The existing compile path receives an optional
sealed state contract; `None` must preserve current output exactly. The
evaluator supplies the contract only to the resolved-treatment condition.

Do not edit `src/models/memory.py` or expose the resolver through
`src/mcp/server.py` during this experiment.

## 9. E3 — Deterministic proof

Write the failing test before the repair. The smallest required set is:

1. exact reproduction of the selected stage failure;
2. intended memory is retrieved, selected, or delivered after the repair;
3. wrong-scope or contradictory memory does not replace it;
4. feature-off output equals the pre-change output;
5. two identical runs produce identical IDs, ordering, reasons, and rendered
   context;
6. memory, graph, access count, co-activation, ranking, and ledger remain
   unchanged during preflight;
7. hard token and evidence-item limits still hold;
8. existing Task Intelligence and evaluator tests remain green.

If the conditional resolver is used, add focused tests for exact-scope match,
wildcard fallback, missing scope, governing/observed mismatch, same-key
conflict, and no mutation.

No model run is allowed until all deterministic checks pass.

## 10. E4 — Causal component test

Extend the existing evaluator; do not create another harness.

- **Control:** the same source-grounded Task Brief v2 without the sealed durable
  memory.
- **Treatment:** the same source-grounded Task Brief v2 plus only the sealed
  durable memory.
- **Held constant:** task, base state, mandatory user policy, model, reasoning,
  tools, prompt protocol, budget, timeout, and acceptance judge.
- **Order:** seeded paired order fixed before execution.
- **Ceiling:** three valid pairs; abort on an invalid judge, failed delivery,
  infrastructure failure, or trust violation.

The outcome record must bind the task contract and record retrieval, selection,
delivery, execution, and acceptance. It must not store raw prompts, responses,
memory bodies, source diffs, or secrets.

The report computes the §1 metric from complete matched pairs. A future
multi-task evaluation may use token intelligence as an effectiveness path only
when treatment has at least one accepted outcome, does not reduce the number of
accepted outcomes, and the task-clustered 95% lower bound of the paired
value-per-total-token difference is above zero. This rule applies prospectively;
consumed outcomes remain diagnostic and cannot be relabelled for promotion.

### Decision rule

This is a local feasibility gate, not product proof.

- **LOCAL GO:** treatment passes 3/3, control passes 0/3, the intended memory is
  selected and delivered in every treatment, the behavioral difference follows
  the pre-registered causal path, and all hard constraints pass.
- **STOP:** the repair does not change the intended stage, treatment passes 0/3,
  or any privacy, authority, scope, contradiction, mutation, or rollback rule
  fails.
- **INCONCLUSIVE:** every other result. Permit one repair iteration only when a
  deterministic trace exposes a reproducible defect. Do not weaken the judge or
  decision rule after seeing results.

Tokens or latency may break a `LOCAL GO`; they cannot create one.

### Task 032 measured result

**Decision: `STOP`.** This is a valid local negative result, not a product
failure rate or release claim.

| Evidence | Result |
|---|---|
| Model-free canary | base failed; known good passed |
| Determinism | source-only and memory Briefs reproduced byte-identically |
| Intended memory | selected and delivered in 3/3 treatments |
| Treatment acceptance | 0/3 |
| Source-only control acceptance | 0/2; a third attempt was terminated before a measurable outcome once treatment 0/3 made `STOP` irreversible |
| Root failure | application/acceptance: all five patches passed earlier routing, preservation, and uninstall assertions, then failed because live MCP `tools/list` lacked `elefante-Recall` |
| Stored evidence | five schema-v3 metadata-only outcomes; no prompts, responses, memory bodies, or source diffs |
| Measured token cost | Five completed outcomes: 1,417,856 input; 1,112,064 cached; 305,792 uncached; 83,452 output; 1,501,308 total input plus output. Exact partial usage from the terminated sixth attempt is `UNKNOWN`. |

Every completed task 032 outcome failed, so accepted value was zero regardless
of token cost. The memory was architecturally relevant but not causally
discriminative. It
described stable per-user installation, one data root, a loopback daemon, and
host coverage; it did not identify or explain the missing task-local Recall API
surface. Both conditions therefore converged on installer routing changes and
missed the same product behavior. This rejects the tested mechanism: selecting
and appending a broadly relevant durable memory is insufficient to improve this
task.

The evaluator now supports a strict `memory-component` comparison and a
decision-complete early stop. Early stop never creates a `LOCAL GO` or marks the
paired protocol complete; it activates on a bound failed delivery or after all
three treatment repeats are bound and observable.

### Final implementation gates

- Full maintained fast suite: 455 passed, 4 skipped, 1 slow deselected.
- Maintained slow gate: 1 passed.
- Benchmark canaries: 9/9 rejected base and accepted known fix.
- Focused Task Intelligence and documentation routing: 86 passed.
- Ruff 0.1.15 and `git diff --check`: passed.
- Exact resume replay: `STOP`, zero new results, one remaining control not
  started; `--require-decision` passed while promotion remained false.

## 11. Rollback

- The experiment flag defaults off.
- Feature-off behavior remains the current v2 path.
- No persistent schema or live store changes exist to undo.
- Evaluation uses disposable repository state and a sanitized sealed fixture.
- Failed workspaces and immutable outcomes remain available for diagnosis.
- Revert the single repair commit to remove the experiment; do not rewrite
  shared history.

## 12. Exit and next decision

### If `STOP`

Preserve the evidence, reject the tested mechanism, and choose no replacement
until a different first-stage failure is demonstrated.

Task 032 is in this state. Do not patch its prompt, add more memories, or buy a
fourth treatment. Its evidence is consumed.

The next candidate scan also stopped before model execution: the live store had
no unconsumed decision-changing memory suitable for a new task. GAP-054's
explicit user-directed capture path now passes model-free: the canonical mission
was stored, an invalid prose scope was exposed rather than hidden, and the same
record became Recall-deliverable after literal scope correction. Do not convert
that continuity proof into a lift claim. Let the stored decision predate a future
independently arising task and reject the pair unless its fact is absent from the
source-only Brief and can change the answer or action.

### If `INCONCLUSIVE`

Do not expand architecture or buy more runs. Diagnose the recorded stage trace.

### If `LOCAL GO`

The repair earns only the next experiment:

1. reproduce benefit on a second independent memory-dependent task;
2. then test multiple task classes with a pre-registered powered design;
3. only after representative lift, design persistent identity or runtime
   integration if the proven mechanism requires it;
4. close BUG-052 before installed-candidate evidence or any release claim;
5. complete customer artifact, host, privacy, rollback, and release gates under
   separate explicit authority.

No one-task result authorizes automatic injection, marketing, merge, version,
tag, release, or deployment.

## 13. Implementation checklist

- [x] E0 task and exact evidence contract approved.
- [x] E1 first failed stage recorded from model-free preflight.
- [x] One repair selected from the routing table.
- [x] Failing deterministic regression included with the repair change.
- [x] Feature-off equivalence and no-mutation proof pass.
- [x] Existing focused Task Intelligence suites pass.
- [x] Exact capped paired plan reviewed before execution.
- [x] Result classified `LOCAL GO`, `STOP`, or `INCONCLUSIVE` without changing
      the rule.
- [x] Evidence and current state recorded in canonical developer surfaces.

## 14. Immediate goal and first real question signal

The first independently arising question after durable capture asked for the
single criterion that distinguishes valuable Elefante work from overhead. The
pre-existing canonical mission contained that user decision; the clean control
had no project source or prior conversation.

The first live Recall attempt exposed two sequential failures. The mission had
been configured as literal-triggered to make one verification question pass, so
a natural paraphrase was blocked. After a reversible `triggered` → `ranked`
metadata correction, the first selector repair still rejected the mission
because it replaced a false-positive role shortcut with one absolute lexical
coverage threshold. The final bounded repair keeps that negative guard and adds
one explicit governance path: a user-locked, scoped, ranked directive may guide
a semantically strong decision question in its named scope. Ordinary memories
still need direct or structural task evidence, and the rule does not depend on
unrelated competitors being present.

A later independently arising self-improvement request exposed one remaining
short-query recurrence: generic Developer Etiquette was promoted when the
repeated project name was the only distinct matched term. The shared selector
now requires two distinct text matches for multi-term questions before ordinary
text can qualify as a direct answer or role anchor. One-term facts and explicit
governing or structural paths remain valid. This is a model-free relevance
repair, not new causal-lift evidence.

Model-free proof now selects only the canonical mission for the paraphrase and
still abstains on the unrelated issue-2 screen. A seeded three-pair Sol Max
component screen produced 3/3 accepted treatment answers and 0/3 control answers
(`UNKNOWN`). Total input plus output tokens were 43,984 treatment and 43,532
control; the additional 452 tokens changed accepted value from zero to three.
A separate fresh Codex session invoked live `elefante-Recall` and answered the
question correctly. This is a local one-task signal, not a representative or
release claim; the maintained evaluator does not yet bind question-response
outcomes, so do not call it promotion evidence.

A later frozen diagnostic compared the same mission question under selective
Recall and full-store injection. Both isolated Sol Max arms returned the exact
accepted criterion. Selective Recall supplied one memory and used 14,912 total
tokens; full-store injection supplied all six records and used 15,420. The
selective arm therefore preserved accepted value while saving 508 tokens (3.3%
of the full arm). Two earlier attempts are invalid and excluded: one leaked the
expected answer through response choices, and one judge matched `controlled` as
if it proved a no-memory `control`. This is evidence against full-store delivery
as the default on this task, not representative lift.

The inventory audit found no second eligible decision memory. After that audit,
the user's previously explicit evidence-based, non-sycophantic,
token-disciplined working protocol was captured as protected ranked memory
`6550d201-75a9-4de6-a7b4-bdb864836920`. Fresh Recall supplied only that record
at score 0.976. Because it was written after the current diagnostic began, it
cannot be used retroactively; it is only a candidate for a later independently
arising task. Its rollback is recoverable archive by ID.

### Active acquisition loop

The absence of an eligible evaluation task is not authority to invent one, but
it is also not a reason to stop product work. Continue the highest-value normal
Elefante task and run the following bounded loop:

1. prepare Task Intelligence before the decision;
2. deliver memory only when it contains discriminative task evidence;
3. if it abstains, proceed from current source and runtime evidence without
   forcing context;
4. after the outcome is verified, capture at most one stable reusable fact when
   it is absent from the store;
5. verify Recall delivery, then leave causal testing to a later independent
   task that the memory predates.

The exact-candidate validation task exercised this loop. The two pre-existing
records were too generic, so the pilot returned a 21-token abstention and no
delivery. After the task exposed and fixed the durable-source defect, one
managed Elefante-scoped release invariant was captured as memory
`726655b2-4941-4602-a1ba-bdbb9ed66eae`. Recall supplied it for a matching future
question, and a model-free lifecycle check delivered it, recorded declared use,
and recorded a test-accepted outcome in trace
`61f1e713-5776-4bf1-a43b-3f9deecc7502` using 217 estimated Brief tokens with no
ranking mutation.

This proves abstention, acquisition, delivery, declared use, and outcome
recording. It does not prove causal lift because the memory was created after
the source task and the later delivery check had no source-only control.

> **Your goal is to keep solving the highest-value Elefante work while this
> loop accumulates clean pre-task opportunities. The next causal comparison is
> allowed only when a previously stored fact can change an independently
> arising task; do not invent a benchmark task or inject generic context.**

One local question lift exists; representative lift does not.

## 15. Recall-first development program — plan before code

**Status:** DEVELOPMENT COMPLETE; LOCAL INSTALLED-CANDIDATE ACCEPTANCE PASSED;
REPRESENTATIVE LIFT UNPROVEN. No source implementation begins under this
program until the package being entered has its dependency, rollback, and
acceptance proof identified below. This sequence implements the user's
Recall-first direction without turning the dirty development checkout into an
unbounded feature pass.

**Classification:** BUG-051 owns end-to-end Recall routing; GAP-053 owns the
difference between broadly relevant and decision-changing memory; GAP-055 owns
accepted task value per total token. The packages reuse the existing Recall,
Task Brief v2, governance, evaluator, and outcome ledger. They do not authorize
a second retrieval system, automatic full-store injection, live-memory
mutation, installation, merge, release, or deployment.

### 15.1 Ordered development packages

| Package | Question and bounded scope | Dependency | Independent exit gate |
|---|---|---|---|
| **R0 — Freeze the baseline** | Bind the exact public, installed, and development tool inventories; reproduce the configured-routing versus live-Recall mismatch; record current Recall response/token sizes. Read-only only. | None | Exact refs and artifacts are recorded; no source, runtime, host, or memory mutation occurred. |
| **R1 — Customer Recall surface parity** | Ensure a customer artifact that installs Recall guidance also contains default-on, read-only `elefante-Recall`, its operator rollback, and the minimal seven-field response contract. Do not enable Task Intelligence or tool-call context injection. | R0 | Source discovery, built customer archive discovery, and focused MCP tests agree on Recall; rollback returns the previous public surface exactly. |
| **R2 — Recall-aware readiness** | Make readiness verify the capability the host was instructed to use: MCP initializes, `tools/list` contains Recall, annotations are read-only, and one bounded Recall probe returns `supplied`, `no_match`, or governed `blocked`. Missing tool, transport failure, or `404` is not customer-ready. | R1 | Deterministic doctor tests cover present, absent, disabled, `404`, and safe abstention; the probe performs no write and exposes no memory body in diagnostics. |
| **R3 — Token-financial response contract** | Measure and minimize Recall request, context, protocol, retry, and failure cost without weakening relevance or governance. Preserve the compact customer payload and keep accounting metadata internal. | R2 | Supplied and positive-control answers retain behavior; `no_match`, `blocked`, and `unavailable` are bounded; no internal IDs, directives, entrypoint wrappers, or `TOKEN_STATS` block enter the Recall payload. |
| **R4 — Relevance and abstention hardening** | Repair only a reproduced retrieval or selection failure. Deliver memory only when it contains discriminative task evidence; preserve one-term facts, governing paths, source-currentness, conflict, privacy, and token limits. | R3 | The first failed causal stage has a failing regression first; false-positive, positive-control, determinism, no-mutation, and hard-budget tests pass. |
| **R5 — Independent outcome proof** | Compare selective Recall with a source-only control on the next independently arising eligible task whose decision-changing memory predates the task. Do not invent a task or reuse consumed evidence. | R4 and a naturally eligible task | At most three pre-registered pairs; black-box acceptance and all observed spend are bound. A failed outcome has zero value. One task cannot authorize promotion. |
| **R6 — Customer closure** | Synchronize shipped reference, installer guidance, release verification, changelog, and rollback only after R1–R5 establish the behavior they describe. | Required preceding package gates | Documentation routing and release-client verification pass; commit, install, merge, tag, release, and deploy remain separately authorized operations. |

Packages are entered one at a time. A package that fails its exit gate stops the
sequence at that layer; later packages cannot compensate with more context,
more model calls, or a weaker judge.

#### R0 baseline evidence — 2026-08-26

- Published and installed v2.12.3 expose 16 tools and 2 prompts; their MCP
  surface does not contain `elefante-Recall`.
- The current development source exposes 17 tools and 2 prompts by default,
  including Recall; Task Intelligence remains a separate opt-in eighteenth
  tool.
- The installed doctor reports `customer_ready=true`, daemon health, verified
  Codex coverage, and installer-owned `codex-recall-routing`, while a live
  Recall invocation returns HTTP `404` at the configured daemon MCP endpoint.
  This is the exact R1/R2 mismatch; a healthy process is not capability proof.
- Model-free heuristic samples using the current development compiler measured
  a one-memory supplied response at 102 context / 143 payload tokens, a
  `no_match` response at 80 context / 121 payload tokens, and an `unavailable`
  response at 86 payload tokens. These are reproducible fixtures, not provider
  billing or general workload averages.
- Current ceilings are 1,000 question characters, 12 retrieval candidates,
  three delivered memories, and 450 heuristic context tokens.

R0 passes. R1 is the next package; no product source, installed runtime, host
configuration, durable memory, or remote state changed during the baseline.

#### R1 result — customer Recall surface parity

- Existing development behavior already exposed Recall by default with
  read-only, non-destructive, idempotent, closed-world annotations; the local
  rollback flag restores the 16-tool surface and Task Intelligence stays
  default-off.
- Added one release-client regression that builds a real Linux customer ZIP and
  requires the packaged MCP source, Codex guidance, and default customer
  configuration to agree on Recall. The archive must contain the Recall tool and
  rollback contract, must tell Codex to call it, and must not disable it.
- Proof: four focused Recall MCP boundary tests pass; the new built-archive
  contract test passes; the complete nine-test release-client suite passed
  before the new guard and will be rerun at closure.

R1 passes. R2 is next. No installed runtime, host configuration, durable
memory, provider model, remote branch, release, or deployment changed.

#### R2 decision and subpackage split — Recall-aware readiness

`ready` continues to mean that the local runtime infrastructure is present and
healthy. `customer_ready` means more: when installer-owned host guidance tells
Codex to call Recall, the active guidance path and the live MCP capability must
both verify. A healthy daemon or a recorded file hash alone is insufficient.

R2 is entered in this order:

1. **R2a — live capability inspector.** Extend the maintained customer MCP
   verifier to initialize the bridge, list tools, validate Recall's read-only
   annotations, and make one bounded read-only probe. Return only a safe status
   summary; never print the retrieved context. Doctor consumes this summary and
   makes missing Recall, invalid annotations, `unavailable`, transport failure,
   or HTTP `404` customer-readiness diagnostics.
2. **R2b — active Codex guidance precedence.** Verify that the installer-owned
   Recall block is in the guidance file Codex actually loads. A later non-empty
   `AGENTS.override.md` must not leave a base-file routing record counted as
   ready when the active override masks it. Preserve every user-managed byte.
3. **R2c — configuration atomicity.** If Codex MCP registration succeeds but
   managed Recall guidance fails, report partial configuration and recover only
   installer-owned state. Do not remove or rewrite a user-managed registration
   or guidance file. This package is entered only after R2a and R2b prove the
   failure path and rollback target.

Each R2 subpackage gets its own failing test, patch, and focused pass before the
next begins. Exact-artifact installation and a real Codex normal-question event
remain R6 acceptance; they are not simulated by weakening R2 unit tests.

##### R2a result — live capability inspector

- The maintained customer MCP verifier can now initialize the real stdio
  bridge, list tools, validate Recall's four safe annotations, and make one
  bounded read-only probe. Its returned summary contains only capabilities,
  counts, booleans, status, and a diagnostic; retrieved context is discarded.
- Doctor runs the probe only when installer ownership records
  `codex-recall-routing`. `ready` remains infrastructure health, while
  `customer_ready` now fails for a missing tool, unsafe annotations,
  unavailable/invalid probe, timeout, or transport failure.
- Pure parser and doctor tests accept safe `no_match`, reject missing/unsafe or
  unavailable Recall, and prove context cannot enter doctor output. Focused
  result: 19 passed, 62 deselected; compilation and whitespace checks pass.
- A live read-only probe against installed v2.12.3 initialized successfully,
  listed 16 tools, and returned `recall_tool_missing`; no Recall call, model
  call, runtime write, host change, or memory mutation occurred.

R2a passes. R2b is next. The installed runtime still runs the unchanged public
v2.12.3 artifact; this development proof is not an installed repair.

##### R2b result — active Codex guidance precedence

- Manifest-owned `codex-recall-routing` now counts as configured only when its
  recorded path is the guidance file Codex currently loads. A non-empty
  `AGENTS.override.md` masks an installer-owned block in `AGENTS.md`, so the
  stale base-file record no longer produces a false ready result.
- Doctor now requires verified Codex host coverage whenever the installer owns
  Recall routing. Live Recall capability alone cannot conceal missing or
  inactive guidance.
- A regression creates a later user-managed override after installation,
  proves readiness is withdrawn, reruns the installer, and proves the user
  bytes remain unchanged while the managed block moves to the active path.
- Focused result: 16 passed, 62 deselected; compilation and whitespace checks
  pass.

R2b passes. R2c is now eligible for its required failure-first proof. No user
guidance, installed runtime, host configuration, durable memory, or remote state
was changed by this development test.

##### R2c entry — reproduced registration/guidance split failure

- A focused regression forces managed Recall guidance to fail after a new Codex
  MCP registration has been added and verified. On the pre-patch path the
  function returns `failed` but leaves that registration active; the test fails
  with `configured != missing`.
- The repair boundary is the one transaction only: defer ownership recording
  until guidance succeeds; on guidance failure, remove the newly added
  installer registration and restore a prior unchanged installer-owned
  registration when one existed. Never remove an unrelated user registration.
- A successful rollback returns `failed` because configuration did not finish.
  A failed rollback returns `partial` so callers cannot mistake residue for a
  clean failure. No broad uninstall helper or user-file rewrite is allowed.

##### R2c result — configuration atomicity

- Host-command ownership is now recorded only after Codex Recall guidance
  succeeds. A clean guidance failure removes a newly added registration; a
  refresh failure restores the exact prior unchanged installer-owned add
  command and leaves its manifest record intact.
- If removal or restoration fails, the adapter returns `partial` rather than a
  clean `failed` result. Existing user-managed registrations remain outside the
  ownership path.
- The original failure-first regression and two ownership/partial-state
  controls pass. The complete installer lifecycle result is 81 passed,
  including the isolated real Codex registration round trip and wheel contract.
  One preliminary run used an audit interpreter without `pip`; after
  bootstrapping `pip` into that temporary environment, the unchanged suite
  passed in full.

R2 passes. R3 is next. The development checkout changed only the documented
readiness/installer sources and tests; no installed runtime, live host, user
guidance, durable memory, release, or remote state changed.

#### R3 decision and subpackage split — token-financial response contract

The relevant cost is the complete host/model path, not only the selected memory
body. Recall therefore treats the request, response metadata, context,
serialization expansion, retries, and failed calls as spend. The seven-field
response remains stable: several booleans are derivable from `status`, but their
small fixed cost preserves a machine-readable compatibility contract and is not
worth a breaking migration.

R3 is entered in this order:

1. **R3a — one-question call discipline.** Align the tool description, Codex
   managed guidance, grounding prompt, and customer reference: skip Recall for
   a self-contained question and call it at most once per user question. A
   terminal `no_match`, `blocked`, or `unavailable` response is not a reason to
   broaden retrieval or retry in the same answer.
2. **R3b — bounded response serialization.** Do not echo the question back in a
   Recall context because the host already owns it. Preserve Unicode in the
   returned text instead of expanding it to ASCII escape sequences. Keep the
   existing 450-token governed context limit and add a 1,000-heuristic-token hard
   cap for the complete seven-field response; fail closed with no memory body if
   encoded output exceeds it.
3. **R3c — internal accounting fidelity.** Count Recall request, complete
   returned payload, and delivered context in the in-memory ledger without
   exposing `TOKEN_STATS`. This remains a local heuristic and never becomes a
   provider invoice or dollar estimate.
4. **R3d — contract reconciliation.** Update only the canonical tool, token,
   architecture, self-protocol, issue, and installer references that state this
   behavior. Remove stale wording; link rather than create another Recall guide.

Each subpackage gets its own focused assertions. R3 does not change retrieval
thresholds, candidate count, memory count, ranking, governance, provider model,
or evaluation prompts.

##### R3 baseline measurements — 2026-08-26

- A maximum-length 1,000-character ASCII question with no selected memory
  produces a 395-token pretty response because the response repeats 349 tokens
  of answer-context/question text.
- A synthetic 450-token ASCII context produces a 495-token complete response;
  the same raw budget made entirely of backslashes produces 946 tokens because
  JSON must escape them.
- A 450-token CJK context produces 1,587 tokens under current ASCII-escaped
  serialization but 475 tokens with Unicode-preserving serialization.
- A pathological 450-token control-character context can still exceed 2,700
  serialized tokens, so Unicode preservation alone is not a hard bound. The
  complete-response cap must fail closed rather than truncate evidence.
- The existing `unavailable` response is 91 tokens. These figures use
  Elefante's checked-in heuristic over the actual pretty JSON shape; they are
  not provider usage or billing totals.

##### R3a result — one-question call discipline

- Recall discovery now says to call at most once per user question, skip a
  self-contained question, and not retry terminal `no_match`, `blocked`, or
  `unavailable` results.
- The same rule is present in the grounding prompt and the exact reversible
  Codex installer block. It does not suppress a later verification Recall after
  an explicit durable write, because that is a distinct post-mutation question.
- Focused source, prompt, installer-preservation, and real built-customer-archive
  assertions pass: 4 passed; compilation and whitespace checks pass.

R3a passes. R3b is next. No tool was called twice, no provider evaluation ran,
and no installed guidance, live host, memory, or remote state changed.

##### R3b result — bounded response serialization

- Recall now asks the shared governed compiler not to echo the current question;
  search, prompt, and opt-in context consumers retain their self-contained
  question text. Both supplied and no-match Recall responses preserve selection
  behavior without paying for the duplicated request.
- Recall serializes its customer text with Unicode preserved. The measured CJK
  case falls from 1,587 to 475 heuristic response tokens while retaining the
  same 450-token context body.
- The complete seven-field response is capped at 1,000 heuristic tokens over
  the exact pretty Unicode JSON shown to the model. An oversized encoded body
  fails closed to a seven-field `blocked` response; it is not truncated or
  silently substituted.
- Post-fix measurements: maximum-length no-match is 105 tokens, the CJK case is
  475, and the synthetic oversized control-character case becomes an 89-token
  blocked response. Four failure-first tests and the full shared
  Recall/answer-context slice pass: 18 passed, 32 deselected; compilation and
  whitespace checks pass.

R3b passes. R3c is next. Retrieval limits remain 12 candidates, three memories,
and 450 context tokens; no ranking, governance, model, installed runtime, or
memory data changed.

##### R3c result — internal accounting fidelity

- Recall's in-memory ledger now measures the exact pretty Unicode payload shown
  to the model and separately counts the returned `context` field. Input remains
  the heuristic size of the tool arguments.
- The seven-field customer response still contains no `TOKEN_STATS`; Recall has
  zero static protocol overhead on this path. Unavailable and blocked attempts
  still count because failed work is spend.
- The failure-first multilingual ledger regression passes, and the complete
  token-intelligence suite passes: 40 passed; compilation and whitespace checks
  pass.

R3c passes. R3d is next. These totals are process-local estimates, reset with
the server, and are neither provider usage nor a dollar-cost calculation.

##### R3d result — canonical contract reconciliation

- The tool, token-intelligence, architecture, self-protocol, orchestrator,
  Copilot, script-index, issue, and changelog surfaces now agree on the one-call
  rule, 450-token context budget, 1,000-token complete-response cap, hidden
  heuristic accounting, active-guidance/readiness proof, and atomic rollback.
- The references continue to state that published v2.12.3 exposes 16 tools and
  that Recall is an unreleased customer candidate in this checkout. Development
  proof is not rewritten as an installed or published claim.
- A cross-document regression binds those claims to the source constants and
  installed-flow descriptions. It passes, and the full documentation-routing
  suite passes: 38 passed; link, anchor, inventory, release-boundary, and
  whitespace checks are included.

R3 passes. No provider evaluation was needed: the repaired serialization path
reduced the measured CJK response from 1,587 to 475 heuristic tokens while
retaining the same selected context, and all other proofs were model-free.

#### R4 entry — relevance and abstention screen before repair

R4 begins with no authorized selector edit. The current Task Brief selector and
its tests already contain uncommitted BUG-045 hardening owned by the existing
developer checkout. First run the registered false-positive and positive-control
tests plus the shared Recall/answer-context slice. If they pass, R4 closes as a
no-change verification; no threshold is moved merely to create activity. If one
fails, document the first failed causal stage and one smallest rollback before
touching `src/core/task_intelligence.py`.

##### R4 result — no new selector repair

- All seven pre-registered BUG-045 negative and positive controls pass, including
  generic constraint rejection, project-name-only rejection, governing
  directive preservation, question-specific anchors, multi-term direct answers,
  and one-term factual answers.
- The shared Recall/answer-context slice passes 18 tests, and the complete Task
  Brief compiler suite passes 34 tests. No current failed causal stage exists.
- R4 therefore closes with no source or test edit to the already-dirty
  `src/core/task_intelligence.py` and `tests/test_task_intelligence.py` files.
  Moving a threshold after these passes would add risk and spend without an
  observed failure.

#### R5 eligibility decision — not entered

The current development task is not a valid independent outcome pair. Its
initial live `elefante-Recall` invocation returned HTTP `404` and supplied no
pre-existing decision-changing Elefante memory. Current source, workspace
instructions, and read-only audits—not a treatment memory—drove the work.
Creating a retrospective memory or reusing prior consumed evidence would violate
R5's pre-registration rule. Therefore no R5 treatment/control model run starts,
no acceptance outcome is relabelled, and representative lift remains unproven.

R6 may perform development closure and exact-archive construction tests. A real
replacement installation and normal-question Codex event remain separately
authorized operator/release acceptance and cannot be inferred from those tests.

#### Prior R6 checkpoint — development closure, not installed promotion

The following evidence describes the pre-reconciliation causal-repair checkout
at `d9aefb1e57fdaad1f4b69c826c83b408a0f07480`. It remains useful historical
proof, but it is not the verification result for the current v2.12.3
reconciliation candidate.

- Three non-overlapping affected lanes pass: 94 runtime/token/handshake tests
  with one intentional deselection, 91 installer/customer-archive tests, and 72
  selector/documentation tests. Total: 257 passed, one deselected.
- The isolated real MCP self-protocol passed 48/48 and deleted its temporary
  HOME/data. Its v2.12.2 banner matched that checkpoint's executable
  `src.__version__`; the current reconciliation source now declares 2.12.3.
- Pinned Ruff 0.1.15 passes every changed path and the new `src/mcp/server.py`
  logic when the committed file's 13 existing `E402`/`F401` findings are held
  constant. Running the same Ruff command against committed `HEAD` reproduces
  those 13 findings exactly. Compilation and `git diff --check` pass.
- Read-only installed proof remains negative: installed v2.12.3 doctor reports
  `customer_ready=true`, but the new independent bridge inspector completes the
  handshake, lists 16 tools, and reports `recall_tool_missing`. This is the
  false-positive readiness condition R2 repairs in development.
- Repository identity remains intentionally unreconciled: branch
  `agent/task-intelligence-causal-repair` is at
  `d9aefb1e57fdaad1f4b69c826c83b408a0f07480`, 20 commits ahead and nine behind
  `origin/main` at `14fda301b9c2c8f027a52bd1ffa23c36950f9da3`.
  Rebase/merge/version formation is release work and was not performed in this
  dirty checkout.

Development packages by mutation boundary:

| Package | Implementation boundary | Proof boundary |
|---|---|---|
| R1 | No product behavior change; customer archive contract only | Real Linux customer ZIP contains default-on Recall and routing agreement |
| R2a | Safe live Recall inspector plus doctor customer-readiness gate | Present/absent/unsafe/unavailable parser and doctor tests; installed missing-tool probe |
| R2b | Active Codex guidance precedence and verified host coverage | Later override masks stale base record without changing user bytes |
| R2c | Registration/guidance transaction rollback | New registration removed, prior owned registration restored, failed rollback reports `partial` |
| R3a | One contextual Recall call per question | Tool, prompt, installer, and built-archive wording agree |
| R3b | No question echo, Unicode response, 1,000-token complete cap | Supplied, no-match, multilingual, and oversized fail-closed cases |
| R3c | Exact hidden Recall payload/context estimates | Full token ledger suite; no `TOKEN_STATS` in customer response |
| R3d | Existing canonical references only | Full documentation routing, links, release split, and script inventory |
| R4 | No selector mutation | Current negative/positive controls and complete compiler suite pass |
| R5 | Not entered | No eligible pre-existing memory; no retrospective or consumed-evidence pair |

At that prior checkpoint, no commit, push, merge, version bump, archive
installation, host reconfiguration, durable-memory access/mutation, release, or
deployment occurred.

#### Current v2.12.3 reconciliation closure — verified pre-commit tree

- Current `origin/main` at
  `14fda301b9c2c8f027a52bd1ffa23c36950f9da3` and PR #25 head at
  `d9aefb1e57fdaad1f4b69c826c83b408a0f07480` were reconciled in the isolated
  local merge commit `46f5ef82961cbb62aa505a2b5364bbe78b359320`.
  The original 49-path dirty checkout remains untouched with status fingerprint
  `cd285fad7a2caa31b08c0c32c06445fe609dee14a1ab86f02918c4ad649fa8df`.
- The affected Recall, token, readiness, archive, selector, and documentation
  lane passes 263 tests with one intentional deselection. The complete fast
  collection passes 500 tests with four explicit legacy-backend skips and one
  slow-test deselection; that slow two-client bridge test passes separately.
- The isolated real MCP self-protocol passes 48/48 and removes its temporary
  HOME/data. Dashboard production build passes, both full and production npm
  audits report zero vulnerabilities, all four workflow files parse, version
  declarations agree on 2.12.3, and release-note validation plus 20 release
  pipeline tests pass.
- The model-free benchmark verifier reports no contract errors and correctly
  keeps promotion blocked. No eligible pre-existing memory existed for an R5
  outcome pair, so no model trial was invented and no representative lift is
  claimed.
- Ruff reports the same 13 `src/mcp/server.py` import-order/unused-import
  findings on the merge baseline and the reconciled tree; no changed line adds
  a lint finding. All changed Python files compile and diff hygiene passes.
- Installed acceptance remains negative: installed v2.12.3 still reports
  `customer_ready=true` while the real Recall invocation returned HTTP `404`.
  The local tests prove the candidate repair, not the installed runtime.

#### Exact local candidate artifact — verified and installed locally

- The implementation candidate is local commit
  `8b7cc5ba43b33b8c62cc80412359227ad8d2e9d9`. Its customer manifest and embedded
  `elefante-build.json` agree on version 2.12.3, clean source, candidate channel,
  and that exact full source commit.
- The maintained builder produced
  `dist/elefante-installer-macOS-8b7cc5b.zip`. The independent verifier passed
  with clean-source, candidate-channel, and macOS-platform requirements. Its
  SHA-256 is
  `2a8ca1cce8598d5dd4e72e4e3ba95455115a0eebffa42af9c06e5263a9da8041`.
- A second clean build was byte-identical and produced the same SHA-256. At the
  prior closure this proved deterministic packaging and provenance, not live
  customer readiness or Recall behavior.
- The exact archive was installed at 2026-08-26 17:08:48 EDT after the owned
  daemon was stopped. The data backup
  `/Users/jay/.elefante/backups/elefante_data_backup_20260826_210611.zip`
  passed checksum, ZIP integrity, and restore preflight; its SHA-256 is
  `18f44bb0822677cd06501e06f95f09470378f73def98ad37d90041cd90bf8826`.
  The previous runtime remains at
  `/Users/jay/.elefante/app/current.backup.20260826_170620`.
- Installed `doctor` now reports the exact candidate identity, 17 tools,
  read-only Recall annotations, `probe_status=supplied`, `recall.ready=true`,
  and `customer_ready=true`. An independent new stdio bridge reports the same
  17-tool/read-only/supplied result.
- Local installed-candidate Codex acceptance passed. This already-open task
  first retained its pre-upgrade MCP session and returned HTTP 404. A fresh
  ephemeral Codex process initialized a new bridge but emitted no model or tool
  event before the bounded run was terminated. One later, pre-documented
  graceful `TERM` removed only the stale task bridge; the immediate Recall event
  returned `Transport closed` while installed doctor and daemon health remained
  green. Without another mutation, Codex then spawned replacement bridge PID
  `58597` under the same app-server. Exactly one post-respawn normal question,
  `What is my Elefante test passcode?`, returned `isError=false`,
  `status=supplied`, `supplied_count=2`, `read_only=true`, and context containing
  the expected test fact. The observed context length was 673 characters, not a
  provider-token or billing measurement. Manual bridge termination remains an
  undocumented diagnostic; Codex Settings → MCP servers → Elefante → Restart is
  still the supported customer path.

Local implementation, exact artifact verification, recoverable local
installation, and one reattached normal-question Codex Recall event are
complete. Push, PR update, remote merge, release, and deployment remain outside
this closure; representative multi-task outcome lift remains separate and
unproven.

### 15.2 Token-financial operating rules

1. **Value before thrift.** One accepted outcome contributes one unit of value;
   a failed outcome contributes zero while retaining its full cost. Optimize
   accepted outcomes per million total tokens, never cheap failure.
2. **Count all observed spend.** Total-token accounting is input plus output for
   every completed attempt, including retries and unpaired early-stop work.
   Cached input is a subset of input and must not be counted twice.
3. **Separate tokens from money.** Elefante's `TOKEN_STATS` is a local heuristic,
   not provider billing. Dollar cost is reported only from actual provider usage
   and current rates: uncached input, cached input, and output are priced
   separately. If either usage or rates are unavailable, dollar cost is
   `UNKNOWN`.
4. **Spend model tokens last.** Tool inventory, governance, deterministic
   selection, delivery, no-mutation, and judge validity must pass model-free
   before an evaluation run. Invalid attempts are fixed or discarded before
   buying another pair.
5. **Keep Recall selective.** The current baseline is at most 12 candidates,
   three delivered memories, and a 450-token heuristic answer-context budget.
   These are ceilings, not proof of optimality. Reduce them only when positive
   controls retain accepted value; never fill a budget merely because it exists.
6. **Make abstention cheap and successful.** `no_match` is a valid read-only
   result. It must not trigger broad search substitution, full-store injection,
   repeated automatic retries, or a model call whose only purpose is to force a
   memory into the answer.
7. **Do not over-trigger the host.** Global guidance calls Recall at most once
   for a question that can materially depend on durable context and skips
   self-contained questions. A retry requires an observable transport failure,
   remains bounded, and is counted in total spend.
8. **Keep the comparison honest.** Hold task, source state, model, reasoning,
   tools, success criteria, timeout, and approval policy constant. Report both
   complete-pair efficiency and all observed spend so early stopping cannot hide
   cost.

### 15.3 Planned write ownership

- R1 owns the released MCP/artifact surface and its focused tests.
- R2 owns doctor/handshake readiness and installer-owned host-routing tests.
- R3 owns Recall payload and token-accounting tests; it does not add provider
  pricing to the product.
- R4 owns selector changes only after a specific failure is reproduced; the
  existing dirty `src/core/task_intelligence.py` and
  `tests/test_task_intelligence.py` must be preserved until that gate is reached.
- R5 uses the maintained evaluator and metadata-only ledger. It creates no new
  benchmark harness and writes no raw prompt, memory body, response, or source
  diff into the outcome store.
- R6 owns documentation and release verification only after behavior is proven.

The immediate authorized move after this plan is R0 read-only baseline proof,
then R1. No installed runtime, durable memory, host configuration, or remote
surface is part of the development write set.
