# Advanced Elefante Agent Integration

> **Release:** v2.15.2
> **Audience:** AI agents connected through MCP

Elefante exposes 18 customer tools and 2 lowercase prompts. Tools use
`elefante-PascalCase`; prompts are `elefante-context` and
`elefante-grounding`.

## 1. Check status

Call `elefante-SystemStatusGet` with `{}`. `elefante-System(action="enable")`
can preload the runtime and set the logical mode, but normal operations use
transaction-scoped storage ownership; it does not reserve a session-wide
database lock.

## 2. Recall when prior context matters

Call `elefante-Recall` at most once with the complete standalone question.
Treat `no_match`, `blocked`, and `unavailable` as terminal for that answer. Do
not retry with broader wording, and do not call Recall for a self-contained
question.

Use `elefante-Memory(action="search")` when you need broader inspection or are
preparing a write:

Call `elefante-Memory` with:

```json
{
  "action": "search",
  "query": "user communication preferences for technical release updates",
  "limit": 5
}
```

Use concrete entities and intent. `list_all: true` is for browsing/export, not
semantic ranking. Search is also required before memory writes by the
Compliance Gate.

## 3. Add durable knowledge

Use this example only if the user has actually confirmed the preference and
authorized saving it. Search first; do not ingest tutorial text as user knowledge.

```json
{
  "action": "add",
  "invocation_mode": "user_directed",
  "content": "The user prefers concise release updates with verification evidence.",
  "memory_type": "preference",
  "domain": "personal",
  "category": "communication",
  "tags": ["preference", "release", "communication"]
}
```

The supported memory types are `fact`, `decision`, `preference`, `insight`,
`note`, `conversation`, `specification`, and `directive`. Do not provide a
manual score. The Elefante runtime initializes metadata and later ranking uses semantic,
concept, co-activation, authority, and temporal signals.

Store only information that is durable, attributable, and likely to matter
again. Do not store secrets, unsupported conclusions, temporary progress, or a
second copy of existing memory.
After a successful write, run Recall with a likely future question, such as
“How should I present a release update?” Report selection or abstention honestly.
Use the host's exact project/workspace boundary; never invent a prose scope.

## 4. Update or remove

- Correct: use `elefante-Memory(action="correct")`, the exact `memory_id`, and
  `correction="edit"`, `"replace"`, `"archive"`, `"restore"`, `"resolve"`, or
  `"permanent_delete"`. Inspect with `apply=false` first. On authorized apply,
  supply its exact hashes, reason and verification question. Inspect the final
  receipt; a planned or attempted write is not completion.
- Prefer Archive for recoverable removal. Permanent deletion requires separate
  confirmation and a verified safety backup. Legacy content/lifecycle update
  and delete calls are not substitutes for this verified correction boundary.
- Consolidate: start with `action="consolidate"` and `force=false`. Current
  consolidation is deterministic duplicate cleanup, not general automatic
  forgetting.

## 5. Interpret results correctly

- SQLite vectors plus Kuzu are the released default; legacy ChromaDB is only an
  explicitly configured support path.
- `RELEVANT_CONTEXT` is disabled in the customer profile. Recall and the
  context prompt are the explicit bounded delivery paths.
- Specifications and directives have zero type decay, but freshness still
  affects vitality.
- When memory conflicts with current source or a newer verified fact, explain
  the conflict and prefer evidence. If a project-specific claim is not
  grounded, mark that claim UNKNOWN.

## 6. Verify the live surface

In the installed customer product, use a fresh configured host to list its MCP
tools and call `elefante-SystemStatusGet`, then run a read-only Recall check.
The following **developer-only checkout commands** inspect source declarations and
an isolated protocol handshake; they do not prove that a customer host is connected:

```bash
./.venv/bin/python scripts/ci/list_mcp_tools.py
./.venv/bin/python scripts/verify/verify_mcp_handshake.py
```

Full schemas and response contracts are in
[`../docs/reference/tools.md`](../docs/reference/tools.md).
