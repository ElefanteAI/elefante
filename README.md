# Elefante

<p align="center">
  <img src="docs/assets/Elefante Logo 1024 black 2.png" alt="Elefante" width="256">
</p>

**A private, persistent second brain for the AI tools you already use.**

Elefante stores durable preferences, decisions, facts, constraints, and lessons
on your machine, then supplies a small governed subset when an agent needs prior
context. It is an MCP memory engine—not an LLM, agent runtime, chat product, or
cloud memory service.

**v2.13.0** — Current published release.

17 tools · 2 prompts · Python 3.11–3.13 · MCP 1.28.1

## What a user can do

- Recall relevant prior context with one bounded, read-only `elefante-Recall`
  call. Irrelevant or unsafe candidates produce an explicit abstention.
- Store, search, amend, archive, consolidate, and resolve durable memories with
  search-before-write protection and user-governed retention rules.
- Connect memories to entities and relationships in a local knowledge graph.
- Attach bounded local image, audio, and video files. Elefante stores and
  integrity-checks them locally; it does not perform OCR, transcription, model
  analysis, or network upload.
- Inspect memory health, relationships, retrieval evidence, usage summaries,
  and Signal Cards in a loopback-only, snapshot-driven dashboard.
- Run the Session Distiller in the foreground, including an opt-in watch mode
  for new or changed supported chat-session files.
- Exchange an explicit allowlist of memories through signed, scope-bound local
  Team Sync bundles. Elefante provides the bundle contract, not a cloud sync
  transport.
- Opt into a separate metadata-only Session Intelligence ledger for provider
  usage, rate-card-backed cost calculation, outcome records, Signal Cards, and
  aggregate training hypotheses. Unknown usage or pricing remains `UNKNOWN`.
- Feed bounded file, terminal-error, or conversation event envelopes to the
  local `/events/surface` endpoint for literal-trigger retrieval. Elefante does
  not silently intercept host activity or persist the event body.

## How it works

```text
MCP host
   │  local HTTP or storage-free stdio bridge
   ▼
Elefante daemon ── governed retrieval ── SQLite vectors
   │                                  └─ Kuzu relationships
   └─ redacted snapshot ───────────────► local dashboard
```

```text
Goal → Perceive → Plan → Act → Observe → Update → Repeat
          ↑                              ↓
     retrieve context              preserve verified outcomes
          └──────────── Elefante ────────────┘
```

The agent owns the goal, plan, tools, and stopping decision. Elefante
participates at two points: it retrieves durable context before or during a
task, and it preserves verified outcomes when the user or workflow explicitly
asks it to write. Elefante is not an LLM, an agent runtime, or a domain adviser.

Normal retrieval is read-only. Search exposure does not reinforce ranking or
prove that a memory improved a task. Conflicting evidence is withheld until it
is resolved; Smart Merge is dry-run-first and requires explicit authority when
there is no unambiguous protected winner.

## Install

