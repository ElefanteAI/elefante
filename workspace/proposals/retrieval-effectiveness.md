# North Star / Implementation PRD: Task Intelligence

> Status: NORTH STAR — FIRST BOUNDED FEASIBILITY EXPERIMENT COMPLETE (`STOP`)
>
> Product state: governed Recall, Task Brief v2, evaluation, and a metadata-only
> outcome ledger exist in unreleased development. Representative task lift is
> not proven.
>
> Canonical role: this file owns the Task Intelligence objective, the immediate
> experiment, its evidence gates, and the boundary to later product work.
>
> Current implementation baseline: `7c705ca03371771be68460afb270fe0998f30231`.
> Published customer release:
> v2.12.2. This document authorizes neither merge nor release.

## 0. Resume contract — do not restart the debate

A future developer starts here, not from the conversation that produced this
PRD.

- The objective is accepted: durable memory must measurably improve an eligible
  task's accepted answer or action.
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
- The next action is the replacement-task screen in §14. Product code remains
  unchanged until a different reproducible causal failure is demonstrated.

If new evidence contradicts this contract, update this canonical PRD and its
planning index in the same change. Do not silently route around it.

## 1. North Star

> **For an eligible memory-dependent task, Elefante must cause a better accepted
> answer or action by supplying the smallest safe set of applicable durable
> memories.**

A task may be a question, decision, plan, code change, or validation action.
Persistence, retrieval, lower token use, and agent acknowledgement are not the
outcome. They are mechanisms or diagnostics.

Priority order:

1. privacy, user authority, scope correctness, and recoverability;
2. observable task correctness;
3. tokens, retries, corrections, latency, and cost;
4. retrieval and delivery diagnostics.

Efficiency never compensates for unchanged correctness. Correctness never
compensates for a trust violation.

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
resolution was the first causal failure.

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
| Measured token cost | Five completed outcomes: 1,417,856 input; 1,112,064 cached; 305,792 uncached; 83,452 output. Exact partial usage from the terminated sixth attempt is `UNKNOWN`. |

The memory was architecturally relevant but not causally discriminative. It
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

## 14. Immediate goal

> **Your goal is to preserve the proven explicit search→write→Recall path, then
> select one independently arising task where a pre-existing memory contains a
> decision-relevant fact absent from source-only evidence. Prove that difference
> model-free before any paired model run.**

The capture and delivery gate is complete; task lift is not. If no eligible task
exists, stop and wait rather than inventing one, changing retrieval, or spending
model tokens.
