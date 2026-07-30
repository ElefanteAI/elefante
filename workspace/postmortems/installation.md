# Installation Postmortems

> **Domain:** Installation, setup, environment, CI/release pipeline.
> **Cross-refs:** BUG/GAP rows + verification commands live in [`../ISSUES.md`](../ISSUES.md). Reusable cross-bug rules live in [`../lessons.md`](../lessons.md).
> **Format per entry:** Trigger / Root cause / Solution / Lesson. Full narrative preserved verbatim in [`_archive/installation-full.md`](_archive/installation-full.md).

---

## Issue #1: Kuzu 0.11.x Path Breaking Change [FIXED]

**Trigger:** Fresh install fails with `RuntimeError: Database path cannot be a directory`.
**Root cause:** Kuzu 0.11.x stopped tolerating a pre-existing `kuzu_db/` directory; older Kuzu was permissive. `src/utils/config.py` eagerly called `KUZU_DIR.mkdir(exist_ok=True)` on import, breaking the new contract.
**Solution:** Removed the eager `KUZU_DIR.mkdir` from `config.py`; `src/core/graph_store.py::_ensure_database_path` now removes any pre-existing directory before letting Kuzu create its own structure; `scripts/setup/install.py` adds a pre-flight check.
**Lesson:** Read library changelogs before upgrading. Let libraries manage their own resources — eager directory creation is helpful only until it isn't.

## Issue #2: Missing Dependencies After Clone [DOCUMENTED]

**Trigger:** Fresh clone fails with `ModuleNotFoundError: No module named 'chromadb' / 'kuzu'`.
**Root cause:** User skipped `pip install -r requirements.txt`. The error message does not name the fix.
**Solution:** `install.sh` / `install.bat` / `scripts/setup/install.py` run pip install automatically — never assume the user did.
**Lesson:** A user-facing installer must run dependency installation itself. Don't expect README compliance.

## Issue #3: Python Version Mismatch [DOCUMENTED]

**Trigger:** Install fails with `ERROR: Package 'kuzu' requires a different Python: 3.9.7 not in '>=3.11'` or cryptic syntax errors from walrus / union types.
**Root cause:** Elefante requires Python 3.11+ for `|` union syntax, walrus operator, and Kuzu/ChromaDB compatibility. Multiple Python versions on a system mask the wrong default.
**Solution:** `scripts/setup/install.py` checks Python version explicitly and creates the venv with `python3.11 -m venv .venv`. README documents the requirement.
**Lesson:** Specify Python version in requirements *and* fail fast in the installer. Cryptic syntax errors waste user time.

## Issue #4: Config Pre-creating Directories [FIXED]

**Trigger:** Same surface as Issue #1 — Kuzu init fails on first run.
**Root cause:** `src/utils/config.py` ran `mkdir(exist_ok=True)` on import for `DATA_DIR` / `CHROMA_DIR` / `KUZU_DIR`. Worked with old Kuzu; broke 0.11.x.
**Solution:** Lazy directory creation via `ensure_data_dirs()` called by code paths that need them. `KUZU_DIR` is never created by Elefante — Kuzu owns it.
**Lesson:** Don't be helpful with directories libraries own. Eager-import side effects are landmines.

## Issue #5: Broken Venv Escape (Trapped Agent) [FIXED]

**Trigger:** Agent runs in VS Code with corrupted `.venv`; `python scripts/setup/install.py` fails with ImportError / wrong-Python because the workspace interpreter is broken.
**Root cause:** Circular dependency — the agent's Python execution uses the broken `.venv` and cannot fix itself from within. No escape hatch to system Python.
**Solution:** Documented escape pattern: `subprocess.run(["/opt/homebrew/bin/python3.11", "-c", "..."])` with absolute path to system Python; alternative `#!/usr/bin/env python3.11` shebang in install scripts forces OS-level resolution.
**Lesson:** When the agent's interpreter is the broken thing, an absolute system-Python subprocess is the only escape. Don't assume the workspace Python is healthy.

