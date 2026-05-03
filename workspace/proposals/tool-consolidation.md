---
status: DRAFT
target: v3.0.0 (breaking change — explicit semver MAJOR)
authority: pre-implementation; supersedes nothing yet shipped
related:
  - workspace/PLANNING.md §2.3 (A2 preserves 20 tools in v2.10.0)
  - workspace/PLANNING.md §2.5 (X1 rejected 3-tool facade)
  - workspace/PLANNING.md §2.5 (X6 rejected Hermes-specific profile)
  - docs/reference/tools.md (current 20-tool surface)
  - src/mcp/server.py (live tool registry)
---

# Tool Surface Consolidation — 20 → 6 Domain-Grouped Tools

## Question this PRD answers

**Can the agent-facing MCP tool surface shrink from 20 atomic tools to 6 domain-grouped tools with discriminated-action parameters — without reproducing the failure modes that killed X1?**

## Problem

Today's surface (verified `grep -c 'types.Tool(' src/mcp/server.py` = 20):

| Domain (today) | Tools | Count |
|----------------|-------|-------|
| Memory primitives | `MemoryAdd`, `MemorySearch`, `MemoryUpdate`, `MemoryDelete`, `MemoryConsolidate` | 5 |
| Knowledge graph + context | `GraphConnect`, `GraphQuery`, `ContextGet`, `SessionsList` | 4 |
| Tasks | `TaskCreate`, `TaskUpdate`, `TaskGraph` | 3 |
| ETL pipeline | `ETLProcess`, `ETLClassify` | 2 |
| Directives | `DirectiveAdd`, `DirectiveList`, `DirectiveRemove` | 3 |
| System / dashboard | `SystemStatusGet`, `System`, `DashboardOpen` | 3 |

**The agent's cognitive load grows linearly with tool count.** Every tool adds a name to learn, a schema to read, a decision to make. Twenty tools means twenty schema descriptions auto-injected into every agent context. Discoverability + retention degrade. New features hit a hard ceiling: every new capability adds another tool, another schema, more tokens consumed before any work begins.

## Why X1 was rejected (cited verbatim from PLANNING.md §2.5)

> "**X1**: 3-tool facade replacing 20 MCP tools | **Lossy hidden routing; doubles maintenance; breaks Compliance Gate visibility; Tasks/ETL not memory primitives**"

Four objections, each independently fatal to X1:

| # | X1 Objection | Why this proposal does not reproduce it |
|---|--------------|------------------------------------------|
| 1 | **Lossy hidden routing** — 3 tools hiding 20 behaviors behind opaque dispatch | This proposal exposes the action discriminator in the schema. `Memory(action="search", ...)` is just as visible to the agent and the Compliance Gate as `MemorySearch(...)`. Routing is **explicit**, not hidden. |
| 2 | **Doubles maintenance** — one tool, many implementation paths, hard to test | Per-action discriminated unions are a normal pattern (used in OpenAI's function calling, JSON-Schema discriminator). Each action gets its own sub-schema and its own test, scoped by `action` value. Not double — same. |
| 3 | **Breaks Compliance Gate visibility** — gate logic cannot see what the agent is doing | Action param **IS** the visibility. Gate inspects `arguments.action` exactly as it inspects `tool.name` today. The Compliance Gate code path becomes `if tool == "Memory" and action == "add": gate(...)` — equivalent fidelity. |
| 4 | **Tasks/ETL not memory primitives** — forcing them into the same facade conflates domains | This proposal **does not** force them together. Tasks → `Task` tool. ETL → `Process` tool. They stay separate domain tools, not jammed into a memory facade. |

**Conclusion: X1's rejections were correct for X1's design. They do not apply to a domain-grouped 6-tool design with explicit action discriminators.** The differences are structural, not cosmetic.

## The 6-tool proposal

| New tool | Replaces (today) | Action values | Notes |
|----------|------------------|---------------|-------|
| **`Memory`** | `MemoryAdd`, `MemorySearch`, `MemoryUpdate`, `MemoryDelete`, `MemoryConsolidate` | `add` \| `search` \| `update` \| `delete` \| `consolidate` | Primary agent surface for memory I/O |
| **`Knowledge`** | `GraphConnect`, `GraphQuery`, `ContextGet`, `SessionsList` | `graph_connect` \| `graph_query` \| `context` \| `sessions` | Graph + composite-context retrieval |
| **`Task`** | `TaskCreate`, `TaskUpdate`, `TaskGraph` | `create` \| `update` \| `read` | Task orchestration |
| **`Process`** | `ETLProcess`, `ETLClassify` | `process` \| `classify` | ETL / pipeline (see Async Pipeline note below) |
| **`Directive`** | `DirectiveAdd`, `DirectiveList`, `DirectiveRemove` | `add` \| `list` \| `remove` | Behavioral rules |
| **`System`** | `SystemStatusGet`, `System`, `DashboardOpen` | `status` \| `toggle` \| `dashboard` | System control + status |

**Surface reduction: 20 → 6 (70%).** Agent reads ~6 schemas instead of ~20. Action enums are short and self-documenting.

## Per-tool action schema sketch

Example: `Memory` tool with discriminated action.

```jsonschema
{
  "type": "object",
  "required": ["action"],
  "oneOf": [
    {
      "properties": {
        "action": { "const": "add" },
        "content": { "type": "string" },
        "memory_type": { "enum": ["fact", "rule", "preference", "specification", "directive", "note"] },
        "tags": { "type": "array", "items": { "type": "string" } },
        "category": { "type": "string" },
        "score": { "type": "integer", "minimum": 0, "maximum": 100 }
      },
      "required": ["action", "content"]
    },
    {
      "properties": {
        "action": { "const": "search" },
        "query": { "type": "string" },
        "max_results": { "type": "integer", "default": 10 },
        "min_similarity": { "type": "number", "default": 0.5 }
      },
      "required": ["action", "query"]
    },
    /* update / delete / consolidate sub-schemas */
  ]
}
```

The agent sees a single tool `Memory`. The schema names exactly which fields apply to which action. The Compliance Gate inspects `arguments.action` to apply per-action policy (e.g. `search-before-write` enforced when `action == "add"`).

## Migration plan (atomic swap, no overlap window)

| Version | Tool surface | Discipline |
|---------|--------------|------------|
| **v2.10.x** | 20 tools (per A2) | No change. PRDs describe the future. |
| **v2.11.0** | 20 tools | No tool-surface change. Daemon + Source schema (GAP-025 closure). |
| **v3.0.0** | 6 tools | **Atomic swap.** Delete the 20 legacy tools in the SAME release that introduces the 6 consolidated tools. No alongside-deployment, no deprecation overlap window. Migration guide in `docs/how-to/migrate-v2-to-v3.md`. |

**Why no overlap window** (lesson learned 2026-05-02 — see "Migration trap" below): an alongside-deployment that adds the consolidated tool while keeping the legacy tools INCREASES tool count + token overhead during the entire window. Tool count would go 20 → 26 (20 + 6 new), which is the opposite of the consolidation goal. Agents would have multiple ways to add a memory (legacy `MemoryAdd` AND `Memory(action=add)`), increasing decision load. The deprecation-window pattern from library migrations does not apply to agent-facing surfaces where every tool schema is paid in tokens on every response.

**Atomic swap means**: at v3.0.0 cut, the 20 legacy tools are deleted in the same commit that introduces the 6 consolidated tools. Clients pin to v2.x or v3.x — never both. Migration guide is the only bridge. This is a normal MAJOR-version semver break, not an unusual one.

## Migration trap (learned 2026-05-02)

On 2026-05-02 a Phase-1 implementation was attempted: ship `elefante-Memory` (consolidated) **alongside** the 5 legacy memory tools as a deprecation overlap. Tool count went 20 → 21. **The cognitive load went UP, not down.** Reverted same day. Lesson: **a migration's first step that adds complexity without removing the old surface delivers NEGATIVE value during the entire transition window.** Either swap atomically or do not ship.

## Acceptance criteria

For v3.0.0 cut:

1. **Surface count.** `grep -c 'types.Tool(' src/mcp/server.py` returns exactly **6**.
2. **Behavioral parity.** Every action-discriminated call in v3.0.0 produces identical results to its v2.x predecessor (same memory-add semantics, same search ranking, same directive lifecycle).
3. **Compliance Gate parity.** Every gate that fires today on a v2.x tool fires identically on the v3.0.0 equivalent (`tool=Memory action=add` triggers the same `search-before-write` check that `MemoryAdd` triggers).
4. **Token-density measurement.** Average tool-schema overhead per MCP response drops by ≥50% (measure `TOKEN_STATS.overhead_tokens` before/after). This is the user-visible win.
5. **Migration test.** `tests/test_migration_v2_to_v3.py` exercises every old tool's contract via the new tool's action and asserts behavioral equivalence.
6. **Hermes round-trip test.** `hermes -z "use Memory action=search to find lifecycle"` works the same as today's `hermes -z "use elefante-MemorySearch ..."` works.

## Async ingestion pipeline (related, but separable)

The user's earlier proposal also mentioned splitting `MemoryAdd`'s synchronous Intelligence Pipeline into async stages. This is **architecturally adjacent** to the tool consolidation but does **not** require it:

- **With consolidation (v3.0.0):** `Memory(action="add", ...)` writes fast; backend pipeline (extractor, classifier, linker, reinforcer) runs async; results land as additive fields with `schema_version`.
- **Without consolidation:** the same async split could happen behind today's `MemoryAdd`. The agent sees no difference.

**Decision:** keep separable. Tool consolidation = v3.0.0 cut. Async pipeline = v3.0.x or v3.1 patch. Don't bundle.

## Open questions (P-series candidates for §2.6)

| Q | Architect lean | Needs user decision |
|---|----------------|---------------------|
| Is v3.0.0 the right version vehicle, or should this go to v2.20.0 with old tools as alias passthroughs? | v3.0.0 — surface contract change is MAJOR per `docs/how-to/close-a-feature.md`. | Yes |
| Should `Process` (ETL) merge into `Memory` as an `enrich` action, or stay as its own tool? | Stay separate — ETL operates on inbox queue, not on individual memory ops. Different lifecycle. | Yes |
| Should v2.11.0 ship the new 6-tool surface alongside, or wait for v3.0.0 cutover? | Ship alongside in v2.11.0 — gives one release of soak time + migration validation. | Yes |
| Will Hermes / cross-client tool descriptions need a re-doc pass? | Yes — `docs/reference/tools.md` rewrites for 6 tools + per-action sub-sections. | (architect, no user gate) |

## What this proposal does NOT cover (out of scope, separate PRDs)

- **Async ingestion pipeline** (above — separate v3.0.x patch).
- **Schema versioning framework** (memories with `schema_version` field, forward-only migrations) — needed for any future field additions, separable.
- **GAP-025 daemon** (singleton owner of Kuzu) — already planned for v2.11.0; this PRD assumes it ships first.
- **`elefante-Remember` curated write primitive** (per A5 in v2.10.0) — already planned, lands in v2.10.x as a 21st tool, then folds into `Memory(action="add", curated=true)` at v3.0.0.

## Status

- **DRAFT** — pre-implementation. No code changes yet.
- **Promotes to** `docs/reference/tools.md` (rewritten for 6-tool surface) when shipped.
- **Cross-references** A2 (v2.10.0 preserves 20), A9 (Hermes generic), X1 (3-tool facade rejected — this is structurally different), X6 (no special profile per consumer — this proposal is consumer-agnostic).

## Decision needed

**P7 (proposed addition to PLANNING.md §2.6):** Approve this proposal for v3.0.0 inclusion + v2.11.0 alongside-deployment? Architect recommendation: **YES** — six tools is a measurable win on cognitive load + token overhead; the X1 objections do not apply; the migration window aligns with existing v2.11.0 daemon work.
