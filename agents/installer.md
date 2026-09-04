---
PROTOCOL: installer
INVOKE: elefante-installer
PROTOCOL_VERSION: 2.15.2
LOAD_WHEN: Fresh install, broken venv, install failure, repair request, "install.sh failed", "install.bat failed", `.elefante-install-summary.txt` reports failure.
DIAGNOSTIC_QUESTION: "What state is broken in the install pipeline, and which of the four venv paths does it call for?"
AUTHORITY: This file owns the install protocol. Inline install troubleshooting in README/docs is forwarding only.
---

# Installer Agent

## Pre-flight

Read in this order before touching anything:

1. `.elefante-install-summary.txt` — last install verdict
2. `.elefante-install-status.txt` — current pipeline state
3. `.elefante-install.log` — full trace

Source-checkout installs: files live in repo root.
Release-bundle / DMG installs: files live in the stable install root (`~/.elefante/app/current` on macOS/Linux; `%LOCALAPPDATA%\Elefante\app\current` on Windows).

Without reading these three first, any fix is a guess.

## The Four `.venv` Paths

When `.venv` exists, the installer offers four choices. Pick by symptom:

| Symptom | Choose |
| ------- | ------ |
| `pip install` errors, missing wheels, version mismatch | **Delete + install fresh** (default) |
| Suspect venv state but want a rollback | **Backup `.venv.broken.<timestamp>` + install fresh** |
| Venv is healthy; only configs failed | **Reuse existing** |
| Need to halt without changes | **Abort** |

Keep `.venv.broken.*` until the repaired environment is verified. Removing a
local backup requires explicit scope and a clear operator report, not a product
changelog entry.

## Failure Routing

| Symptom | Route |
| ------- | ----- |
| Wrong Python version detected | Verify Python 3.11, 3.12, or 3.13 on PATH; rerun `scripts/setup/install.py` |
| SQLite / Kuzu initialization failed | `scripts/setup/init_databases.py` (idempotent); legacy ChromaDB only when explicitly configured |
| IDE not picking up MCP server | Hand off to `agents/restarter.md` |
| DMG install GUI broken | Check `scripts/ci/installer_gui.py`; see BUG-020 in `workspace/ISSUES.md` |
| AppKit installer (macOS) fails | Fall back to legacy Python/Tk path documented in `scripts/setup/install.py` |
| `.venv` corrupted mid-install | Choose backup-and-fresh; do not reuse |
| `git clone` failed (source-checkout) | Verify network + GitHub reachability; release bundle path is preferred |

## Authorized Scripts

`scripts/setup/install.py`, `scripts/setup/init_databases.py`, `scripts/setup/configure_vscode_bob.py`, `scripts/setup/configure_antigravity.py`, `scripts/setup/bootstrap_release_bundle.py`.

Anything outside `scripts/setup/` requires a different agent.

## Closure

After successful repair:

1. Verify the installer's `VERIFIED_COMPLETE` receipt and customer Doctor, then
   use a fresh configured host to Recall one known eligible memory. If there is
   no such memory, report execution and safe abstention separately from useful
   selection. The installer removes its disposable acceptance record; do not
   expect a permanent test passcode or create a replacement seed.
2. Update `workspace/ISSUES.md` Known Issues row if a recurring failure mode was encountered.
3. If a new failure class was discovered, append to `workspace/postmortems/installation.md`.
