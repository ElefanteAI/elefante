# Token Intelligence

> **Status:** Released since v2.5.0. This reference describes the current
> source contract, not historical implementation work.

Elefante estimates the token size and protocol overhead of MCP calls. The
numbers are local heuristics for operational feedback; they are not provider
billing totals or exact model-token counts.

## Per-call response

Every tool response includes:

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

`RELEVANT_CONTEXT` is measured separately in the in-memory session ledger. It
is default-off, conditional, and is not counted as static protocol overhead.

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

## Verification

```bash
./.venv/bin/python -m pytest tests/test_token_intelligence.py -q
```

Source authorities:

- `src/utils/token_counter.py` — heuristic, budgets, and session ledger
- `src/mcp/server.py` — response injection and memory-add enrichment
- [`tools.md`](tools.md) — MCP response contract