## Issue #6: IDE Holding Stale MCP Server Connections [DOCUMENTED]

**Trigger:** After re-install or update, IDE keeps talking to an old MCP server version (e.g. v1.6.3 when v2.1.4 is installed).
**Root cause:** IDEs (VS Code, Cursor, Antigravity) launch the MCP server as a background process at session start. Updating `mcp_config.json` does not terminate the running instance.
**Solution:** Mandatory IDE window reload after install or config change (Command Palette → Developer: Reload Window). Manual `pkill` of the zombie Python process if reload fails.
**Lesson:** IDEs do not hot-reload MCP server configurations. Make the reload step explicit in install output.

## Issue #7: IBM Bob Non-Standard MCP Settings Path [DOCUMENTED]

**Trigger:** Auto-config script reports "Configured VS Code successfully" but IBM Bob still shows no Elefante MCP server.
**Root cause:** IBM Bob stores MCP settings at `~/.bob/settings/mcp_settings.json` (non-standard) — not the AppData/`%APPDATA%\Bob-IDE\...` path other IDEs use.
**Solution:** `scripts/setup/configure_vscode_bob.py` checks both paths; manual fallback documented in [`../../docs/how-to/configure-ide.md`](../../docs/how-to/configure-ide.md).
**Lesson:** IDE config paths are not standardized. Always grep the IDE's own dotfile dir first; never assume the AppData convention.

## Issue #8: CI Binary Build — Frontend Step Missing + Wrong Vite Output [FIXED v2.5.4]

**Trigger:** First `v*` tag push triggers `build-binaries.yml` and all three platform jobs fail with PyInstaller path-not-found on the `datas` entry.
**Root cause:** Two layers — (1) `elefante.spec` referenced `src/dashboard/ui/build` but Vite's `vite.config.ts` outputs to `dist/`. (2) `src/dashboard/ui/dist/` is gitignored so CI checks out without it; no `setup-node` + `npm ci && npm run build` step preceded PyInstaller.
**Solution:** `elefante.spec` `datas` entry → `src/dashboard/ui/dist`. `build-binaries.yml` adds `setup-node@v4` + `npm ci` + `npm run build` in `src/dashboard/ui/` before the Python install step.
**Lesson:** A CI pipeline that builds compiled artifacts must include every build step required to produce them. Gitignored build outputs do not exist in CI. Verify `outDir` against `vite.config.ts` / `webpack.config.js` before referencing in a build spec.

## Issue #9: GitHub Release Publish Failure After Successful Builds [FIXED v2.7.1]

**Trigger:** All three platform builds succeed, but `Create GitHub Release` job fails. Release object exists with macOS + Windows assets; Linux asset missing.
**Root cause:** `softprops/action-gh-release@v1` rejects assets ≥ GitHub's 2 GiB per-file release cap. Linux artifact for `v2.6.0` was 4,021,041,080 bytes.
**Solution:** `scripts/ci/select_release_assets.py` runs between artifact download and release publish, filters assets above the cap, and writes uploaded vs skipped to step summary. Workflow keeps green when smaller assets are valid; oversized asset is reported, not poisonous.
**Lesson:** Build-job success does not imply release-asset eligibility. Enforce platform upload quotas before publication or one oversized asset poisons the entire release job.

## Issue #10: DMG GUI Installer .app Broken — Multi-Edit Corruption [FIXED v2.8.1]

**Trigger:** `Install Elefante.app` exits code 1; no GUI window. `IndentationError: unexpected indent` on `installer_gui.py:173`.
**Root cause:** `scripts/ci/installer_gui.py` was patched 3+ times in a single session via overlapping string-replacement edits (chmod fix, dark→light palette swap, path display additions). Result: undefined `style`, orphaned kwargs, duplicate widget constructors, references to nonexistent palette keys. File was never committed — no git recovery possible.
**Solution:** Rewrote the corrupted zone (~140 lines: `__init__` tail + `_build_ui`) from scratch as a coherent light-mode version. Verified by `py_compile`, AST structural check, DMG rebuild + diff, `.app` launch, full pytest.
**Lesson:** After any multi-edit session on a single file, run `py_compile` BEFORE moving on. Test suite passing means nothing if the test suite doesn't import the file. Commit working states; don't leave critical files untracked across sessions.

