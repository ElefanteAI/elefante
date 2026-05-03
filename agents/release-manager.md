---
PROTOCOL: release-manager
INVOKE: elefante-release-manager
PROTOCOL_VERSION: 2.10.0-pre
LOAD_WHEN: Version bump request, CHANGELOG entry needed, "ready to release", "tag X.Y.Z", "push to GitHub Releases".
DIAGNOSTIC_QUESTION: "Is this an Add / Fix / Change, what semver bump does that imply, and is the CHANGELOG entry written before the bump?"
AUTHORITY: This file owns the release pipeline. CONTRIBUTING.md release section forwards here.
---

# Release Manager Agent

## The Inviolable Order

CHANGELOG entry → `advise_version_bump.py` → `bump_version.py X.Y.Z` → commit → tag → push. Skip any step = release is broken.

Never hand-edit version strings. The orchestrator's Never (4) covers this; this file enforces it.

## Step 1 — CHANGELOG Entry

`CHANGELOG.md` uses three live headings: `### Added`, `### Fixed`, `### Changed`. Map the work:

| Work | Heading |
| ---- | ------- |
| New feature, new file, new capability | `### Added` |
| Bug fix, regression repair | `### Fixed` |
| Behavior change to existing feature, refactor visible to user | `### Changed` |
| File/script/doc removal | `### Removed` (per `agents/memory-janitor.md` rule 1) |

Entry format: one line, past tense, names the artifact. No marketing prose.

## Step 2 — Advise the Bump

```
python scripts/ci/advise_version_bump.py
```

This reads CHANGELOG and proposes the semver bump. Strict semver per `docs/how-to/close-a-feature.md`:

- New `### Added` only → MINOR (`X.Y.0`)
- Only `### Fixed` → PATCH (`X.Y.Z+1`)
- `### Changed` involving breaking API/CLI/tool surface → MAJOR (`X+1.0.0`)
- `### Removed` of a public surface → MAJOR

If `advise_version_bump.py` proposes a bump you disagree with, the disagreement is a CHANGELOG framing issue. Fix the CHANGELOG, not the bump.

## Step 3 — Bump

```
python scripts/ci/bump_version.py 2.10.0
python scripts/ci/bump_version.py --check
```

`--check` confirms every version-bearing file picked up the new value. Failure here = tooling bug, not a manual-fix license.

## Step 4 — Commit

One commit, one concern. Subject line format:

- `chore: bump to vX.Y.Z` (when the work was committed earlier and this is just the bump)
- `feat: <description> (vX.Y.Z)` (when the bump rides with the feature commit)

## Step 5 — Tag and Push

```
git tag vX.Y.Z
git push origin main vX.Y.Z
```

GitHub Actions renders the release body from the matching `CHANGELOG.md` entry via `scripts/ci/render_release_notes.py`. **Do not push a `v*` tag before the CHANGELOG entry exists** — the release body will be empty.

## Authorized Scripts

`scripts/ci/advise_version_bump.py`, `scripts/ci/bump_version.py`, `scripts/ci/render_release_notes.py`, `scripts/ci/select_release_assets.py`, `scripts/ci/build_dmg.py`, `scripts/ci/build_installer_bundle.py`.

## Closure

After tag is live:

1. Verify GitHub Releases page rendered the body (not empty).
2. Update README's `**vX.Y.Z**` badge line if stale.
3. Memory Janitor: a `### Released` audit memory if the release closed a tracked spec.
