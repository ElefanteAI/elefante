# Install Elefante v2.13.0

Use the platform archive from the
[v2.13.0 GitHub release](https://github.com/ElefanteAI/elefante/releases/tag/v2.13.0).
This is the supported customer path.

## Requirements

- macOS, Windows, or Linux
- Python 3.11, 3.12, or 3.13
- at least 5 GB of free disk space
- internet access while the locked runtime dependencies are installed

Git, Node.js, and a source checkout are not required. The dashboard build is
already included.

## 1. Download and verify

Download `SHA256SUMS` and the matching universal installer:

- `elefante-installer-macOS.zip`
- `elefante-installer-Windows.zip`
- `elefante-installer-Linux.zip`

Verify the archive before opening it:

```bash
# macOS
shasum -a 256 -c SHA256SUMS --ignore-missing

# Linux
sha256sum -c SHA256SUMS --ignore-missing
```

On Windows PowerShell, compare:

```powershell
Get-FileHash .\elefante-installer-Windows.zip -Algorithm SHA256
```

with the matching line in `SHA256SUMS`.

ZIP installers are the universal release contract. A signed/notarized macOS
DMG or Authenticode-verified Windows EXE may also appear on the release when the
platform credential gates succeed. Elefante never publishes an unsigned native
package as though it were signed.

## 2. Run the installer

Extract the ZIP first. Do not run a launcher from inside the archive.

- **macOS:** open `Install Elefante.command`. If macOS asks for confirmation,
  Control-click it, choose **Open**, then choose **Open** again.
- **Windows:** open `Install Elefante.bat`.
- **Linux:** run `chmod +x install.sh && ./install.sh`.

The installer creates one stable customer runtime and one durable data root:

| Platform | Runtime | Data |
|---|---|---|
| macOS/Linux | `~/.elefante/app/current` | `~/.elefante/data` |
| Windows | `%LOCALAPPDATA%\Elefante\app\current` | `%USERPROFILE%\.elefante\data` |

One loopback-only daemon owns SQLite and Kuzu. Hosts that require stdio use a
storage-free bridge; they do not open either database.

## 3. What installation changes

The installer:

1. checks Python, disk, paths, and the customer profile;
2. places the runtime in the stable per-user location;
3. installs the exact hash-locked runtime dependencies;
4. initializes SQLite vectors and Kuzu; private media storage is created on the
   first attachment;
5. installs the user-level daemon;
6. configures every detected compatible host without overwriting user-managed
   entries;
7. installs a marked, reversible Recall-routing block for Codex;
8. verifies the daemon, real stdio bridge, detected hosts, Recall annotations,
   and one bounded read-only Recall probe;
9. stores one harmless `Indigo-Echo` seed memory for the first connection check.

Rerunning the same installer repairs the runtime and connects compatible hosts
installed later. It preserves the durable data root.

### Build identity

The archive, installed payload, ownership manifest, and `doctor` report must
agree on:

- semantic version;
- exact clean source commit;
- publication channel (`candidate` or `release`).

A missing, legacy, dirty, development-channel, version-mismatched, or
commit-mismatched customer runtime is not reported customer-ready. Reinstalling
a known-good release restores its runtime identity without replacing the data
root.

## 4. Verify the installation

Restart the IDE or agent host, then ask:

```text
What is my Elefante test passcode?
```

The expected answer is `Indigo-Echo`. This proves the installed Recall path; it
does not prove general task-quality lift.

Run the read-only doctor if the host does not answer correctly:

```bash
# macOS/Linux
~/.elefante/app/current/.venv/bin/python \
  ~/.elefante/app/current/scripts/lifecycle/doctor.py --json
```

```powershell
# Windows PowerShell
& "$env:LOCALAPPDATA\Elefante\app\current\.venv\Scripts\python.exe" `
  "$env:LOCALAPPDATA\Elefante\app\current\scripts\lifecycle\doctor.py" --json
```

A healthy customer runtime reports `ready=true`, `customer_ready=true`, a
matching build identity, a healthy loopback daemon, and no uncovered detected
hosts. `doctor` is read-only: it does not start services, rewrite host
configuration, migrate data, or repair the installation.

## 5. Host coverage

The v2.13.0 installer has ownership-safe, contract-tested adapters for:

- VS Code Copilot
- Claude Code
- Cursor
- Kiro
- Continue
- Zed
- Gemini CLI
- Codex
- OpenClaw

These adapters are **compatible**, not vendor-certified. IBM Bob and
Antigravity are preview integrations. Agent Zero is a documented community
path. See [Configure a host](configure-ide.md) for exact status and manual
fallbacks.

## 6. If installation fails

Read the files printed by the installer in this order:

1. `.elefante-install-summary.txt` — final verdict and failed stage
2. `.elefante-install-status.txt` — latest pipeline state
3. `.elefante-install.log` — detailed trace

For a release install, they live in the stable runtime root. Do not delete the
data root, edit host JSON by guesswork, remove Kuzu lock files, or factory-reset
as a first response.

Common blockers:

- **Unsupported Python:** install Python 3.11–3.13 and rerun.
- **Host not connected:** close the host, rerun the installer, then restart the
  host.
- **User-managed `elefante` entry:** the installer preserves it and reports a
  conflict instead of overwriting it.
- **Daemon unhealthy:** follow [Restart Elefante](restart.md), then rerun
  `doctor`.
- **Kuzu ownership or lock error:** follow
  [Kuzu troubleshooting](kuzu-troubleshooting.md).
- **Build identity mismatch:** reinstall the verified v2.13.0 archive; do not
  edit identity files manually.

## 7. Data, upgrade, and uninstall

Fresh installations use SQLite vectors plus Kuzu. Explicit paths in
`config.yaml` remain authoritative. Legacy ChromaDB is support-only and is
never migrated or deleted silently.

Stop the daemon before copying, importing, or restoring durable data. CSV is an
analysis export. JSON supports additive memory migration but omits graph
topology and is not a full backup. Use [Backup and rollback](rollback.md) for
the checksummed binary path.

Use the installed lifecycle uninstaller so only unchanged installer-owned
service definitions, host entries, and Recall guidance are removed. Uninstalling
the runtime does not authorize deletion of the durable data root.

Developers reproducing or changing Elefante should start at
[the repository developer entrypoint](../../AGENTS.md), not this customer
procedure.