## Issue #11: DMG Customer Surface Broken — Tk/Aqua Paint Failure [FIXED v2.9.0]

**Trigger:** `.app` launches successfully, `GUI_RUNNING=YES`, widgets exist with valid geometry — but the rendered window is a mostly blank white screen with no usable installer experience.
**Root cause:** Three-layer chain. (a) BUG-019's syntax rewrite used `tk.Label(parent, bg=C["panel"], ...)` everywhere. (b) On macOS, the Aqua theme overrides explicit `bg=` on `tk.Label` — backgrounds are OS-painted. (c) Result: invisible text against white window. `py_compile`, launch liveness, and widget-tree dump all passed; only a screenshot caught it.
**Solution:** Pivoted DMG `.app` away from Tk for the customer surface. `scripts/ci/installer_app.swift` (native AppKit, 794 lines) is now the primary installer; `installer_gui.py` retained only as fallback when Swift compilation is unavailable. Both surfaces route failures to the same persisted `.elefante-install-{summary,status,log}` files.

### Question-First Verification Path

For installer UX bugs, **start with the narrowest customer-visible question** and only widen proof when the prior check fails:

1. Screenshot the rendered installer surface (customer-visible proof).
2. Only if the screenshot is still broken, inspect widget existence separately (`winfo_children`, geometry).
3. Treat compile/launch/widget-tree gates as secondary diagnostics, not authoritative.

This is the **quality-per-token path for installer UX bugs**: customer-visible proof first, internal diagnostics second.

**Lesson:** A live widget tree is not proof of a usable UI. Customer-facing desktop UI must be verified as pixels (screenshot), not as process state.

## Issue #12: Installer Seed-Memory Collision With Test-Memory Guard [FIXED v2.9.1]

**Trigger:** Every fresh install fails at stage 3 (Database Initialization). `.elefante-install.log` shows `blocked_test_memory_submission` with `Matched conditions: tag 'test' present`.
**Root cause:** Two correct surfaces collided. (a) Guard from BUG-011 in `src/core/orchestrator.py::add_memory()` rejects any submission with tag `"test"`. (b) `scripts/setup/init_databases.py::inject_seed_memory` submitted `tags=["seed", "test", "passcode"]` — legacy phrasing from the README's "test passcode" wording. The seed is a *production* memory (proves MCP handshake on first query); the `"test"` tag was wrong.
**Solution:** One-line change to seed payload: `tags=["seed", "passcode"]`. Content-search by "Indigo-Echo" still works.
**Lesson:** Guards that protect a data surface must be tested on *both* positive AND negative paths at the exact call sites that use them. Two individually-correct surfaces with intersecting value spaces ship a broken interaction. The installer should propagate the underlying rejection reason into the summary, not surface a generic "stage failed."

## Issue #13: Installer Reuse Mode Fails When `pip` Missing From .venv [FIXED]

**Trigger:** `.venv` has working Python 3.11 but install Step 2 fails with `No module named pip` and `Pip self-upgrade failed`.
**Root cause:** Reuse path validated only that `.venv/bin/python` existed. A `uv venv --python 3.11`-created environment is valid Python but pip-less. `install_dependencies()` called `python -m pip ...` without verifying pip first.
**Solution:** `scripts/setup/install.py::install_dependencies()` runs `python -m pip --version` before any dependency step; on failure, runs `python -m ensurepip --upgrade` and rechecks. Failure cites this entry directly.
**Lesson:** A reusable virtual environment must be validated at the *tool* level, not just the interpreter level. `python` exists ≠ `pip` exists.

