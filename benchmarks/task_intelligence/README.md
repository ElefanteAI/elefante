# Task Intelligence evaluation

This is developer-only evaluation infrastructure. It does not prove a public
product claim.

## Current truth

- The Task Intelligence **evaluation infrastructure is implemented**. It can
  validate judges, plan capped paired trials, record causal-stage metadata,
  summarize repeated outcomes, and fail promotion closed.
- `tasks.json` preserves 30 historical tasks and the v1 evidence record.
- Those tasks are **diagnostic-only** because many hidden tests require an
  undisclosed historical implementation shape. A behaviorally correct repair
  can therefore fail.
- Three tasks now have reviewed black-box canaries. Each canary fails at its
  exact base ref and passes at its exact known-good ref. The other 27 tasks
  remain ineligible, so the benchmark as a whole is not promotion-ready.
- Current causal result: **promotable correctness improvement has not been
  demonstrated**. CORS tied at 3/3 passes per condition. A later three-pair
  restore canary produced 0/3 control passes and 2/3 Task Brief passes, but it
  is one task, has no cross-task confidence interval, and exceeded the latency
  gate. It is a useful local signal, not a product claim.
- The current retrieval diagnostic reaches a historical repair path in 16/18
  calibration tasks. This measures navigation only, not task success.
- `--require-promotion-ready` fails closed until every selected task has an
  explicit behavioral acceptance contract and rollback refs.
- v2 Task Briefs are opt-in. v1 remains the default and its outcomes are stored
  under different filenames.
- Runner failures with no measurable model attempt abort instead of becoming
  task failures. Unobserved retry/correction counts are stored as `null`, never
  fabricated as zero.
- Each new schema-v2 outcome records judge, retrieval, selection, delivery,
  execution, and acceptance status plus SHA-256 evidence. Prompts, responses, memory
  bodies, and source diffs are not stored. Whether the agent actually used a
  delivered memory remains `UNKNOWN`.
- One-task reports return no clustered confidence interval. Resampling one task
  would create false certainty about performance on other tasks.
- Model execution against an invalid historical judge is blocked unless the
  operator explicitly passes `--allow-diagnostic`. Diagnostic results can
  never satisfy promotion.

## Golden path

1. Freeze a repository base commit and observable success criteria.
2. Use a black-box CLI, API, filesystem, or browser acceptance test. Do not
   require private symbols, source substrings, or arbitrary historical patch
   structure unless the task states that interface explicitly.
3. Give control and treatment the same model, tools, task, critical-reasoning
   protocol, limits, and disposable repository snapshot.
4. Give only the treatment a deterministic v2 Task Brief built from the base
   snapshot. Never read the acceptance ref while retrieving evidence.
5. Keep raw prompts, responses, and memory bodies out of outcome records.
6. Promote only after the manifest is promotion-ready, all paired runs are
   complete, correctness improves with a confidence interval excluding zero,
   and cost/privacy gates pass.

The frozen seed randomizes pair order; it does not make model output
deterministic. Use all required repetitions and never select a favorable run.
Disposable workspaces default to the short system-temp path
`elefante-ti/trial-<digest>` because longer repository paths caused the Codex
CLI to fail before a measurable attempt.

Every promotable task requires `acceptance_contract`:

```json
{
  "kind": "behavioral",
  "promotion_eligible": true,
  "observable_surface": ["documented CLI or API"],
  "acceptance": {
    "command": ["python", "-m", "pytest", "path::test", "-q"],
    "assertions": ["observable result, not implementation shape"]
  },
  "rollback": {
    "base_ref": "40-character pre-change SHA",
    "restore_ref": "the exact 40-character acceptance_ref SHA"
  },
  "adversarial_review": {
    "status": "approved",
    "implementation_coupling_found": false,
    "reviewer": "reviewer identifier",
    "reviewed_at": "YYYY-MM-DD",
    "test_sha256": "SHA-256 of the exact hidden test file"
  }
}
```

The review must inspect the assertions, not trust the contract label. The
verifier binds approval to the exact hidden-test digest so later test changes
invalidate promotion readiness.

## Commands

```bash
# Historical integrity: should pass, while reporting diagnostic_only=true.
python scripts/ci/verify_task_intelligence_benchmark.py

# Evaluator self-test: every eligible judge must fail on base and pass on fix.
python scripts/ci/verify_task_intelligence_benchmark.py --verify-canaries

# Promotion readiness: intentionally fails for the current historical set.
python scripts/ci/verify_task_intelligence_benchmark.py --require-promotion-ready

# Source-retrieval diagnostic. This is not task-outcome proof.
python scripts/ci/audit_task_intelligence_retrieval.py --split calibration

# Plan an isolated paired v2 run; no model runs without --execute and exact caps.
python scripts/ci/run_task_intelligence_evaluation.py \
  --task TASK_ID --brief-profile v2 --repetitions 1

# Execute only after the plan reports the exact two-run cost.
python scripts/ci/run_task_intelligence_evaluation.py \
  --task TASK_ID --brief-profile v2 --repetitions 1 --execute \
  --max-runs 2 \
  --max-total-input-tokens INPUT_CAP \
  --max-total-uncached-input-tokens UNCACHED_CAP

# Report fails unless every pair and every causal-stage trace is complete.
python scripts/ci/summarize_task_intelligence_evaluation.py \
  --brief-profile v2 --split calibration --require-complete

# Report one completed task without pretending it proves cross-task lift.
python scripts/ci/summarize_task_intelligence_evaluation.py \
  --brief-profile v2 --split calibration --task TASK_ID --require-complete

# Promotion is a separate, stricter gate and currently fails by design.
python scripts/ci/summarize_task_intelligence_evaluation.py \
  --brief-profile v2 --split holdout --require-promotion

# Diagnose one side only. This cannot support a causal or promotion claim.
python scripts/ci/run_task_intelligence_evaluation.py \
  --task TASK_ID --brief-profile v2 --condition task-brief --repetitions 1 \
  --allow-diagnostic
```

## Rollback

- Immediate evaluator rollback: omit `--brief-profile v2` or pass
  `--brief-profile v1`.
- v1 and v2 outcome filenames and disposable worktrees are isolated.
- A failed evaluation changes no branch or live memory. Delete only its
  disposable benchmark worktree after inspection.
- Before merge, return to the unchanged product with `git switch main`.
- After merge, revert the Task Intelligence commit; do not reset or rewrite
  shared history. Record the exact commit ID in the pull request.
- Do not reset or rewrite historical outcomes, tags, or commits.
