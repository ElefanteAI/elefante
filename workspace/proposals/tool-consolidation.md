---
status: EXPLORING
target: unassigned
authority: design-only; current released surface remains 16 tools and 2 prompts
related:
  - docs/reference/tools.md
  - src/mcp/server.py
---

# Tool Surface Consolidation

## Question

Would reducing Elefante's 16 MCP tools to a smaller set of domain tools improve
task outcomes enough to justify a breaking public-contract change?

## Current truth

The released v2.12.2 surface is 16 tools and 2 prompts. Memory CRUD/search is
already consolidated under `elefante-Memory(action=...)`. No further tool
consolidation is approved, implemented, assigned to a version, or promised.

## Hypothesis

Five additional domain tools could replace the remaining graph/context, task,
ETL, directive, and system groups using explicit `action` discriminators. This
might reduce schema overhead and tool-selection errors.

That benefit is unproven. Fewer tool names could also create larger schemas,
invalid cross-action parameter combinations, weaker capability discovery, and
harder policy enforcement. Tool count alone is not a product metric.

## Non-negotiable constraints

1. No overlap window that exposes old and new surfaces together.
2. No hidden routing: action and applicable fields must remain explicit.
3. Compliance, read/write boundaries, and authorization must be equivalent or
   stronger.
4. Existing clients need a documented migration and rollback path.
5. The change must demonstrate lower decision/schema cost **and** equal or
   better task success across a representative evaluation.
6. A breaking release requires separate user approval and normal release gates.

## Evidence required before approval

- Source-derived schema-token comparison for the current and proposed surfaces.
- Agent tool-selection error rate across multiple real task types.
- Behavioral parity tests for every existing operation.
- Cross-host MCP round trips.
- An explicit compatibility and rollback plan.
- Task Intelligence evidence that consolidation improves outcomes rather than
  merely reducing a count.

Until that evidence exists, keep the 16-tool surface documented in
[`docs/reference/tools.md`](../../docs/reference/tools.md) and derive its exact
inventory with:

```bash
./.venv/bin/python scripts/ci/list_mcp_tools.py
```
