<!--
Annotated excerpt from docs/technical/spec-tools.md.
This file was the target of a 13-item audit, but it is not the blocker now.
The current doc already matches the live MCP surface.
-->

# Excerpt: docs/technical/spec-tools.md

## Current MCP Surface

<!--
Supposed to do:
state the live tool and prompt counts from src/mcp/server.py.

Current status:
correct. This closes the old "21 tools" / prompt-count drift claim.
-->
Elefante exposes **20 tools** and **2 prompts**.

## MemoryAdd excerpt

<!--
Supposed to do:
document permanent memory types and their meaning.

Current status:
correct. specification and directive are already present.
-->
- `specification` and `directive` never decay.
- `memory_type` (optional, string, default `fact`): `fact`, `decision`, `preference`, `insight`, `note`, `conversation`, `specification`, or `directive`.

## Parameter coverage excerpt

<!--
Current status:
correct. These lines already cover the parameters that were previously reported missing.
Do not reopen this audit without first diffing src/mcp/server.py.
-->
- `include_system_status` (optional, boolean, default `false`): Include `elefante-SystemStatusGet` output in the response.
- `parameters` (optional, object): Parameter values for the query.
- `session_id` (optional, string): Session UUID when the caller wants context tied to a specific session.
- `offset` (optional, integer, default `0`): Pagination offset.
- `parent_id` (optional, string): Parent task UUID for subtask relationships.
- `blocked_by` (optional, string[]): Task IDs that must complete first.
- `force` (optional, boolean, default `false`): Force-enable despite a lock conflict.

## ETL and dashboard excerpt

<!--
Supposed to do:
document the live ETL workflow and the dashboard mode dependency.

Current status:
correct. This part is not the blocker.
-->
1. Call `elefante-ETLProcess`.
2. Read each raw memory.
3. Call `elefante-ETLClassify` for each one.

- `refresh=true` reads from live databases and requires Elefante Mode to be enabled.

## Operational best practices excerpt

<!--
Current status:
correct. These lines closed the previous workflow-guidance drift claim.
-->
1. **Search before write**: Run `elefante-MemorySearch` before `MemoryAdd`, `MemoryUpdate`, `MemoryDelete`, or `GraphConnect`.
3. **Use `list_all` deliberately**: It is browse/export mode, not a replacement for a targeted relevance search.
7. **Treat ETL as a pair**: `ETLProcess` fetches raw memories; `ETLClassify` is what actually improves future retrieval.
8. **Refresh the dashboard only when mode is active**: `DashboardOpen(refresh=true)` touches live data.