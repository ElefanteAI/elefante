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

That question requires a live subprocess, the real direct MCP tool/prompt
surface, real state mutation, restart persistence, and cleanup inside an
isolated store.

This document defines that whole-system proof.

It does not replace the customer transport proof. The shipped topology is a
stdio bridge talking to the loopback daemon, while this harness launches the
MCP handler directly. `tests/test_mcp_daemon.py` separately proves the real
bridge/daemon handshake, exact 18-tool current-source customer inventory, concurrent bridges,
and bounded stale-session recovery. A release claim needs both layers.

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
- Explicitly enables the default-off Task Intelligence development surface
- Verifies **18 of 19 development tools** plus **both prompts**
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

Use this only when you explicitly want the nineteenth development tool checked.

Preconditions:

- Port `8000` must be free before the harness starts
- You accept a short-lived dashboard subprocess during the run

Runtime behavior:

- The harness preflights port `8000`
- Browser launch is stubbed with an isolated Python no-op command built from the
  active interpreter, so the optional phase has no POSIX-only path dependency
- The dashboard server is killed during cleanup
- Snapshot verification must follow the live runtime path, which may be the `HOME`-derived `~/.elefante/data/dashboard_snapshot.json` path used by `src.mcp.server`

If you do not need the `elefante-DashboardOpen` tool itself, do not run this mode.

---

## What The Protocol Proves

The authoritative harness verifies these phases in order:

1. **Handshake and inventory**
   The real MCP server boots, completes `initialize`, and exposes the expected
   opt-in 19-tool plus 2-prompt development surface. Current-source customer
   discovery and the current published customer profile expose 18 tools and 2
   prompts, including verified `elefante-Recover`. The extra Task Intelligence
   tool remains default-off and developer-only.
2. **Answer context and prompt retrieval**
   `elefante-Recall` returns its seven-field bounded read-only payload without
   an echoed question, internal IDs, or generic protocol wrappers. The governed
   context stays within 450 heuristic tokens and the complete response within
   1,000;
   `elefante-grounding` and `elefante-context` return usable prompt content.
3. **Routing and directives**
   Successful and failing non-Recall tool calls both inject `DIRECTIVES` and
   `ENTRYPOINT_SEQUENCE_READ_THIS_FIRST`.
4. **System compatibility**
   `elefante-SystemStatusGet` and `elefante-System` behave correctly under transaction-scoped mode.
5. **Directive lifecycle**
   Add, list, and remove all work against the real persistent directive store.
6. **Compliance Gate**
   A fresh session with no prior search cannot mutate memory.
7. **Memory lifecycle**
   One strict registered project owns the isolated records. Verified Remember
   persists and proves a future Recall cue; `search` and `list_all` inspect the
   scoped result; verified Correct edits one record and permanently deletes
   protocol-created records through its backup-bound lifecycle. Legacy content
   and lifecycle aliases are not used as product proof.
8. **Task Intelligence lifecycle**
   A pilot Task Brief delivers bounded memory IDs, and declared use is accepted
   only for the same trace without changing ranking.
9. **Graph and context**
   `GraphConnect`, `GraphQuery`, `ContextGet`, and `SessionsList` all return meaningful state derived from protocol-created entities.
10. **Task graph**
   `TaskCreate`, `TaskUpdate`, and `TaskGraph` persist and read back live task state.
11. **ETL workflow**
    `ETLProcess` returns raw memories and `ETLClassify` removes a classified memory from the raw queue.
12. **Refinery workflow**
    `elefante-Memory(action="consolidate", force=false)` returns a dry-run refinery plan and stats.
13. **Restart persistence**
    Memory, graph-backed state, task state, and sessions survive a full MCP subprocess restart.
14. **Cleanup isolation**
    Protocol-created memories are deleted through the tool surface, then the temp Elefante home/data tree is removed.

## Full-Surface Coverage Map

When run with `--with-dashboard-open`, the self-protocol invokes all 19 opt-in
development MCP tools and both prompts. Default mode verifies 18 of 19 and skips
only `elefante-DashboardOpen`. The harness sets both Task Intelligence flags only
inside its isolated temporary environment.

### Tools

| Surface | Harness phase | Default mode | Full-surface mode |
| --- | --- | --- | --- |
| `elefante-Memory(action="add")` | Memory lifecycle | Yes | Yes |
| `elefante-Memory(action="search")` | Routing, compliance reset, memory lifecycle, cleanup | Yes | Yes |
| `elefante-Recall` | Bounded customer answer context | Yes | Yes |
| `elefante-Recover(action="health")` | Read-only lifecycle health | Yes | Yes |
| `elefante-TaskIntelligence` | Bounded prepare and trace-bound declared use | Yes | Yes |
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

This is the concrete answer to "are all direct development-handler tools really
invoked?" The full-surface run is the maintained path that proves yes without
polluting the user's durable memory store. It is not, by itself, proof of the
customer bridge/daemon topology.

---

## What It Does Not Prove By Default

Default mode does **not** prove `elefante-DashboardOpen` itself or the shipped
stdio bridge/daemon transport.

That exclusion is deliberate. The dashboard tool is process- and UI-bearing, so its safest automated coverage remains split:

- Default self-protocol: everything self-contained
- Opt-in `--with-dashboard-open`: full 19-tool development sweep when explicitly requested
- Targeted dashboard guards: `pytest tests/test_dashboard_serializer.py -k "dashboard" -v`
- Customer transport guards: `pytest tests/test_mcp_daemon.py -k "stdio_bridge or bridge_reinitializes" -q`

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
