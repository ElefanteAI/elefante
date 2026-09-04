# Elefante

<p align="center">
  <img src="docs/assets/Elefante Logo 1024 black 2.png" alt="Elefante" width="256">
</p>

**A private, persistent second brain for the AI tools you already use.**

Elefante stores durable preferences, decisions, facts, constraints, and lessons
on your machine, then supplies a small governed subset when an agent needs prior
context. It works beside the AI tools you already use and gives their separate
sessions one private, inspectable memory.

**v2.15.2** — Current published release.

Published v2.15.2: 18 tools · 2 prompts · Python 3.11–3.13 · MCP 1.28.1

## Install

1. Download the matching installer ZIP from the
   [latest release](https://github.com/ElefanteAI/elefante/releases/latest),
   verify its SHA-256, and extract it.
2. Open `Install Elefante.command` on macOS. If macOS asks, Control-click it,
   choose **Open**, then **Open** again. Administrator access and Terminal
   commands are not required. On Windows, open `Install Elefante.bat`; on Linux,
   run `chmod +x install.sh && ./install.sh`.
3. Choose the project folder whose memories must stay isolated, finish the
   installer checks, and restart your connected agent.

For source installation, checksums, repair, migration, upgrade, and uninstall,
use the [installation guide](docs/how-to/install.md).

The dashboard is included. Git, Node.js, a source checkout, and a browser
extension are not required for a customer installation.

Signed native packages are published only when credential-gated notarization or Authenticode verification
succeeds; an unsigned substitute is never presented
as a release asset.

**If installation fails:** read the paths printed by the installer in this order:

1. `.elefante-install-summary.txt`
2. `.elefante-install-status.txt`
3. `.elefante-install.log`

Do not delete the data root or edit host configuration by guesswork.

## Verify the installation

The v2.15.2 installer has a disposable real-MCP acceptance check and a verified
baseline backup. Installation does not succeed unless that private check passes.
Readiness proves connection health; useful selection still requires one real
question.

1. Follow the [five-minute real-memory demo](examples/README.md). It uses one
   decision that matters to your work—never a preloaded fake conversation.
2. Open the [customer guide](docs/README.md) for everyday use, every dashboard
   feature, recovery, and troubleshooting.

## The product loop

| Action | What you do | What Elefante does |
|---|---|---|
| **Remember** | Ask your connected agent to keep one durable decision, preference, constraint, fact, or lesson | Searches before writing and returns an explicit result |
| **Recall** | Ask a real task question | Supplies a small eligible context bundle, or explicitly abstains |
| **Correct** | Review outdated or conflicting knowledge | Plans and verifies Edit, Replace, Archive, Restore, Resolve, or permanent deletion |
| **Understand** | Open the local dashboard | Shows sources, health, topics, explicit relationships, and usage evidence |
| **Recover** | Check health, back up, restore, or create a support report | Uses verified, rollback-protected local operations |

The AI tool continues to do the work. Elefante retrieves durable context before
or during a task and preserves verified outcomes only when the user or workflow
explicitly asks it to write.

```text
Goal → Perceive → Plan → Act → Observe → Update → Repeat
          ↑                              ↓
     retrieve context              preserve verified outcomes
          └──────────── Elefante ────────────┘
```

```text
Connected agent ── Remember / Recall ──► local Elefante daemon
                                             │
                              SQLite vectors + Kuzu relationships
                                             │
                              local maintenance dashboard
```

Read-only Recall never edits a memory and a selected record does not prove that
an answer is good. Conflicting or ineligible evidence can be withheld. The user
remains responsible for deciding what is true and what should be kept.

## Documentation map

| If you are… | Start here | Continue with |
|---|---|---|
| Trying Elefante for the first time | [Five-minute demo](examples/README.md) | [Complete customer guide](docs/README.md) |
| Installing or repairing it | [Installation guide](docs/how-to/install.md) | [Host configuration](docs/how-to/configure-ide.md) |
| Learning the dashboard | [Dashboard guide](docs/README.md#dashboard) | [Detailed offline dashboard reference](docs/how-to/view-dashboard.html) |
| Operating advanced features | [Advanced guide index](docs/README.md#advanced-reference) | [Tools and prompts](docs/reference/tools.md) · [Architecture](docs/reference/architecture.md) |
| Integrating an agent | [Advanced agent tutorial](examples/AGENT_TUTORIAL.md) | [System-prompt fallback](examples/system-prompt-template.md) |
| Developing Elefante | [Developer entrypoint](AGENTS.md) | [Plan](workspace/PLANNING.md) · [Issues](workspace/ISSUES.md) · [Tests](tests/README.md) |

Customer guidance describes released behavior. Developer plans, experiments,
postmortems, and Task Intelligence evaluation are separate and do not expand the
published product contract.

## Published boundary

The v2.15.2 customer profile exposes 18 MCP tools and 2 prompts. The local
daemon owns embedded SQLite vectors and Kuzu relationships; connected hosts use
local HTTP or a storage-free stdio bridge. Memory, graph, media, dashboard, and
consented Session Intelligence data stay local by default. Elefante has no
product telemetry.

Advanced released capabilities include local media attachments, the foreground
Session Distiller, signed scope-bound Team Sync bundles, private host-event
retrieval, and consented metadata-only Session Intelligence. Their exact use,
limits, and safety boundaries are in the [customer guide](docs/README.md#all-released-features)
and [technical reference](docs/README.md#advanced-reference).

Task Intelligence evaluation remains developer-only and default-off. It has not
established representative multi-task outcome lift and is not a public product
performance claim.

## License

Elefante is licensed under the [Business Source License 1.1](LICENSE), which
converts to Apache 2.0 on 2029-02-10. During the business-source period, do not
describe the project as open source.

[Contributing](CONTRIBUTING.md) · [Changelog](CHANGELOG.md) · [GitHub Releases](https://github.com/ElefanteAI/elefante/releases)
