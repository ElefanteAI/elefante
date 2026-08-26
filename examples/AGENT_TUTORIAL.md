# Elefante Agent Tutorial

> **Release:** v2.12.3
> **Audience:** AI agents connected through MCP

Elefante exposes 16 tools and 2 lowercase prompts. Tools use
`elefante-PascalCase`; prompts are `elefante-context` and
`elefante-grounding`.

## 1. Check status

Call `elefante-SystemStatusGet` with `{}`. `elefante-System(action="enable")`
can preload the runtime and set the logical mode, but normal operations use
transaction-scoped storage ownership; it does not reserve a session-wide
database lock.

## 2. Search when prior context matters

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

```json
{
  "action": "add",
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

## 4. Update or remove

- Update: `elefante-Memory` with `action="update"`, `memory_id`, and only the
  fields that should change. Use `supersedes_id` when a newer decision replaces
  an older one.
- Delete: `elefante-Memory` with `action="delete"`, `memory_id`, and a reason.
- Consolidate: start with `action="consolidate"` and `force=false`. Current
  consolidation is deterministic duplicate cleanup, not general automatic
  forgetting.

## 5. Interpret results correctly

- SQLite vectors plus Kuzu are the released default; legacy ChromaDB is only an
  explicitly configured support path.
- `RELEVANT_CONTEXT` may be appended to eligible operations. It is
  supplementary and not proof that the memory helped.
- Specifications and directives have zero type decay, but freshness still
  affects vitality.
- When memory conflicts with current source or a newer verified fact, explain
  the conflict and prefer evidence. If a project-specific claim is not
  grounded, mark that claim UNKNOWN.

## 6. Verify the live surface

```bash
./.venv/bin/python scripts/ci/list_mcp_tools.py
./.venv/bin/python scripts/verify/verify_mcp_handshake.py
```

Full schemas and response contracts are in
[`../docs/reference/tools.md`](../docs/reference/tools.md).
