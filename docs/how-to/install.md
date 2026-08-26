# Install Elefante v2.12.3

Use the platform archive from the
[v2.12.3 GitHub release](https://github.com/ElefanteAI/elefante/releases/tag/v2.12.3).
This is the customer path. A source checkout is a separate developer runtime.

## Requirements

- Python 3.11, 3.12, or 3.13
- At least 5 GB free disk space
- macOS, Windows, or Linux
- Internet access while locked runtime dependencies are installed

Git and Node.js are not required for the released customer archive. The
dashboard build is already included.

## 1. Download and verify

Download the platform ZIP and `SHA256SUMS` from the same release:

- `elefante-installer-macOS.zip`
- `elefante-installer-Windows.zip`
- `elefante-installer-Linux.zip`

Verify before opening it:

```bash
# macOS
shasum -a 256 -c SHA256SUMS --ignore-missing

# Linux
sha256sum -c SHA256SUMS --ignore-missing
```

On Windows PowerShell, compare `Get-FileHash <archive> -Algorithm SHA256` with
the matching line in `SHA256SUMS`.

## 2. Run the installer

Extract the ZIP first. Do not run a launcher from inside the archive.

- **macOS:** double-click `Install Elefante.command`. If macOS requests
  confirmation, Control-click it, choose **Open**, then **Open** again.
- **Windows:** double-click `Install Elefante.bat`.
- **Linux:** run `chmod +x install.sh && ./install.sh`.

The v2.12.3 macOS archive preserves the executable permission required by
Finder. Administrator access and manual permission repair are not part of the
normal flow. Signed and notarized native packaging is Upcoming.

The installer creates one stable customer runtime and one local memory store:

| Platform | Runtime | Data |
|---|---|---|
| macOS / Linux | `~/.elefante/app/current` | `~/.elefante/data` |
| Windows | `%LOCALAPPDATA%\Elefante\app\current` | `%USERPROFILE%\.elefante\data` |

One loopback-only daemon is the durable store owner. Every detected compatible
host connects through a transport-only bridge; hosts do not open SQLite or Kuzu
themselves.

## 3. What installation changes

The installer:

1. checks Python, disk, paths, and the requested installation profile;
2. places the runtime in the stable per-user location;
3. creates a virtual environment and installs the hash-locked client runtime;
4. initializes SQLite vectors and Kuzu;
5. installs the user-level daemon;
6. configures every detected compatible host without overwriting user-managed
   entries;
7. verifies the daemon and real stdio bridge before reporting success;
8. stores a harmless `Indigo-Echo` seed memory for the first connection check.

Rerunning the same installer repairs the runtime and connects compatible hosts
installed later. It preserves the existing memory store.

### Build identity boundary

The published v2.12.3 installer records its semantic version, but its schema-v2
installation manifest does not record the exact source commit or release
channel. Do not use version alone to attribute development behavior to the
published release. The provenance-aware identity guard exists in the active
development checkout and is not part of the v2.12.3 customer contract.

The next provenance-aware customer candidate records and cross-checks the
semantic version, exact clean source commit, and `candidate` or `release`
channel in the archive, installed payload, ownership manifest, and `doctor`
report. A legacy, dirty, development-channel, or mismatched customer runtime is
not reported customer-ready. Reinstalling a known-good published archive
restores that archive's identity without changing the memory data root.

## 4. Verify the customer installation

Restart the IDE or agent host, then ask:

```text
What is my Elefante test passcode?
```

The expected seed value is `Indigo-Echo`. This confirms retrieval, not general
task-quality improvement.

Run the read-only doctor if needed:

```bash
# macOS / Linux
~/.elefante/app/current/.venv/bin/python \
  ~/.elefante/app/current/scripts/lifecycle/doctor.py
```

```powershell
# Windows PowerShell
& "$env:LOCALAPPDATA\Elefante\app\current\.venv\Scripts\python.exe" `
  "$env:LOCALAPPDATA\Elefante\app\current\scripts\lifecycle\doctor.py"
```

`doctor` is diagnostic. It does not start services, change host configuration,
migrate data, or repair build identity. A provenance-aware customer runtime
reports matching `installation.version`, `installation.source_commit`, and
`installation.release_channel` values.

## 5. Supported installation surfaces

Released adapter coverage exists for VS Code, Cursor, Kiro, Gemini CLI,
Claude Code, Codex, and OpenClaw. These are **compatible**, not certified: adapter
tests pass, but complete host-driven lifecycle certification is still
incomplete. IBM Bob and Antigravity are preview surfaces. Agent Zero is a
community path. See [`configure-ide.md`](configure-ide.md).

The source adapters are:

- `scripts/setup/configure_vscode_bob.py`
- `scripts/setup/configure_cursor_kiro.py`
- `scripts/setup/configure_antigravity.py`
- `scripts/setup/configure_cli_agents.py`

These names are developer references; customers normally rerun the release
installer instead of invoking adapters directly.

## 6. If installation fails

Read the files printed by the installer, in this order:

1. `.elefante-install-summary.txt` — final verdict and failed stage
2. `.elefante-install-status.txt` — latest pipeline state
3. `.elefante-install.log` — detailed trace

For a release install they are in the stable runtime root. Do not delete the
existing data directory, edit IDE JSON by guesswork, or run a factory reset as a
first response.

Common blockers:

- **No supported Python:** install Python 3.11–3.13 and rerun.
- **A host is not connected:** close the host, rerun the installer, then restart
  the host.
- **User-managed MCP entry exists:** Elefante preserves it and reports a
  conflict rather than overwriting it.
- **Daemon health fails:** use [`restart.md`](restart.md), then rerun `doctor`.
- **Kuzu ownership or lock error:** use
  [`kuzu-troubleshooting.md`](kuzu-troubleshooting.md).

## 7. Storage configuration

Fresh installs use the configured embedded vector store, SQLite by default,
plus Kuzu. Paths explicitly configured in `config.yaml` remain authoritative.
Legacy ChromaDB is support-only and is never migrated or deleted silently.

Stop the daemon before copying or restoring durable data. JSON/CSV exports are
for inspection and are not restorable backups; use [`rollback.md`](rollback.md)
for backup and recovery.

## 8. Developer source path

Developers should clone the exact release tag when reproducing customer
behavior, or use their approved development branch for product work:

```bash
git clone --branch v2.12.3 --depth 1 https://github.com/ElefanteAI/elefante.git
cd elefante
chmod +x install.sh
./install.sh
```

A source checkout cannot replace an existing customer-global runtime. Use its
local `.venv` and the verification routes in `tests/README.md`. Customer
archives intentionally exclude developer workspace, tests, migration tools,
and release utilities.

## 9. Uninstall and data control

Use the installed lifecycle script so only unchanged installer-owned service
and host entries are removed. Review dry-run output before applying it.
Uninstalling the runtime does not imply permission to delete `~/.elefante/data`;
that directory contains the user's memories.

For exact uninstall, backup, and restore commands, see [`rollback.md`](rollback.md)
and the lifecycle scripts included in the customer runtime.
