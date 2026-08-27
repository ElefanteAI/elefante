# Token Intelligence

> **Status:** Released since v2.5.0. This reference describes the current
> source contract, not historical implementation work.

Elefante estimates the token size and protocol overhead of MCP calls. The
numbers are local heuristics for operational feedback; they are not provider
billing totals, dollar-cost estimates, or exact model-token counts.

## Per-call response

Every tool in the published v2.12.3 surface includes:

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

The unreleased customer candidate adds `elefante-Recall`. It intentionally
returns a minimal payload and keeps token accounting internal rather than
exposing `TOKEN_STATS` in that response. For Recall, the development ledger
measures the input arguments, exact pretty Unicode payload shown to the model,
and returned `context` separately. Failed, unavailable, and blocked calls still
count as spend. The response does not echo the question, keeps governed context
within 450 heuristic tokens, and fails closed if the complete response would
exceed 1,000 heuristic tokens. This candidate behavior is not part of the
published v2.12.3 tool surface.
`RELEVANT_CONTEXT` is measured separately in the in-memory session ledger. It
is default-off in the development pilot, conditional, and is not counted as
static protocol overhead.

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

## Session ledger

`elefante-SystemStatusGet` exposes accumulated estimated input, output,
overhead, and context tokens for the current server instance. The ledger is
in-memory and resets when that instance restarts. Per-call `TOKEN_STATS` is
returned to the caller and is not persisted as a billing or analytics record.

The memory record persists `content_tokens` and `token_density` in its system
metadata. Website analytics and model-provider token accounting are separate
systems.

For financial comparisons, count observed input plus output for every completed
attempt, including failures, retries, and unpaired early-stop work. Cached input
is a subset of input and must not be added twice. Elefante's estimates are not
provider usage: exact dollar cost remains unknown unless the provider supplies
actual uncached input, cached input, and output usage and those values are
multiplied by current rates.

These resource totals do not define accepted developer value or measure the
complete path from task start to acceptance. Per-call duration, model-run
duration, token count, and `signal_ratio` cannot by themselves support a claim
that Elefante helps a developer deliver more value in the same time or the same
value in less time. One explicit opt-in local development slice now implements
that contract across Session Intelligence and Task Intelligence, but it is not
automatic host instrumentation, representative lift, or part of the published
v2.12.3 Token Intelligence surface.

## Verification

```bash
./.venv/bin/python -m pytest tests/test_token_intelligence.py -q
```

Source authorities:

- `src/utils/token_counter.py` — heuristic, budgets, and session ledger
- `src/mcp/server.py` — response injection and memory-add enrichment
- [`tools.md`](tools.md) — MCP response contract
