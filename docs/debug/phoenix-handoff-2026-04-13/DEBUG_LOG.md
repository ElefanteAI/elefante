# Debug Log

## Current Roadblock

The active runtime bugs are not the blocker anymore. The remaining issue is process drift between `docs/technical/dev-sdd.md` and `CHANGELOG.md`.

- `dev-sdd.md` still prescribes: `### The Problem Solved` + `### The Solution` + `### Changes`
- `CHANGELOG.md` now uses: `### Added` + `### Fixed` + `### Changed`
- `tests/test_developer_routing.py` currently misses an assertion for that mismatch, so CI stays green.

## Failed Hypotheses

1. The 13-item `spec-tools.md` audit was still open.
   False. The live `docs/technical/spec-tools.md` already matches `src/mcp/server.py`.
2. A full-sweep failure in `verify_e2e_tests.py --with-dashboard-open` meant the live dashboard/runtime was broken.
   False. The failure came from stale verifier assumptions about snapshot path and subprocess line size.
3. The graph/session contract was still blocking progress.
   False. BUG-008 is fixed and guarded.
4. The next fix needs runtime code changes in `src/mcp/server.py`.
   False. The immediate blocker is documentation and missing regression coverage.
5. `pytest tests/test_developer_routing.py -v` already covers all active process guidance.
   False. It guards paths and tool counts, but not the live changelog-heading contract.

## Test Cases And Reproduction

### A. Current blocker: stale changelog instruction

#### Trigger

Inspect the Gate 5 checklist in `docs/technical/dev-sdd.md`.

#### Incorrect output

```text
- [ ] **CHANGELOG.md entry written** — `### The Problem Solved` + `### The Solution` + `### Changes` format
```

#### Working contrast

The live top of `CHANGELOG.md` is:

```text
### Added
### Fixed
### Changed
```

#### Why this matters

Elefante tells developers to follow the process docs first. If the process doc is wrong, it actively regenerates drift.

### B. Recently resolved blocker: self-protocol false failures

#### Trigger

```bash
.venv/bin/python scripts/verify/verify_e2e_tests.py --with-dashboard-open
```

#### Previous incorrect output

```text
[FAIL] DashboardOpen refresh writes snapshot and reports ready state
```

and then, after that was fixed:

```text
[FAIL] Harness execution -- Separator is found, but chunk is longer than limit
```

#### Current expected output

```text
Full sweep passes when port 8000 is free.
```

Operationally, that now means the maintained proof reaches a fully green dashboard-enabled run instead of reporting verifier-only false bugs.

### C. Closed audit that should not be reopened blindly

#### Trigger

Audit `docs/technical/spec-tools.md` against the live tool schema in `src/mcp/server.py`.

#### Previous assumption

```text
There are still 13 open documentation bugs in spec-tools.md.
```

#### Actual result

```text
The current spec-tools.md already documents 20 tools, 2 prompts,
current ETL fields, GraphConnect/GraphQuery/ContextGet parameters,
System.force, DashboardOpen refresh dependency, and operational best practices.
```

## Prior Working Version / Known Good Contract

No earlier good `dev-sdd.md` Gate 5 snippet was found in the active repo. Use the live changelog itself as the source of truth.

```md
## [2.4.1] - 2026-04-13

### Added

- Self-Elefante protocol ...

### Fixed

- Graph/session schema contract drift ...
- Self-protocol verifier drift ...

### Changed

- Verification routing ...
```

## What Is Already Proven Healthy

- `scripts/lifecycle/restart_elefante.py --verify` passes.
- `pytest tests/test_developer_routing.py -v` passes.
- The full self-protocol passes after the verifier drift fixes.
- Formal BUG-001 through BUG-009 entries are fixed or tested in `docs/debug/README.md`.