## Issue #14: Installer Bundle Build Walks `.venv*` Backups [FIXED]

**Trigger:** `scripts/ci/build_installer_bundle.py` fails with `FileNotFoundError: '.venv.broken.<timestamp>/bin/python3'` after a workspace recovery left backup venvs in place.
**Root cause:** Bundle exclusion list contained exact `.venv` only. Broken-symlink backup directories like `.venv.broken.20260417-132309/` slipped through `should_exclude()` and crashed `zipfile.ZipInfo.from_file()`.
**Solution:** Top-level exclusion now uses prefix match: `TOP_LEVEL_PREFIX_EXCLUDED = (".venv",)`. Anything starting with `.venv` is excluded. Failure message cites this entry.
**Lesson:** Repo packagers must exclude *families* of local env directories, not the primary name. When a build step fails on workspace state, the failure should name the recovery doc, not dump a raw traceback.

---

## Issue #15: Test Manifest Leakage [BUG-032, FIXED, guarded]

**Trigger:** Pre-migration inspection found `~/.elefante/install-manifest.json` containing only temporary `pytest-of-*` VS Code paths.
**Root cause:** The low-level VS Code adapter accepted `manifest_home=None`; one direct test passed a temporary target but omitted the ownership root, so `Path.home()` received test records.
**Solution:** Make `manifest_home` mandatory at the low-level helper boundary. The production caller passes `Path.home()` explicitly and every direct test supplies an isolated home. Quarantine the residual manifest before migration.
**Guard:** `pytest tests/test_install_setup.py -k "manifest_home or transport_only_bridge" -v`.
**Lesson:** A helper that writes ownership state must receive its state root explicitly. A temporary artifact path does not imply an isolated metadata path.

## Issue #16: Lock Freshness Check Floated Transitive Dependencies [BUG-035, FIXED, guarded]

**Trigger:** PR #7's Python Quality job failed at `cmp requirements.lock ...` although the dashboard change did not modify Python requirements and the locked installation succeeded.
**Root cause:** The workflow copied only `requirements.txt` into an empty temporary directory. `uv pip compile` therefore selected newly published transitive versions instead of validating the checked-in pins.
**Solution:** Copy both `requirements.txt` and `requirements.lock` into the temporary directory before recompilation. `uv` now preserves valid transitive pins and changes the lock only when the declared requirements make that necessary.
**Guard:** `pytest tests/test_release_pipeline.py -k "lock_freshness" -v` verifies the copy → compile → compare order; a clean temporary reproduction must compare byte-for-byte.
**Lesson:** A lock-freshness gate must validate the existing lock, not ask the package index for today's preferred solution. Otherwise unrelated upstream releases make CI nondeterministic.

## Issue #17: Release Installer Launcher And First-Run UX Failure [BUG-037, FIXED, guarded]

**Trigger:** A stakeholder clicked the macOS download and received an extracted `elefante-installer-macOS` directory containing both `install.sh` and `install.bat`, with no obvious next action. Cross-platform asset inspection then found the published v2.11.1 Windows launcher contained ASCII backspace byte `0x08` in `scripts\setup\bootstrap_release_bundle.py`.
**Root cause:** The bundle generator treated archive structure as the acceptance contract. It emitted both OS wrappers into every platform bundle, gave users implementation filenames instead of a primary action, and embedded a Windows path in a normal Python triple-quoted string, so `\b` was decoded before ZIP creation. Existing tests asserted filenames only; they never decoded launchers, rejected control bytes, or exercised the customer entrypoint.
**Solution:** Emit platform-specific root launchers, add `START HERE.txt`, give macOS a double-clickable `Install Elefante.command`, give Windows a legible `Install Elefante.bat`, preserve Unix execute bits with explicit ZIP metadata, emit Windows CRLF, and use a raw string for the bootstrap path. Regression coverage reads the launcher bytes, rejects hidden control characters, checks exact entrypoints, and dry-runs the macOS customer launcher.
**Guard:** `pytest tests/test_installer_bundle.py -v`; build `macOS`, `Windows`, and `Linux` bundles; inspect archive root entries; execute `Install Elefante.command ... --dry-run` from a fresh extraction.
**Boundary:** The three published v2.11.1 installer assets were replaced under explicit storefront remediation authority on 2026-07-29. Their re-downloaded SHA-256 digests match the validated local archives; the macOS and Windows files remain launcher ZIPs, not signed native packages.
**Lesson:** A release ZIP is a customer interface. Verification must decode and execute the exact downloaded entrypoint, not merely prove that an archive contains files with plausible names.

