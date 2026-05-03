# PRD: Elefante Installer Procedure

> **Status**: DRAFT — Phase 1 only
>
> **Author**: Agent
>
> **Date**: 2026-04-16
>
> **Scope**: Ship a downloadable Elefante installer product that removes `git clone` from the end-user install path and wraps the current Elefante installer as the single source of truth

---

## 1. Problem Statement

Elefante already has a real installer.

That installer is `scripts/setup/install.py`, with thin wrappers at `install.sh` and `install.bat`.

The current failure is not missing install logic.

The failure is the product entrypoint.

Today an end user must still:

- find the GitHub repository
- clone it
- enter the repo root
- know which wrapper to run
- avoid running it from a disposable path that will later break IDE configuration

That is not a finished installation product.

### Core Requirement

Phase 1 must create a downloadable Elefante installer product that installs **Elefante as it exists now**.

It must not introduce provider selection yet.

It must not fork the installer logic into a second implementation.

It must not require `git clone` in the end-user flow.

---

## 2. Honest Assessment: Current Elefante Reality

| Surface | Current State |
| ------- | ------------- |
| `scripts/setup/install.py` | Real installer authority: pre-flight checks, `.venv`, dependencies, dashboard build, DB init, dashboard snapshot, IDE config, bootstrap verification, health check, MCP handshake |
| `install.sh` / `install.bat` | Thin source-checkout wrappers that find Python and delegate into `install.py` |
| `scripts/setup/configure_vscode_bob.py` | Writes IDE MCP config using absolute paths to the installed Elefante tree |
| `scripts/setup/configure_antigravity.py` | Same absolute-path pattern for Antigravity |
| `scripts/verify/verify_health.py` | Core install verification |
| `scripts/verify/verify_mcp_handshake.py` | MCP liveness verification |
| `scripts/verify/verify_e2e_tests.py` | Only maintained whole-surface live proof |
| `elefante.spec` | Packages `src/main.py`, which is the app/runtime entrypoint, not the end-user installer |
| `.github/workflows/build-binaries.yml` | Builds application binaries, not a first-run installer product |

### Current Installer Sequence

From `scripts/setup/install.py`, the live install flow is:

1. Purge bytecode
2. Run pre-flight checks
3. Resolve `.venv` handling
4. Install Python dependencies
5. Build dashboard UI if needed
6. Initialize databases
7. Generate dashboard snapshot
8. Configure IDE / MCP integration
9. Verify agent bootstrap files
10. Run health check
11. Run MCP handshake verification

That sequence is already the best authority in the repo.

Phase 1 should wrap it.

It should not replace it.

---

## 3. Critical Constraints

### 3.1 No Second Installer Engine

The bootstrap installer may orchestrate setup, packaging, placement, status display, and cancellation.

It must **not** duplicate Elefante's dependency, database, or IDE configuration logic in a separate codepath.

`scripts/setup/install.py` remains the single authority for Elefante installation.

### 3.2 No Git Clone In End-User Flow

The downloadable installer must consume a shipped Elefante release payload.

It must not ask the user to clone the repo.

It must not depend on Git being installed for a standard product install.

### 3.3 No Provider Choices In Phase 1

OpenAI, xAI, DeepSeek, Ollama model menus, runtime profile prompts, and any `.env` provider flow are all deferred.

Phase 1 installs Elefante exactly as Elefante works today.

### 3.4 No False "Installed" Claim From A Disposable Path

This matters because Elefante's IDE configuration writes absolute paths.

If the user runs the installer from `Downloads`, a temp unzip folder, or a moved release directory, MCP configuration will later point to a path that no longer exists.

So the product installer must place Elefante in a stable install location before delegating into `install.py`.

---

## 4. Product Decision

Phase 1 ships a **bootstrap installer**.

This bootstrap installer is a product entrypoint that:

- starts from a downloadable Elefante release bundle
- places Elefante into a durable install directory
- keeps a visible terminal window open
- shows the install state clearly at all times
- exposes a cancel path at safe checkpoints
- writes status, summary, and log files
- delegates the real install work into `scripts/setup/install.py`

### What Phase 1 Is Not

- not a new Elefante installer implementation
- not a provider-selection wizard
- not a runtime-profile feature
- not the current `elefante.spec` app bundle repackaged as an installer

