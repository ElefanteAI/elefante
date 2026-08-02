---
status: DRAFT
target: v3.0.0 (breaking change — explicit semver MAJOR)
authority: pre-implementation; supersedes nothing yet shipped
related:
  - workspace/PLANNING.md §2.5 (X1 rejected 3-tool facade)
  - workspace/PLANNING.md §2.5 (X6 rejected Hermes-specific profile)
  - CHANGELOG.md [2.10.0] (Memory atomic swap: 20 tools to 16)
  - docs/reference/tools.md (current 16-tool surface)
  - src/mcp/server.py (live tool registry)
---

# Tool Surface Consolidation — 16 → 6 Domain-Grouped Tools

## Question this PRD answers

**Can the agent-facing MCP tool surface shrink from 16 tools to 6 domain-grouped tools with discriminated-action parameters — without reproducing the failure modes that killed X1?**

## Problem

Today's source-derived surface (`python scripts/ci/list_mcp_tools.py`) is 16 tools:

| Domain (today) | Tools | Count |
|----------------|-------|-------|
| Memory | `Memory(action=add|search|update|delete|consolidate)` | 1 |
| Knowledge graph + context | `GraphConnect`, `GraphQuery`, `ContextGet`, `SessionsList` | 4 |
| Tasks | `TaskCreate`, `TaskUpdate`, `TaskGraph` | 3 |
| ETL pipeline | `ETLProcess`, `ETLClassify` | 2 |
| Directives | `DirectiveAdd`, `DirectiveList`, `DirectiveRemove` | 3 |
| System / dashboard | `SystemStatusGet`, `System`, `DashboardOpen` | 3 |

**The agent's cognitive load grows linearly with tool count.** Every tool adds a name to learn, a schema to read, and a decision to make. The v2.10.0 Memory atomic swap proved explicit action discrimination can reduce the surface without hiding behavior; the remaining five domains still pay fifteen schemas.

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
| **`Memory`** | Existing `Memory` tool (unchanged) | `add` \| `search` \| `update` \| `delete` \| `consolidate` | Already shipped in v2.10.0 |
| **`Knowledge`** | `GraphConnect`, `GraphQuery`, `ContextGet`, `SessionsList` | `graph_connect` \| `graph_query` \| `context` \| `sessions` | Graph + composite-context retrieval |
| **`Task`** | `TaskCreate`, `TaskUpdate`, `TaskGraph` | `create` \| `update` \| `read` | Task orchestration |
| **`Process`** | `ETLProcess`, `ETLClassify` | `process` \| `classify` | ETL / pipeline (see Async Pipeline note below) |
| **`Directive`** | `DirectiveAdd`, `DirectiveList`, `DirectiveRemove` | `add` \| `list` \| `remove` | Behavioral rules |
| **`System`** | `SystemStatusGet`, `System`, `DashboardOpen` | `status` \| `toggle` \| `dashboard` | System control + status |

**Surface reduction: 16 → 6 (62.5%).** The agent reads 6 schemas instead of 16. Action enums remain explicit and self-documenting.

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
| **v2.10.0** | 16 tools | Memory atomic swap shipped; no overlap window. |
| **v2.11.0** | 16 tools | Trust Release only; no further tool-surface change. |
| **v3.0.0** | 6 tools | **Atomic swap.** Replace the remaining 15 atomic domain tools with 5 domain tools in one release; the existing Memory tool remains. No alongside deployment. |

**Why no overlap window** (lesson learned 2026-05-02 — see "Migration trap" below): adding the five remaining domain tools while keeping their fifteen predecessors would increase the surface from 16 to 21. The deprecation-window pattern from libraries does not fit agent-facing surfaces where every schema consumes context before work starts.

**Atomic swap means**: at v3.0.0 cut, the remaining fifteen atomic domain tools are deleted in the same commit that introduces their five replacements. Clients pin to v2.x or v3.x, never both. This is a normal MAJOR-version contract break.

## Migration trap (learned 2026-05-02)

On 2026-05-02 a Phase-1 implementation was attempted: ship `elefante-Memory` (consolidated) **alongside** the 5 legacy memory tools as a deprecation overlap. Tool count went 20 → 21. **The cognitive load went UP, not down.** Reverted same day. Lesson: **a migration's first step that adds complexity without removing the old surface delivers NEGATIVE value during the entire transition window.** Either swap atomically or do not ship.

## Acceptance criteria

For v3.0.0 cut:

1. **Surface count.** `python scripts/ci/list_mcp_tools.py` reports exactly **6** tools.
2. **Behavioral parity.** Every action-discriminated call in v3.0.0 produces identical results to its v2.x predecessor (same memory-add semantics, same search ranking, same directive lifecycle).
3. **Compliance Gate parity.** Every gate that fires today on a v2.x tool fires identically on the v3.0.0 equivalent (`tool=Memory action=add` triggers the same `search-before-write` check that `MemoryAdd` triggers).
4. **Token-density measurement.** Average tool-schema overhead per MCP response drops by ≥50% (measure `TOKEN_STATS.overhead_tokens` before/after). This is the user-visible win.
5. **Migration test.** `tests/test_migration_v2_to_v3.py` exercises every old tool's contract via the new tool's action and asserts behavioral equivalence.
6. **Cross-client round trip.** A compatible host executes `Memory(action=search)` and each new domain action through the v3 surface.

## Async ingestion pipeline (related, but separable)

The user's earlier proposal also mentioned splitting `MemoryAdd`'s synchronous Intelligence Pipeline into async stages. This is **architecturally adjacent** to the tool consolidation but does **not** require it:

- **With or without the remaining consolidation:** `Memory(action="add", ...)` can write fast while the backend pipeline runs asynchronously. The concerns remain separable.

**Decision:** keep separable. Tool consolidation = v3.0.0 cut. Async pipeline = v3.0.x or v3.1 patch. Don't bundle.

## Open questions (P-series candidates for §2.6)

| Q | Architect lean | Needs user decision |
|---|----------------|---------------------|
| Is v3.0.0 the right version vehicle, or should this go to v2.20.0 with old tools as alias passthroughs? | v3.0.0 — surface contract change is MAJOR per `docs/how-to/close-a-feature.md`. | Yes |
| Should `Process` (ETL) merge into `Memory` as an `enrich` action, or stay as its own tool? | Stay separate — ETL operates on inbox queue, not on individual memory ops. Different lifecycle. | Yes |
| When should the remaining atomic swap occur? | Only after the v2.11.0 Trust Release, in v3.0.0. | Yes |
| Will Hermes / cross-client tool descriptions need a re-doc pass? | Yes — `docs/reference/tools.md` rewrites for 6 tools + per-action sub-sections. | (architect, no user gate) |

## What this proposal does NOT cover (out of scope, separate PRDs)

- **Async ingestion pipeline** (above — separate v3.0.x patch).
- **Schema versioning framework** (memories with `schema_version` field, forward-only migrations) — needed for any future field additions, separable.
- **GAP-025 daemon** (singleton owner of Kuzu) — shipped baseline; this PRD assumes it remains the storage authority.
- Any curated-write behavior belongs in the existing `Memory(action="add")` contract, not a seventeenth tool.

## Status

- **DRAFT** — pre-implementation. No code changes yet.
- **Promotes to** `docs/reference/tools.md` (rewritten for 6-tool surface) when shipped.
- **Cross-references** the shipped v2.10.0 Memory atomic swap plus X1 (three-tool facade rejected) and X6 (no client-specific memory semantics).

## Decision needed

Approve the remaining **atomic** 16 → 6 surface reduction for v3.0.0 after the Trust Release. No alongside deployment is permitted.
