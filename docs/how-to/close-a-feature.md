# Close an Elefante Development Change

**Applies to:** current developer workflow at v2.12.2

This is a developer procedure, not customer documentation. `AGENTS.md` and
`agents/orchestrator.md` define the governing workflow.

## 1. Clean

- Review `git status --short` and preserve unrelated user work.
- Remove temporary diagnostics, generated scratch artifacts, and dead code.
- Do not delete user data, backups, or another contributor's changes.

## 2. Synchronize documentation

- Update the single canonical product, operational, or developer document that
  owns the changed claim.
- Update `docs/README.md` only when its published navigation changes.
- Update `CHANGELOG.md` under `Unreleased` for a user-visible or release-relevant
  change. Use live Keep a Changelog headings: `### Added`, `### Fixed`,
  `### Changed`, or `### Removed`.
- Never use retired headings such as `### The Problem Solved`,
  `### The Solution`, or `### Changes`.

## 3. Verify

Run the smallest maintained regression that proves the change, then the
required routing/release gates for its scope. Record exact results; “looks
correct” is not proof.

```bash
./.venv/bin/python -m pytest tests/test_developer_routing.py -q
git diff --check
```

Use `tests/README.md` for targeted and full-suite routes.

## 4. Version only during an approved release

Do not bump the product for every development commit. When a release is
approved, write its changelog entry first, then run:

```bash
./.venv/bin/python scripts/ci/advise_version_bump.py
./.venv/bin/python scripts/ci/bump_version.py <X.Y.Z>
./.venv/bin/python scripts/ci/bump_version.py --check
```

The advisor provides evidence; approved scope determines the final SemVer.
Never hand-edit scattered version strings.

## 5. Commit and publish within authority

- Review the complete diff and test results.
- Commit one coherent concern.
- Push, open a PR, tag, publish, merge, or deploy only when the user's request
  authorizes that external change.
- After a push, verify the intended local and remote commit and required CI.
