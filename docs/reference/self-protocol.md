# Self-Elefante Protocol

> **Purpose:** Prove that Elefante is actually running as a live MCP system, not just that a few narrow regressions are green.
> **Authoritative runner:** `./.venv/bin/python scripts/verify/verify_e2e_tests.py`

---

## Why This Exists

The current verification stack is layered on purpose:

- Targeted `pytest` files prove specific contracts.
- `scripts/verify/verify_health.py` proves structural readiness.
- `scripts/verify/verify_mcp_handshake.py` proves stdio JSON-RPC handshake.

That stack is valid. It is not sufficient when the question is broader:

> "Is Elefante actually running end-to-end as a real MCP server?"

That question requires a live subprocess, the real MCP tool/prompt surface, real state mutation, restart persistence, and cleanup inside an isolated store.

This document defines that whole-system proof.

---

## Hard Rule

Do not create parallel scratch harnesses for this question.

If the whole-system proof is stale or incomplete, extend `scripts/verify/verify_e2e_tests.py`. Do not build a second verifier that will drift.

---

## Safe Default Run

```bash
./.venv/bin/python scripts/verify/verify_e2e_tests.py
```

Default mode is intentionally self-contained:

- Uses temporary `HOME`, `USERPROFILE`, and `ELEFANTE_DATA_DIR`
- Enables `ELEFANTE_ALLOW_TEST_MEMORIES=1`
- Verifies **19 of 20 tools** plus **both prompts**
- Deletes protocol-created memories through the tool surface
- Removes the entire temporary Elefante store at the end

### Default Exclusion

`elefante-DashboardOpen` is excluded by default.

Reason:

- It binds fixed port `8000`
- It attempts to open a browser
- Those side effects are outside the isolated temp store

That means it is not fully self-contained, so it cannot be part of the default safe sweep.

---

## Opt-In Full Surface Run

```bash
./.venv/bin/python scripts/verify/verify_e2e_tests.py --with-dashboard-open
```

Use this only when you explicitly want tool 20 checked.

Preconditions:

- Port `8000` must be free before the harness starts
- You accept a short-lived dashboard subprocess during the run

Runtime behavior:

- The harness preflights port `8000`
- Browser launch is stubbed with `BROWSER=/usr/bin/true`
- The dashboard server is killed during cleanup
- Snapshot verification must follow the live runtime path, which may be the `HOME`-derived `~/.elefante/data/dashboard_snapshot.json` path used by `src.mcp.server`

If you do not need the `elefante-DashboardOpen` tool itself, do not run this mode.

---

## What The Protocol Proves

The authoritative harness verifies these phases in order:

1. **Handshake and inventory**
   The real MCP server boots, completes `initialize`, and exposes the expected 20-tool plus 2-prompt surface.
2. **Prompt retrieval**
   `elefante-grounding` and `elefante-context` both return usable content over the live prompt surface.
3. **Routing and directives**
   Successful and failing tool calls both inject `DIRECTIVES` and `ENTRYPOINT_SEQUENCE_READ_THIS_FIRST`.
4. **System compatibility**
   `elefante-SystemStatusGet` and `elefante-System` behave correctly under transaction-scoped mode.
5. **Directive lifecycle**
   Add, list, and remove all work against the real persistent directive store.
6. **Compliance Gate**
   A fresh session with no prior search cannot mutate memory.
7. **Memory lifecycle**
   `MemoryAdd`, `MemorySearch`, `list_all`, `MemoryUpdate`, and `MemoryDelete` all round-trip through the live store.
8. **Graph and context**
   `GraphConnect`, `GraphQuery`, `ContextGet`, and `SessionsList` all return meaningful state derived from protocol-created entities.
9. **Task graph**
   `TaskCreate`, `TaskUpdate`, and `TaskGraph` persist and read back live task state.
10. **ETL workflow**
    `ETLProcess` returns raw memories and `ETLClassify` removes a classified memory from the raw queue.
11. **Refinery workflow**
    `MemoryConsolidate(force=false)` returns a dry-run refinery plan and stats.
12. **Restart persistence**
    Memory, graph-backed state, task state, and sessions survive a full MCP subprocess restart.
13. **Cleanup isolation**
    Protocol-created memories are deleted through the tool surface, then the temp Elefante home/data tree is removed.

## Full-Surface Coverage Map

When run with `--with-dashboard-open`, the self-protocol invokes every live MCP tool and both prompts. Default mode skips only `elefante-DashboardOpen`.

### Tools

