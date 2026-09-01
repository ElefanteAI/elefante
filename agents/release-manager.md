---
PROTOCOL: release-manager
INVOKE: elefante-release-manager
PROTOCOL_VERSION: 2.14.0
LOAD_WHEN: Version bump request, CHANGELOG entry needed, "ready to release", "tag X.Y.Z", "push to GitHub Releases".
DIAGNOSTIC_QUESTION: "Is this an Add / Fix / Change, what semver bump does that imply, and is the CHANGELOG entry written before the bump?"
AUTHORITY: This file owns the release pipeline. CONTRIBUTING.md release section forwards here.
---

# Release Manager Agent

## The Inviolable Order

Approved release scope → CHANGELOG entry → `advise_version_bump.py` →
`bump_version.py X.Y.Z` → verification → commit → exact-SHA green checks → tag
and publish → published-asset redownload verification. Tagging, pushing, or
publishing requires explicit release authorization.

Never hand-edit version strings. The orchestrator's Never (4) covers this; this file enforces it.

## Step 1 — CHANGELOG Entry

`CHANGELOG.md` uses four live headings: `### Added`, `### Fixed`, `### Changed`,
and `### Removed`. Map the work:

| Work | Heading |
| ---- | ------- |
| New feature, new file, new capability | `### Added` |
| Bug fix, regression repair | `### Fixed` |
| Behavior change to existing feature, refactor visible to user | `### Changed` |
| File/script/doc removal | `### Removed` (per `agents/memory-janitor.md` rule 1) |

Entry format: one line, past tense, names the artifact. No marketing prose.

## Step 2 — Advise the Bump

```
./.venv/bin/python scripts/ci/advise_version_bump.py
```

This reads CHANGELOG and proposes the semver bump. Strict semver per `docs/how-to/close-a-feature.md`:

- New `### Added` only → MINOR (`X.Y.0`)
- Only `### Fixed` → PATCH (`X.Y.Z+1`)
- `### Changed` involving breaking API/CLI/tool surface → MAJOR (`X+1.0.0`)
- `### Removed` of a public surface → MAJOR

Treat the advisor as evidence, not authority. If the approved release scope
requires a different SemVer, document the reason and apply the approved version
through `bump_version.py`; do not manipulate changelog language to force a
preferred answer.

## Step 3 — Bump

```
./.venv/bin/python scripts/ci/bump_version.py <X.Y.Z>
./.venv/bin/python scripts/ci/bump_version.py --check
```

`--check` confirms every version-bearing file picked up the new value. Failure here = tooling bug, not a manual-fix license.

## Step 4 — Commit

One commit, one concern. Subject line format:

- `chore: bump to vX.Y.Z` (when the work was committed earlier and this is just the bump)
- `feat: <description> (vX.Y.Z)` (when the bump rides with the feature commit)

## Step 5 — Tag and Push

Only after explicit authorization, run the commands against the approved
commit and target branch:

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
2. Verify the version-bump cascade updated README and every declared version
   surface; do not repair individual version strings by hand.
3. Search Elefante and store a release lesson only if it is durable, useful for
   future work, and not already represented by the changelog and living plan.
