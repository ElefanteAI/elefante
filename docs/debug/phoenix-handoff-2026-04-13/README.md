# Phoenix Continuation Package

## Project Goal

Elefante is a local-first MCP memory engine that gives AI agents persistent memory, graph context, task state, directives, ETL enrichment, and a snapshot-driven dashboard.

## Current Blocker

The runtime is green. The live self-protocol now passes the full 20-tool sweep, the graph/session and verifier regressions are fixed, and the `spec-tools.md` audit is closed. The remaining blocker is developer-process drift: `docs/technical/dev-sdd.md` still tells contributors to write `CHANGELOG.md` entries using the obsolete `### The Problem Solved` / `### The Solution` / `### Changes` format, while the live `CHANGELOG.md` uses `### Added` / `### Fixed` / `### Changed`. Because Elefante routes developers through process docs first, this stale line can regenerate bad edits even though the product is healthy.

## Priority Next Step

Patch `docs/technical/dev-sdd.md` Gate 5 to match the live `CHANGELOG.md` contract, then add a regression assertion to `tests/test_developer_routing.py` so CI fails if that drift returns.

## Status Snapshot

- `scripts/verify/verify_e2e_tests.py --with-dashboard-open` now passes the full sweep when port `8000` is free.
- `pytest tests/test_developer_routing.py -v` is green, but it does not yet guard the changelog-heading contract.
- `scripts/lifecycle/restart_elefante.py --verify` is green.
- Formal bug ledger `BUG-001` through `BUG-009` is fixed or tested in `docs/debug/README.md`.

## Key Decisions & Rationale

- `scripts/verify/verify_e2e_tests.py` is now the authoritative whole-system proof.
  Rationale: narrow tests were not sufficient for end-to-end health claims.
- `elefante-DashboardOpen` stays opt-in in the full sweep.
  Rationale: it binds port `8000` and attempts browser launch, so it is a side-effect tool rather than a pure self-contained verifier step.
- The verifier was fixed to follow the live runtime contract instead of convenience assumptions.
  Rationale: the false failures came from the harness checking the wrong dashboard snapshot path and using the default asyncio line limit.
- The 13-item `spec-tools.md` audit is closed.
  Rationale: the current `docs/technical/spec-tools.md` already matches `src/mcp/server.py`; reopening that audit is wasted motion.
- Cross-bug learnings live in `docs/debug/best_practices.md` and route through `docs/debug/README.md`.
  Rationale: the project wants reusable debugging rules, not one-off conversation residue.