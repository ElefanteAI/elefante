# Install Elefante

Use the platform archive from the
[latest published GitHub release](https://github.com/ElefanteAI/elefante/releases/latest).
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

The installer creates one stable customer runtime, one durable data root, and
one Elefante-managed backup location:

| Platform | Runtime | Data | Backups |
|---|---|---|---|
| macOS/Linux | `~/.elefante/app/current` | `~/.elefante/data` | `~/.elefante/backups` |
| Windows | `%LOCALAPPDATA%\Elefante\app\current` | `%USERPROFILE%\.elefante\data` | `%USERPROFILE%\.elefante\backups` |

Setup displays this backup location but does not ask the customer to choose a
different path. Recover uses the same location for backup, restore, and health
proof.

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
6. requires and configures Codex without overwriting a user-managed entry;
7. optionally configures only the compatibility-preview hosts selected by the
   customer;
8. installs a marked, reversible Recall-routing block for Codex;
9. verifies the daemon, real stdio bridge, certified Codex connection, Recall
   annotations, and one bounded read-only Recall probe; optional preview
   failures are reported but do not block customer readiness;
10. proves one generated project-scoped memory through the real Recall path,
   removes it, verifies that it is gone, and creates a verified local backup.

Rerunning the same installer repairs the runtime and preserves the durable data
root. A compatibility-preview host is connected only when explicitly selected;
it does not become part of the certified support lane.

After installation, open Elefante Home directly at
`http://localhost:8000`. The local daemon owns this loopback-only page and
connects it to a short-lived in-memory control session. No Chrome extension,
browser connector, IDE command, or special bookmarked URL is required. With one
active project, Home selects it automatically; with several, Home asks which
project to use before project-scoped actions.

### First-run choices: folders, memories, and privacy

Choose one or more specific, existing folders that represent a body of work—for
example, a repository or a dedicated project workspace. Do not choose your home
folder, the `Documents` folder itself, or Elefante's own data folder. If you work
across several repositories, add each repository separately.

The folder is a boundary, not an import source. Elefante does not scan or change
project files, and it does not automatically import every past session. It keeps
governed durable knowledge such as decisions, constraints, preferences, facts,
and lessons. Do not store passwords, API keys, access tokens, hidden reasoning,
or full transcripts as durable memories. Any optional session or file ingestion
must be explicitly enabled and remains subject to the same project boundary.

For a large existing history, start small: remember one real decision, ask a
later project question, verify that Recall selects the right memory, and create
a verified backup. Add more durable knowledge deliberately as it proves useful.
The goal is a trusted project context, not a second copy of every conversation.

### Project selection and isolation

On a fresh customer installation, the native macOS installer and the
cross-platform fallback require at least one real project folder. Each selected
folder receives an isolated memory scope. There is no shared-across-project
memory scope. An existing upgrade can remain in compatibility mode until its
older unassigned memories have been reviewed in Elefante Home. Elefante does not
scan or modify the project's files.

The headless equivalent is:

```bash
./.venv/bin/python scripts/setup/install.py \
  --project "Elefante=/absolute/path/to/elefante" \
  --project-mode strict
```

Repeat `--project NAME=ABSOLUTE_PATH` to register more than one folder. Paths
must already exist, must be absolute, and cannot be the filesystem root or the
user home directory. Clean customer-scope setup requires at least one project
and always enables strict isolation; a clean developer setup opts in with
`--project-mode strict`. Existing runtime upgrades do not accept project changes
inside the installer: they preserve current registrations and require review in
Elefante Home.

Strict intent is stored separately from the private Project Registry. Once
strict mode is chosen, a missing, corrupt, conflicting, or downgraded registry
fails closed instead of silently returning to unscoped compatibility behavior.
Installer failure restores the exact pre-install registry, intent marker, and
Home snapshot.

The package carries the selections into the installer and writes a private,
content-free acceptance receipt only after project isolation, disposable
Recall, cleanup, and the initial backup are all verified. The release workflow
must also prove install, data-preserving uninstall, and reinstall while keeping
the same project identities.

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

The installer has already proved the connection with generated disposable
content. Restart the IDE or agent host, then begin with a real project decision:

```text
Remember that this project's release owner is the founder.
```

In a later session, ask who owns the release. This checks useful continuity
without turning permanent demo data into part of the product.

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

A healthy customer candidate reports `ready=true`, `customer_ready=true`, a
matching build identity, a healthy loopback daemon, a verified Codex connection
and Recall path, and explicit preview-host coverage. An uncovered preview does
not fail the required Codex validation. `doctor` is read-only: it does not start services,
rewrite host configuration, migrate data, or repair the installation.

To print the installed package version without relying on a document header:

```bash
# macOS/Linux
(
  cd ~/.elefante/app/current
  .venv/bin/python -c 'from src import __version__; print(__version__)'
)
```

```powershell
# Windows PowerShell
Set-Location "$env:LOCALAPPDATA\Elefante\app\current"
& .\.venv\Scripts\python.exe -c "from src import __version__; print(__version__)"
```

## 5. Host coverage

The supported installer has ownership-safe, contract-tested adapters for:

- VS Code Copilot
- Claude Code
- Cursor
- Kiro
- Continue
- Zed
- Gemini CLI
- Codex
- OpenClaw

For the supported release workflow, Codex is the required validation target.
All other adapters are optional compatibility previews and cannot make the
customer installation ready by themselves. Adapter coverage says nothing about
task quality. IBM Bob and
Antigravity remain preview integrations. Agent Zero is a documented community
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
- **Build identity mismatch:** reinstall the archive that matches the installed
  build; do not edit identity files manually.

### Create a privacy-safe support report

In Elefante Home, open **Recover → Support report**. Review the complete
**Included** and **Never included** lists, confirm, and download the verified
ZIP. Elefante creates the ZIP locally and does not send it anywhere.

The report contains product/build identity, OS and Python version, agent and
Recall readiness, diagnostic codes, backup validity counts, and bounded
lifecycle receipts. It does not contain memory content, project names or paths,
prompts, questions, answers, transcripts, credentials, environment values,
host configuration contents, or logs. Do not substitute an unreviewed log or
environment dump. If Home cannot run, preserve the installation and use the
official-package support fallback once available; do not improvise by copying
the durable data root.

## 7. Data, upgrade, and uninstall

Fresh installations use SQLite vectors plus Kuzu. Explicit paths in
`config.yaml` remain authoritative. Legacy ChromaDB is support-only and is
never migrated or deleted silently.

Stop the daemon before copying, importing, or restoring durable data. CSV is an
analysis export. JSON supports additive memory migration but omits graph
topology and is not a full backup. Use [Backup and rollback](rollback.md) for
the checksummed binary path.

The installer-owned lifecycle uninstaller can detach only unchanged
installer-owned service definitions, host entries, and Recall guidance. It
preserves the app and data and is not a complete product uninstall.

The official-package uninstall flow owns complete uninstall from outside the
installed app. Use the package that exactly matches the installed build:

- macOS: open `Uninstall Elefante.command`;
- Windows: open `Uninstall Elefante.bat`;
- Linux: run `chmod +x uninstall.sh && ./uninstall.sh`.

The package shows the exact impact and requires the customer to type
`UNINSTALL`. It stops Elefante, creates a new backup and independently verifies
that the backup can be restored, removes the active app plus only unchanged
Elefante-owned connections, verifies that managed memory data did not change,
and writes a private completion receipt. Modified or unverified customer
configuration is preserved. The durable data root is never deleted by this
operation.

If the customer later installs Elefante again, the matching installer
reattaches the preserved data root and removes the temporary preservation
pointer only after Doctor and a live Recall check pass. A stale plan, changed
data, mismatched package, unsafe path, failed backup, or unverified removal
fails closed or directs the customer to a privacy-safe support report. This
package flow must pass exact packaged install → uninstall → reinstall acceptance
before it is treated as a release.

Developers reproducing or changing Elefante should start at
[the repository developer entrypoint](../../AGENTS.md), not this customer
procedure.