Download the matching `elefante-installer-<OS>.zip` and `SHA256SUMS` from the
[latest GitHub release](https://github.com/ElefanteAI/elefante/releases/latest),
verify the checksum, extract the archive, then use its single platform launcher:

- macOS: open `Install Elefante.command`. If macOS asks for confirmation,
  Control-click it, choose **Open**, then choose **Open** again. Administrator
  access and Terminal commands are not required.
- Windows: open `Install Elefante.bat`
- Linux: run `chmod +x install.sh && ./install.sh`

The installer creates one stable per-user runtime and one local data root, then
connects every detected compatible host it can verify.

- macOS/Linux runtime: `~/.elefante/app/current`
- Windows runtime: `%LOCALAPPDATA%\Elefante\app\current`

ZIP installers are the universal release contract. A signed/notarized macOS
DMG or Authenticode-verified Windows EXE is published only when the release
workflow completes credential-gated notarization or Authenticode verification;
an unsigned native package is never substituted as a release asset.

For source installation, repair, checksum commands, and uninstall details, see
the [installation guide](docs/how-to/install.md).

**If installation fails:** read the persisted recovery files in this order:

1. `.elefante-install-summary.txt`
2. `.elefante-install-status.txt`
3. `.elefante-install.log`

The installer prints their exact location. Do not delete the data root or edit
host configuration by guesswork.

## Verify the installation

Restart the host, then ask:

```text
What is my Elefante test passcode?
```

The installer creates one harmless seed memory; the expected answer is
`Indigo-Echo`. If the host does not route the question automatically, ask it to
call `elefante-Recall` once.

The installed runtime also provides a read-only doctor:

```bash
cd ~/.elefante/app/current
./.venv/bin/python scripts/lifecycle/doctor.py --json
```

A customer-ready installation reports `customer_ready=true` and identifies any
detected host that was not connected or verified.

## Host coverage

The v2.13.0 installer has ownership-safe, contract-tested adapters for VS Code
Copilot, Claude Code, Cursor, Kiro, Continue, Zed, Gemini CLI, Codex, and
OpenClaw. These integrations are **compatible**, not vendor-certified.

IBM Bob and Antigravity remain preview integrations because their full host
lifecycle has not been independently certified. Agent Zero remains a documented
community path. Planned hosts are not advertised as supported.

## Public MCP surface

The default customer profile exposes 17 tools + 2 prompts.

| Area | Surface |
|---|---|
| Recall | `elefante-Recall` |
| Memory | `elefante-Memory` |
| Graph | `elefante-GraphConnect`, `elefante-GraphQuery` |
| Context | `elefante-ContextGet`, `elefante-SessionsList` |
| Tasks | `elefante-TaskCreate`, `elefante-TaskUpdate`, `elefante-TaskGraph` |
| ETL | `elefante-ETLProcess`, `elefante-ETLClassify` |
| Directives | `elefante-DirectiveAdd`, `elefante-DirectiveList`, `elefante-DirectiveRemove` |
| System | `elefante-System`, `elefante-SystemStatusGet`, `elefante-DashboardOpen` |
| Prompts | `elefante-context`, `elefante-grounding` |

See the [tool and prompt reference](docs/reference/tools.md) for parameters,
result contracts, and safety rules.

## Privacy and product boundaries

- Memory, graph, media, Session Intelligence, and dashboard data stay local by
  default. Elefante has no product telemetry.
- The daemon and dashboard bind to loopback. Exposing either over a network is
  an operator decision that requires a separately authenticated boundary.
- Context intentionally sent to an AI host remains subject to that provider's
  policy.
- Token estimates are local heuristics. Dollar cost is authoritative only when
  provider-actual usage and a matching dated rate card are both present.
- Task Intelligence evaluation exists for developers, remains default-off, and
  has not established representative multi-task outcome lift. It is not part
  of the 17-tool customer profile or a public performance claim.

## Documentation

Elefante keeps user and developer documentation separate.

### User documentation

- [User documentation index](docs/README.md)
- [Install and repair](docs/how-to/install.md)
- [Configure a host](docs/how-to/configure-ide.md)
- [Tool reference](docs/reference/tools.md)
- [Architecture](docs/reference/architecture.md)
- [Dashboard](docs/how-to/view-dashboard.md)

### Developer documentation

- [Repository entrypoint](AGENTS.md)
- [Developer constitution](agents/orchestrator.md)
- [Living product plan](workspace/PLANNING.md)
- [Issue and gap ledger](workspace/ISSUES.md)
- [Script catalog](scripts/README.md)
- [Test catalog](tests/README.md)
- [Release history](CHANGELOG.md)

Developer plans, experiments, postmortems, and release procedures do not define
the shipped customer contract. Current source, tagged artifacts, and exact-head
release verification remain authoritative.

## License

Elefante is licensed under the [Business Source License 1.1](LICENSE), which
converts to Apache 2.0 on 2029-02-10. During the business-source period, do not
describe the project as open source.

[Contributing](CONTRIBUTING.md) · [Changelog](CHANGELOG.md) · [GitHub Releases](https://github.com/ElefanteAI/elefante/releases)
