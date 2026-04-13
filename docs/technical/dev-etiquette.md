# Elefante Developer Etiquette (Native SDD Specification)

**Version:** 2.2.3
**Type:** SPECIFICATION

This document governs the required closure sequence for all feature development, bug fixes, and architectural adjustments within the Elefante repository. 

As a `SPECIFICATION`, this document holds immutable authority (1.0). Agents MUST execute the following sequence precisely before claiming that a task is complete.

## 1. Delete Leftovers (`CLEAN_ENVIRONMENT`)
Never leave experimental artifacts, scratchpads, debug logs, or temporary scripts in the repository once a feature is proven and integrated.

*   **Audit the Tree:** Run a `git status` or `tree` equivalent to identify untracked files.
*   **Wipe Experiments:** Delete any `.md` or `.py` files created solely to formulate a plan or test a hypothesis that is now resolved. The final implementation is the truth; the scratchpad is liability.
*   **Remove Dead Code:** Do not leave commented-out blocks of the previous implementation. If it's old, delete it. Git maintains the history.

## 2. Update Documentation (`DOC_SYNC`)
Code is secondary; the specification is primary. You cannot consider a code change "done" until the public and technical documentation reflects it.

*   **READMEs:** Ensure `README.md` is updated if the core feature set, architecture, or installation process changes. `docs/README.md` is a navigation index — update it only when files are added, moved, or deleted.
*   **Architecture Specs:** Update `docs/technical/spec-architecture.md` immediately if the cognitive flow or component interaction changes.
*   **Changelog:** Add an entry to `CHANGELOG.md` matching the current version bump. Explicitly document the "Why," "What," and "Impact."

## 3. Versioning (`STRICT_SEMVER`)
Elefante enforces strict, automated semantic versioning (`x.y.z`). Manual version edits in individual files are prohibited.

*   **Understand the Bump:**
    *   `MAJOR` (x): Breaking changes or DB migrations.
    *   `MINOR` (y): New features, backward compatible (e.g., adding `SPECIFICATION` schema).
    *   `PATCH` (z): Bug fixes, internal cleanup.
*   **Use the Bumper:** Run `python3 scripts/bump_version.py <version>` to cascade the correct version across all 42+ project files simultaneously.

## 4. Final Lock (Git Etiquette)
Once the tree is clean, the docs are synced, and the version is cascaded, lock the state.

*   **Diff Audit:** Review the diff to ensure no accidental debug print statements or commented code escaped.
*   **Atomic Commit:** Write a clean, professional commit message outlining the feature completion and the version bump.
*   **Clean Tree:** Run `git status` before finishing. It must return `nothing to commit, working tree clean`.
