# Token Intelligence

> **Status:** Released since v2.5.0. This reference describes the current
> source contract, not historical implementation work.

Elefante estimates the token size and protocol overhead of MCP calls. The
numbers are local heuristics for operational feedback; they are not provider
billing totals, dollar-cost estimates, or exact model-token counts.

## Per-call response

Every normal non-Recall tool response includes:

```json
{
  "TOKEN_STATS": {
    "output_tokens": 847,
    "overhead_tokens": 312,
    "signal_ratio": 0.632
  }
}
```

- `output_tokens`: estimated response size including `TOKEN_STATS`.
- `overhead_tokens`: estimated protocol/directive/entrypoint overhead plus the
  stats block itself.
- `signal_ratio`: estimated non-overhead share of the response, clamped to
  `0.0–1.0`.

`elefante-Recall` intentionally returns a minimal customer payload; it keeps
token accounting internal rather than exposing `TOKEN_STATS` in that response.
For Recall, the ledger measures the input arguments, exact pretty Unicode
payload shown to the model, and returned `context` separately. Failed,
unavailable, and blocked calls still count as spend. The response does not echo
the question, keeps governed context within 450 heuristic tokens, and fails
closed if the complete response would exceed 1,000 heuristic tokens.
Any explicitly enabled tool-response context is measured separately in the
in-memory session ledger and is not counted as static protocol overhead. The
default customer profile uses Recall or the context prompt instead.

## Estimation method

`src/utils/token_counter.py` uses a character-ratio heuristic: about 3.5
characters per token for mostly ASCII text, blended toward 2.0 for text with a
higher non-ASCII share. It is deliberately fast and dependency-free.

Do not compare these values with an API invoice or use them as a strict model
context-limit gate.

## Memory density guidance

Successful `elefante-Memory(action="add")` responses include
`content_tokens` and `token_density`. A `density_warning` appears only when the
estimated content exceeds twice the advisory budget.

| Memory type | Advisory tokens |
|---|---:|
| `specification` | 800 |
| `insight` | 500 |
| `decision` | 400 |
| `preference` | 300 |
| `fact` | 250 |
| `directive` | 200 |
| `note` | 150 |
| `conversation` | 100 |

The default for an unknown type is 300. These budgets are advisory and do not
prove memory quality. A concise but wrong memory is still harmful; a longer
memory may be justified when it materially improves a task.

## MCP response ledger

`elefante-SystemStatusGet` exposes accumulated estimated input, output,
overhead, and context tokens for the current server instance. The ledger is
in-memory and resets when that instance restarts. Per-call `TOKEN_STATS` is
returned to the caller. The separate consented capture below can persist these
estimates; neither ledger turns them into billing or exact model usage.

The memory record persists `content_tokens` and `token_density` in its system
metadata. Website analytics and model-provider token accounting are separate
systems.

## Persistent Session Intelligence

The current release includes a separate, consent-gated, metadata-only SQLite
ledger, introduced in v2.13.0 and operated by
`scripts/pipeline/session_intelligence.py` or the loopback `/events/usage`
endpoint. It can retain provider-actual or estimated usage provenance, bounded
outcome records, dated rate cards, Signal Cards, and aggregate training
hypotheses. It rejects prompts, transcripts, responses, hidden reasoning, and
credentials.

Estimated usage never becomes provider-actual usage. Dollar cost remains
`UNKNOWN` unless an event contains provider-actual token counts and a matching
dated rate card is registered. Consent, export, retention, and deletion are
explicit per purpose.

### Automatic MCP capture

The runtime supports automatic capture at the shared MCP tool boundary.
Verify the installed build before expecting capture from an older package; use
the current release notes and the status command below.
It reuses the v2.13.0 ledger, not a new analytics store.

After local `usage_analytics` permission, each completed MCP dispatch queues one
metadata-only estimate: tool, opaque transport-session/event IDs, client label,
times, duration, result status and token sizes. A repeated real invocation counts
again; delivery of the same event ID does not. Successful abstention is success;
blocked/error results also count. Interrupted dispatches flag incomplete coverage
rather than inventing successful events. Invalid protocol requests rejected
before dispatch are outside this coverage.

No question, argument, response, memory ID, transcript, raw error or content
fingerprint is added to the usage event. Capture does not depend on an IDE or a
project. A transport session is not necessarily a chat. HTTP header/client
metadata and the existing stdio host identity supply provenance; unknown hosts
remain unknown. This source does **not** automatically collect provider/model
usage. Actual usage still needs a verified adapter sending metadata to
`/events/usage`; current-host actual coverage is unverified.

