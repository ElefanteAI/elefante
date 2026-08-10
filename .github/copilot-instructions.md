# Use Elefante as a Task Memory

Elefante is a local-first memory service. Use it to improve the current task
with relevant prior decisions, preferences, facts, and evidence. Retrieval is
input to reasoning, not proof that a memory is correct.

## When to retrieve

Call `elefante-Recall` before answering when the request may depend on:

- the user's preferences or enforced instructions;
- earlier project decisions, constraints, or unresolved problems;
- work performed in another session, IDE, or agent host.

Pass the complete standalone question with named projects, files, people, and
concepts. Recall returns only a bounded governed context or abstains. Use
`elefante-Memory(action="search")` for broad inspection and before memory
mutations. Do not fetch memory for a self-contained question that cannot benefit
from prior context.

## How to reason with results

1. Compare each memory with current source evidence and the user's present
   request.
2. Prefer current, source-grounded, non-archived records. Surface conflicts;
   do not silently choose the agreeable result.
3. Agreement is not evidence. Challenge weak assumptions and mark unresolved
   facts as `UNKNOWN`.
4. Use the smallest relevant memory set. Irrelevant context can reduce task
   quality even when retrieval succeeds.
5. Never claim that Elefante improved a task unless a task-level comparison
   measured the outcome.

## When to write

Search first; the MCP Compliance Gate requires it. Then write only durable,
useful information that the user requested or that the active task clearly
needs across sessions.

- `add`: a new decision, preference, verified fact, reusable insight, or
  durable specification.
- `update`: correct or supersede an existing record.
- `delete`: permanently remove a false, unsafe, or explicitly unwanted record.
- `consolidate`: inspect deterministic duplicate cleanup with `force=false`
  before applying it.

Do not store secrets, raw credentials, speculative conclusions, routine chat,
or every interaction. User-directed retention has priority. Automatic user
locks and mandatory injection policies are not part of the v2.12.2 runtime.

## Choose the memory type deliberately

| Type | Use |
|---|---|
| `specification` | Durable architecture, schema, or contract truth |
| `directive` | A stored behavioral memory; use Directive tools for active rules |
| `preference` | Stable user preference |
| `decision` | A choice that should shape later work |
| `fact` | A verified fact that may change |
| `insight` | A reusable pattern supported by evidence |
| `note` | Short-lived working context |
| `conversation` | Ephemeral session context |

Specification and directive memories have zero type-specific decay, but
freshness still affects their vitality. They are not automatically immutable or
injected into every response. Active rules belong in the separate Directive
store.

## Current MCP surface

Published Elefante v2.12.2 exposes 16 tools and 2 prompts. The unreleased
customer candidate adds the default-on, read-only `elefante-Recall` path; it is
not a published release claim.

- Memory: `elefante-Recall`, `elefante-Memory`
- Context and graph: `elefante-ContextGet`, `elefante-GraphQuery`,
  `elefante-GraphConnect`
- Sessions and tasks: `elefante-SessionsList`, `elefante-TaskCreate`,
  `elefante-TaskUpdate`, `elefante-TaskGraph`
- Optional agent ETL: `elefante-ETLProcess`, `elefante-ETLClassify`
- Directives: `elefante-DirectiveAdd`, `elefante-DirectiveList`,
  `elefante-DirectiveRemove`
- Runtime: `elefante-System`, `elefante-SystemStatusGet`,
  `elefante-DashboardOpen`
- Prompts: `elefante-grounding`, `elefante-context`

Normal product-operation responses include active directives and protocol
guidance. Management responses use a minimal path. Every response includes
heuristic `TOKEN_STATS`; `RELEVANT_CONTEXT` is conditional.

## Safety and boundaries

- The Elefante store remains local. Content intentionally sent to a connected
  AI provider is governed by that provider's policy.
- Never place passwords, API keys, private keys, tokens, or unnecessary
  sensitive personal data in memory.
- Do not expose the loopback daemon or dashboard directly to a public network.
- Do not mutate, delete, reset, publish, deploy, or contact third parties
  without the authority required by the user's request.

For exact tool schemas, see `docs/reference/tools.md`. For operation and
recovery, use `docs/how-to/`.
