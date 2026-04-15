<!--
Annotated excerpt from docs/technical/dev-sdd.md.
This is the live blocker.
Unrelated sections are omitted on purpose.
-->

# Excerpt: docs/technical/dev-sdd.md

## Gate 5: Output Discipline

Before committing:

- [ ] **Minimal patch** — No unrelated refactors bundled in. One problem, one fix.
<!--
Supposed to do:
tell contributors which headings to use when they add a CHANGELOG entry.

Current failure:
this still points at the retired headings "The Problem Solved / The Solution / Changes".

Why it matters:
the live CHANGELOG now uses Keep a Changelog sections "Added / Fixed / Changed",
so this line is wrong and can regenerate bad edits.

Debugging already done:
- compared this line against CHANGELOG.md top headings
- confirmed the runtime is healthy, so the blocker is process drift rather than product behavior
- confirmed tests/test_developer_routing.py does not yet assert this contract, which is why CI stays green
-->
- [ ] **CHANGELOG.md entry written** — `### The Problem Solved` + `### The Solution` + `### Changes` format
- [ ] **Version bumped** using `scripts/ci/advise_version_bump.py` — never edit version strings by hand
- [ ] **All linked docs updated** — if you changed a tool signature, update `docs/technical/spec-tools.md`
- [ ] **`grep -r "filename" docs/`** — if you moved or renamed any file, all links resolved