---

## 5. User Experience Contract

The installer must feel like a product, not a repo ritual.

### 5.1 First-Run Flow

The target flow is:

1. User downloads the Elefante installer bundle for their platform
2. User runs one visible entrypoint
3. Installer places Elefante in a stable install location
4. Installer runs the real Elefante install flow
5. Installer ends with a truthful summary and the next required action

### 5.2 Terminal UX Requirements

The installer runs in a visible terminal window.

Required behavior:

- show current phase number and phase name
- show what is happening now
- show a continuously rolling spinner while work is active; preferred pattern is a braille-style loop such as `⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏`, repeated for the full duration of the active step
- show what completed and what failed
- keep the most important current state visible, not buried in scrollback
- show where logs and summaries are written
- show how to cancel

### 5.3 Motion Requirements

Lightweight terminal motion is allowed.

The rolling spinner is required during active work.

Examples:

- spinner
- progress bar
- staged section transitions
- highlighted current phase

Hard rule:

Motion must never replace information.

If rich terminal output fails or the terminal does not support it, the installer must fall back to plain text and continue successfully.

### 5.4 Cancel Requirements

Cancel must be explicit.

The installer must allow cancellation at safe checkpoints before destructive actions or before entering the next major stage.

If cancelled, it must say what already changed and what did not.

---

## 6. Bootstrap Architecture

### 6.1 Release Artifact

Phase 1 should ship a platform-specific installer bundle.

That bundle contains:

- a bootstrap entrypoint for the platform
- the Elefante release payload
- prebuilt dashboard assets
- install metadata such as version and manifest information

Hard rule:

The bundle is the install source.

It is not a Git checkout.

### 6.2 Stable Install Location

The installer must copy or unpack Elefante into a durable location before writing MCP configuration.

Default target:

- macOS / Linux: `~/.elefante/app/current`
- Windows: `%LOCALAPPDATA%\Elefante\app\current`

Why this matters:

- IDE config uses absolute paths
- the install must survive cleanup of `Downloads`
- upgrades and repairs need one canonical app root

### 6.3 Bootstrap Responsibilities

The bootstrap layer is responsible for:

- locating or creating the stable install directory
- unpacking or copying the Elefante payload there
- checking for supported Python and surfacing a clear blocker if missing
- launching `scripts/setup/install.py` from the installed payload
- passing status/log file locations into the delegated installer
- preserving a visible terminal window for the whole run

### 6.4 Delegated Installer Responsibilities

The delegated installer remains responsible for:

- `.venv` handling
- dependency installation
- database initialization
- dashboard snapshot generation
- IDE configuration
- bootstrap verification
- health verification
- MCP handshake verification

If new UX is added inside `install.py`, it must be added as instrumentation around the existing steps, not as duplicate logic.

### 6.5 Dashboard Build Contract

Phase 1 should not force end users to install Node.js just to view the dashboard.

The installer bundle should ship with prebuilt dashboard assets.

`install.py` should prefer bundled `src/dashboard/ui/dist` output when present and only build the UI when that artifact is absent.

That preserves the current installer behavior while removing an avoidable end-user dependency.

---

## 7. Installer State Files

Phase 1 should add product-grade install state files in the installed Elefante root.

Required files:

- `.elefante-install-status.txt` — current active stage
- `.elefante-install-summary.txt` — stage-by-stage completion ledger
- `.elefante-install.log` — readable transcript of the installer run

Requirements:

- updated throughout the run
- readable without the terminal open
- truthful on failure and cancel
- safe to inspect when support is needed

---

## 8. Verification Strategy

### 8.1 Core Principle

The installer is only real when the installed Elefante payload is real.

So phase-1 validation must stay attached to maintained Elefante verifiers.

### 8.2 Required Proofs

| Verifier | Responsibility |
| -------- | -------------- |
| `scripts/verify/verify_health.py` | Core install health |
| `scripts/verify/verify_mcp_handshake.py` | MCP liveness |
| `scripts/verify/verify_e2e_tests.py` | Release-level live surface proof |

### 8.3 Seed Passcode Limitation

The passcode prompt in current install UX is not sufficient as the primary proof.

Why:

- `scripts/setup/init_databases.py` currently logs `Successfully injected seed memory.` after `add_memory(...)`
- the orchestrator can still block that memory via `blocked_test_memory_submission`
- the debug record in `workspace/postmortems/memory.md` already documents this false-positive path

Therefore:

- phase-1 installer success must be based on maintained verifiers first
- the passcode prompt may remain a demo step only after `init_databases.py` truthfully checks the write result

### 8.4 Truthful Exit Summary

The installer must end with a summary shaped like this:

```text
Payload placement: COMPLETE
Core install: VERIFIED
IDE configuration: COMPLETE
Next action: restart your IDE
```

or, on failure:

```text
Payload placement: COMPLETE
Core install: FAILED at MCP handshake verification
See: .elefante-install.log
```

No vague success banner without stage truth.

---

## 9. Exact Changes Required

| File / Surface | Required Change |
| -------------- | --------------- |
| `scripts/setup/install.py` | Add machine-readable phase/status hooks, safe cancel checkpoints, and truthful final summary output |
| `scripts/setup/init_databases.py` | Fix seed-memory false-success before the passcode demo is treated as install proof |
| `install.sh` / `install.bat` | Keep as source-distribution wrappers; do not overload them into a second installer architecture |
| New bootstrap installer entrypoints | Add platform-specific product entrypoints that place payload in a stable install dir and delegate into `install.py` |
| Release packaging workflow | Build installer bundles from a shipped Elefante payload with prebuilt dashboard assets |
| `elefante.spec` / release messaging | Stop treating the current app-runtime bundle as the installer surface |
| `tests/test_release_pipeline.py` | Extend guards for installer artifact selection and packaging assumptions |
| `docs/how-to/install.md` | Rewrite shipped install docs after implementation to match the product path |

---

## 10. Success Criteria

| # | Criterion |
| - | --------- |
| 1 | End-user installation requires no `git clone` |
| 2 | Elefante is installed into a stable durable path, not run from `Downloads` |
| 3 | `scripts/setup/install.py` remains the single installer authority |
| 4 | The installer keeps a visible terminal window open for the entire run |
| 5 | The installer always exposes current phase, log path, and cancel behavior |
| 6 | Status, summary, and log files are written throughout the run |
| 7 | Dashboard assets are available without requiring Node.js on the user machine when bundled output exists |
| 8 | Installer success is backed by maintained Elefante verifiers |
| 9 | No provider-selection or cloud credential prompts appear in phase 1 |

---

## 11. Risks And Constraints

| Risk | Why It Matters | Mitigation |
| ---- | -------------- | ---------- |
| Second installer logic path drifts from `install.py` | Fastest way to break Elefante installation | Keep `install.py` authoritative |
| Running from temp or download paths breaks MCP later | IDE configs store absolute paths | Install into a stable location before configuration |
| Missing Python remains a first-run blocker | Phase 1 still depends on Python | Surface a precise blocker and keep Python bootstrap as a separate problem if needed |
| Release bundle omits dashboard assets | End-user dashboard degrades or needs Node | Bundle `dist` assets in the installer payload |
| Installer claims success based on the passcode demo alone | Existing seed-memory path is not fully truthful | Gate success on maintained verifiers |
| Release artifact size grows unnecessarily | Already a known Elefante release risk | Package only the installer payload needed for end-user install |

---

## 12. Phase 2 Is Explicitly Deferred

Phase 2 may later add:

- LLM provider choices
- OpenAI / xAI / DeepSeek selection
- Ollama model choices
- runtime provider profile persistence
- provider-aware verification

Phase 2 must not begin until phase 1 is tested and working as intended.

That gate is intentional.

Phase 1 is about making Elefante installable as a product.

Phase 2 is about optional connected runtime choices.

---

## 13. Open Questions

1. Should the durable app root be exactly `~/.elefante/app/current` and `%LOCALAPPDATA%\Elefante\app\current`, or should the product use a different stable path?
2. Should Linux ship the same full installer bundle in phase 1, or follow after Windows and macOS validation?
3. Does phase 1 also need Python bootstrap, or is a clear Python blocker acceptable for the first product release?
4. Should the product installer launch a post-install verifier automatically, or only summarize the commands/results?

---

*This PRD documents phase 1 only. Provider-choice work is intentionally deferred until the downloadable Elefante installer is real, tested, and truthful.*