## Issue #18: Installer Dry-Run Mutated The Live Installation [BUG-038, FIXED, guarded]

**Trigger:** Destination validation executed the downloaded macOS and Linux launchers with `--dry-run`. Both invocations moved the live `~/.elefante/app/current` installation to backups and placed the v2.11.1 payload before printing the delegated command.
**Root cause:** `bootstrap_release_bundle.py` called `place_payload()` before its `if args.dry_run` branch. The flag suppressed only the delegated installer process, not the bootstrap mutation, so the command name promised a stronger invariant than the control flow implemented.
**Solution:** Build the delegated command first and return immediately for `--dry-run`; payload placement, backup creation, and subprocess execution now occur only after that branch. The original v2.9.2 installation was restored from the first backup, and validation payloads were quarantined without deletion.
**Guard:** `pytest tests/test_installer_bundle.py -k "dry_run" -v` monkeypatches `place_payload` to fail if called and asserts an absent target stays absent. Artifact smoke uses an isolated `--install-root` and independently asserts it was not created.
**Lesson:** A dry-run flag is a no-mutation transaction boundary, not a “skip the last command” option. Test the absence of every durable side effect.

## Issue #19: Initializer Reported Retired Chroma Path [BUG-039, FIXED, guarded]

**Trigger:** The v2.12 release audit found that fresh-install configuration selected SQLite while the database initializer still described Chroma and reported `<data>/chroma` instead of the configured vector path.
**Root cause:** The initialization script predated the backend factory and retained a hard-coded diagnostic path after SQLite became the default.
**Solution:** Initialization and verification now use `vector_store.type`, `vector_store.persist_directory`, and `graph_store.database_path` from the active configuration.
**Guard:** `pytest tests/test_install_setup.py -k "configured_storage_paths" -v`.
**Lesson:** Backend selection and operator diagnostics must read the same configuration contract; a correct factory with stale initialization messages is still a broken install experience.

## Cross-bug pattern (extracted to `../lessons.md`)

The five most-recurring rules from the issues above:

1. **Read error messages literally** — "cannot be a directory" means don't pre-create. Issue #1.
2. **Library changelogs first** — version bumps break things. Issues #1, #4.
3. **Don't be helpful with resources libraries own** — eager mkdir, eager validation, eager state setup. Issues #1, #4.
4. **A live process is not a working UI** — pixels are the only proof. Issue #11.
5. **Test both positive and negative guard paths** — guards interact silently. Issue #12.

Distill any new repeating rule into `../lessons.md`. Postmortems hold the bug-specific narrative; `lessons.md` holds the cross-bug edge.

---

## Full historical narrative

The pre-distillation full narrative — including Cognitive Failure Analysis sections, "Why This Took So Long" reflections, Methodology Failures tables, Prevention Protocols, code-block solutions in full, and original Symptom/Problem prose — is preserved verbatim at [`_archive/installation-full.md`](_archive/installation-full.md).

This file (`installation.md`) is the **active retrieval surface** — atomic Trigger/Root cause/Solution/Lesson chunks that Elefante surfaces at high signal-per-token. The archive is the **historical context surface** — open it when the distilled chunk is insufficient and you need the full debugging arc.

Distilled here = what Elefante surfaces. Archived next to it = what informed the distillation. Neither is lost.
