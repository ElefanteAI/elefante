# Next Steps

## Strategy A: The Quickest Fix

Patch `docs/technical/dev-sdd.md` Gate 5 so it points to the live changelog headings `Added`, `Fixed`, and `Changed`, then extend `tests/test_developer_routing.py` to assert that contract.

### Core Hypothesis

The current blocker is pure process drift. A small doc fix plus one regression assertion should close it cleanly.

## Strategy B: The Alternative Path

Add a dedicated regression test such as `test_dev_sdd_matches_live_changelog_contract()` that reads both `docs/technical/dev-sdd.md` and `CHANGELOG.md` and fails when the process doc names retired headings.

### Core Hypothesis

If the existing generic routing tests are getting crowded, a focused changelog-contract test will make future failures easier to diagnose.

## Strategy C: The Step Back

Stop hand-maintaining this rule in multiple places. Centralize the changelog contract in one source-derived check or generate the relevant `dev-sdd.md` checklist line from a shared constant/template.

### Core Hypothesis

The recurring pattern in this repo is documentation drift. A generated or centrally asserted process contract reduces the number of manual sync points.

## Identified Risks And Traps

1. Do not reopen the `spec-tools.md` 13-bug audit unless `src/mcp/server.py` changes again.
2. Do not misclassify verifier failures as product regressions before comparing the harness against the live runtime contract.
3. Do not patch runtime source to solve a docs-only blocker.
4. Do not hand-edit scattered version strings. If versioning is part of closure, use `scripts/ci/bump_version.py`.

## Success Criteria For The Next Session

- `docs/technical/dev-sdd.md` no longer names retired changelog headings.
- `tests/test_developer_routing.py -v` fails before the fix and passes after it.
- The handoff package remains accurate: runtime green, verifier green, process-doc drift closed.