| Surface | Harness phase | Default mode | Full-surface mode |
| --- | --- | --- | --- |
| `elefante-Memory(action="add")` | Memory lifecycle | Yes | Yes |
| `elefante-Memory(action="search")` | Routing, compliance reset, memory lifecycle, cleanup | Yes | Yes |
| `elefante-GraphQuery` | Graph and context | Yes | Yes |
| `elefante-ContextGet` | Graph and context | Yes | Yes |
| `elefante-SessionsList` | Graph and context, restart persistence | Yes | Yes |
| `elefante-SystemStatusGet` | Baseline routing and system status | Yes | Yes |
| `elefante-Memory(action="consolidate")` | ETL and consolidation | Yes | Yes |
| `elefante-Memory(action="update")` | Memory lifecycle | Yes | Yes |
| `elefante-Memory(action="delete")` | Compliance gate, memory lifecycle, cleanup | Yes | Yes |
| `elefante-DashboardOpen` | Optional dashboard tool | No | Yes |
| `elefante-GraphConnect` | Graph and context | Yes | Yes |
| `elefante-System` | Baseline routing and system status, system compatibility and restart | Yes | Yes |
| `elefante-TaskCreate` | Task orchestration | Yes | Yes |
| `elefante-TaskUpdate` | Task orchestration | Yes | Yes |
| `elefante-TaskGraph` | Task orchestration, restart persistence | Yes | Yes |
| `elefante-ETLProcess` | ETL and consolidation | Yes | Yes |
| `elefante-ETLClassify` | ETL and consolidation | Yes | Yes |
| `elefante-DirectiveAdd` | Directive tools | Yes | Yes |
| `elefante-DirectiveList` | Directive tools | Yes | Yes |
| `elefante-DirectiveRemove` | Directive tools | Yes | Yes |

### Prompts

| Surface | Harness phase | Default mode | Full-surface mode |
| --- | --- | --- | --- |
| `elefante-grounding` | Surface inventory | Yes | Yes |
| `elefante-context` | Memory lifecycle | Yes | Yes |

This is the concrete answer to "are all Elefante tools really invoked?" The full-surface run is the maintained path that proves yes without polluting the user's durable memory store.

---

## What It Does Not Prove By Default

Default mode does **not** prove `elefante-DashboardOpen` itself.

That exclusion is deliberate. The dashboard tool is process- and UI-bearing, so its safest automated coverage remains split:

- Default self-protocol: everything self-contained
- Opt-in `--with-dashboard-open`: full 20-tool sweep when explicitly requested
- Targeted dashboard guards: `pytest tests/test_dashboard_serializer.py -k "dashboard" -v`

This is not a gap hidden under the rug. It is an explicit boundary between self-contained proof and global side-effect proof.

---

## Cleanup Contract

The harness must clean up in two layers:

### Tool-Surface Cleanup

- Remove the custom directive immediately after testing it
- Delete protocol-created memories through `elefante-Memory(action="delete")`

### Environment Cleanup

- Stop MCP subprocesses
- Kill the opt-in dashboard subprocess if it was started
- Delete the entire temporary Elefante home/data directory

Some artifacts, such as graph entities and tasks, have no dedicated delete tool in the current MCP surface. Those traces are still safe because they only ever exist inside the temporary Elefante store that is removed at the end.

---

## Maintainer Notes

The self-protocol is itself part of the maintained confidence surface.

Two implementation constraints are easy to get wrong:

- The MCP client must allow large one-line JSON-RPC payloads. `ContextGet` can exceed asyncio's default subprocess readline chunk size, so the harness explicitly raises its stream limit.
- The optional dashboard phase must verify the snapshot where the live runtime writes it, not only where the harness would prefer it to be. `src.mcp.server` refresh currently writes through the `HOME`-derived `DATA_DIR` path.

If these invariants change, update the harness and the guard tests together.

---

## When To Use This Protocol

Use the self-protocol when:

- The user asks whether Elefante is actually running
- You want release-level confidence in the live MCP surface
- You changed code that crosses multiple domains and targeted tests are too narrow to prove the full behavior

Do **not** start here when:

- The failure already matches a `BUG-NNN` row in `workspace/ISSUES.md`
- A smaller existing `pytest` target can answer the exact question faster

In those cases, run the maintained narrow verifier first and only escalate to the self-protocol if the question becomes whole-system.

---

## Failure Routing

Use the failing phase to narrow the next move:

- **Handshake / inventory / prompts**: inspect `src/mcp/server.py`, `tests/test_developer_routing.py`, and `docs/reference/tools.md`
- **Routing / directives / compliance**: inspect `workspace/postmortems/ai-behavior.md`
- **Memory / ETL / refinery**: inspect `workspace/postmortems/memory.md`
- **Graph / sessions / tasks / lock symptoms**: inspect `workspace/postmortems/database.md`
- **Dashboard opt-in phase**: inspect `workspace/postmortems/dashboard.md`

Always prefer the phase-specific maintained verifier before inventing a scratch reproducer.

---

## Decision Rule

If you need to say either of these sentences:

- "Elefante is running."
- "The live MCP surface is healthy end-to-end."

Run the self-protocol first.