The writer queues at most 64 pending events per process, serializes persistence
off the MCP response path, rechecks consent on each write, and drains for at most
six seconds on normal shutdown. It never creates a ledger just by starting or
making a call. Queue overflow, interruption and persistence/snapshot failures are
reported as incomplete coverage, not retried tool operations. Abrupt process
termination can lose queued events; this is not a lossless billing ledger.

### Read the six dashboard values

Home → **Advanced: Session Intelligence** remains view-only. The snapshot covers
all retained events unless it was explicitly generated with narrower scope.
Three summary cards show **Recorded events**, **Usage cost**, and **Task result**.
Scope stays visible; **Usage details** holds token counts, exact evidence,
client/time provenance and technical reasons. **Suggestions** exposes the existing
hypotheses and counts. Both disclosures start closed; failure/pending/permission
warnings remain visible. Unavailable cost and unverified results use plain labels
in the summary, with `UNKNOWN` retained in evidence; no calculation changes.

| Value | Meaning |
|---|---|
| Usage observations | Recorded events, not tasks or model invocations. Actual and estimated observation counts are shown separately; overlapping observations must not be summed as model usage. Reload does not record an event. |
| Actual input / output tokens | Provider-reported counts only. No actual observation means `UNKNOWN`; a recorded zero is zero. Estimated argument/response/overhead sizes appear separately. Cached input is part of input, not extra input. |
| Verified cost | Known only when every covered event has complete actual usage and compatible dated rate-card evidence. Mixed estimates/actuals or missing rates keep the aggregate `UNKNOWN`. |
| Causal outcome | Accepted/rejected only from the existing comparable causal-outcome records. A user assertion or usage count alone does not establish benefit. |
| Training hypotheses | Number of provisional aggregate suggestions, with their statements and basis available in the disclosure. Missing report is `UNKNOWN`; an available empty report is zero. No model training or employee ranking occurs. |

Snapshot absence with no ledger means collection is off. Existing ledger with a
missing/broken snapshot means unavailable, not off or zero. The same-process
daemon adds content-free capture health (since, pending, failed and dropped
counts); the dashboard never opens the ledger. A refresh failure may leave a
saved event absent from the displayed totals. Standalone snapshot serving has no
live capture-health proof. Process health resets on restart; generation time is
not proof that all host activity was observed.
Permission failures describe the last attempted write, not necessarily current
permission: each new call rechecks consent, including after a fresh grant.

### Existing local controls

Run from the intended installed package with its Python environment. Use `--db`
and `--snapshot` for isolated tests; omit them only for the authorized configured
installation. These commands do not change semantic memories or graph data.

```bash
./.venv/bin/python scripts/pipeline/session_intelligence.py status
./.venv/bin/python scripts/pipeline/session_intelligence.py consent --purpose usage_analytics --purpose provider_usage --purpose enterprise_training --confirm ENABLE
./.venv/bin/python scripts/pipeline/session_intelligence.py snapshot
./.venv/bin/python scripts/pipeline/session_intelligence.py revoke
```

Grant only authorized purposes: local usage analytics, supplied provider usage,
and aggregate hypotheses respectively. Revoke stops new writes without deleting
retained evidence. Existing `export`, `delete` and `prune` commands provide data
controls; deletion requires an exact target and confirmation. Default event
retention is 30 days, applied when the ledger opens and by explicit pruning,
not by a continuous expiry service. No retroactive chat import, uploads, model
calls or hidden memory writes are part of activation.

For financial comparisons, count observed input plus output for every completed
attempt, including failures, retries, and unpaired early-stop work. Cached input
is a subset of input and must not be added twice. Elefante's estimates are not
provider usage: exact dollar cost remains unknown unless the provider supplies
actual uncached input, cached input, and output usage and those values are
multiplied by current rates.

## Verification

```bash
./.venv/bin/python -m pytest tests/test_token_intelligence.py tests/test_session_intelligence*.py tests/test_dashboard_ui.py -q
```

Source authorities:

- `src/utils/token_counter.py` — heuristic, budgets, and session ledger
- `src/mcp/server.py` — response injection and memory-add enrichment
- `src/session_intelligence/runtime.py` — consented capture and snapshot generation
- [`tools.md`](tools.md) — MCP response contract
