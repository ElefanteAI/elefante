# Elefante

<p align="center">
  <img src="docs/assets/Elefante Logo 1024 black 2.png" alt="Elefante" width="256">
</p>

**Carry forward the context worth keeping.**

AI sessions and providers often fail to carry forward the preferences,
decisions, and discovered patterns that made earlier work productive. Elefante
gives MCP-compatible agents a persistent, local second brain: durable memories
remain inspectable across sessions, while retrieval selects context for the
task at hand.

**v2.12.3** — Current published release.

```
┌─────────────────────────────────────────────────────────────┐
│ YOUR HOST (VS Code · Cursor · Codex · compatible MCP host)  │
└────────────────────────┬────────────────────────────────────┘
                         │ MCP HTTP / stdio bridge
┌────────────────────────▼────────────────────────────────────┐
│ LAYER 1 · MCP PROTOCOL                                      │
│ 16 tools · 2 prompts · Context Injection                    │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│ LAYER 2 · INTELLIGENCE ENGINE                               │
│ Orchestrator · 5-signal scoring · Hybrid Memory             │
│ (SQLite vectors + Kuzu graph)                               │
└────────────────────────┬────────────────────────────────────┘
                         │ snapshot.json
┌────────────────────────▼────────────────────────────────────┐
│ LAYER 3 · DASHBOARD                                         │
│ Read-only briefing of what should shape the next answer     │
│ http://127.0.0.1:8000                                       │
└─────────────────────────────────────────────────────────────┘
```

Durable context stays local and inspectable. Retrieval remains selective.

---

## What It Does

Elefante is a local-first persistent memory engine for AI agents, connected via the [Model Context Protocol](https://modelcontextprotocol.io/) (MCP).

- **Stores** facts, preferences, decisions, code patterns, and tasks
- **Searches** using hybrid retrieval — semantic vectors, knowledge graph, and session context
- **Ranks** retrieval candidates with 5 signals (semantic match, concept overlap, co-activation, authority, temporal freshness) — no manual importance rating
- **Injects bounded context** on eligible tool calls; memory-heavy operations skip automatic context to avoid duplication
- **Connects knowledge** through an entity-relationship graph
- **Reduces context-free writes** with a search-before-write compliance gate and deterministic duplicate checks
- **Visualizes** memory state and explicit relationships through a snapshot-driven dashboard

The Elefante store runs locally with no Elefante product telemetry. Context you
intentionally send to a connected AI client is governed by that provider's data
policy.

---

## How It Works

The agent owns the goal, plan, tools, and stopping decision. Elefante participates
at two points in that loop: it retrieves durable context before the agent plans,
then preserves verified outcomes after the agent acts.

```text
Goal → Perceive → Plan → Act → Observe → Update → Repeat
          ↑                              ↓
     retrieve context              preserve outcomes
          └──────────── Elefante ────────────┘
```

This boundary is deliberate: Elefante is not an LLM, an agent runtime, or a
domain adviser. It is the local memory authority those systems can use.

### Layer 1 — MCP Protocol

The interface between your IDE and the memory engine. 16 tools and 2 prompts let agents store, search, connect, and manage knowledge. A **Compliance Gate** searches before memory writes and reduces redundant memories. **Context Injection** can attach relevant memories to eligible operations when a usable search signal exists. **Directives** can accompany normal product operations. **Token Intelligence** measures MCP tool responses and reports estimated output, protocol overhead, and signal ratio.

Full tool reference → [docs/reference/tools.md](docs/reference/tools.md)
IDE configuration → [docs/how-to/configure-ide.md](docs/how-to/configure-ide.md)

### Layer 2 — Intelligence Engine

Two local storage layers work together:

- **SQLite** — the dependency-free default vector store; it preserves complete memory JSON and float32 embeddings with deterministic exact-cosine retrieval.
- **Kuzu** — a knowledge graph that tracks entities, relationships, and structural context.
- **Behavioral Relevance** — a 5-signal scoring system that ranks memory candidates. Retrieval frequency is not proof that a memory improved the task.

Scoring details → [docs/reference/scoring.md](docs/reference/scoring.md)
Architecture → [docs/reference/architecture.md](docs/reference/architecture.md)

### Layer 3 — Dashboard

A read-only Memory Intelligence briefing, served from a redacted snapshot so the agent stays fast and the browser never owns your stores:

- A decision briefing that can show old assumption → evidence → decision → enforced guard
- Searchable, sortable memory inspection with source and lifecycle context
- Topic, distribution, and knowledge-connection views
- A carbon, tusk, copper, brass, clay, and sage interface built around information state—not generic AI gradients

Dashboard details → [docs/how-to/view-dashboard.md](docs/how-to/view-dashboard.md)
Docker deployment → [docs/how-to/docker.md](docs/how-to/docker.md)

---

## Designed For

Released adapter coverage currently includes VS Code, Cursor, Kiro, Gemini CLI,
Claude Code, Codex, and OpenClaw. These integrations are compatible, not yet
host-certified end to end. Other MCP-compatible clients can use the community
bridge contract without becoming a supported integration claim.

---

## Release Installation

**Requirements:** Python 3.11, 3.12, or 3.13. Release CI currently runs on
Python 3.11; the installer accepts all three versions. Git is only required for
the source-checkout fallback path.

Our installer detects your OS, creates a stable per-user customer runtime,
installs the locked runtime dependencies, initializes local graph and vector
databases, and connects every compatible host detected on the machine.

**Release bundle (preferred):** Download `elefante-installer-<OS>.zip` from GitHub Releases and extract it, then:

- **macOS:** double-click `Install Elefante.command`. If macOS asks for confirmation, Control-click the file, choose **Open**, then choose **Open** again. Administrator access and Terminal commands are not required.
- **Windows:** double-click `Install Elefante.bat`.
- **Linux:** run `chmod +x install.sh && ./install.sh`.

The bootstrap places Elefante in a stable install root before it starts setup:

- macOS / Linux: `~/.elefante/app/current`
- Windows: `%LOCALAPPDATA%\Elefante\app\current`

Signed and notarized native macOS packaging is Upcoming. The verified v2.12.3 customer path is the macOS ZIP launcher above.

If `.venv` already exists, the installer offers four paths:

- Delete existing `.venv` and install fresh (default)
- Backup existing `.venv` and install fresh
- Reuse existing `.venv`
- Abort installation

**If installation fails:** read the persisted installer files in this order:

1. `.elefante-install-summary.txt`
2. `.elefante-install-status.txt`
3. `.elefante-install.log`

For release bundles, those files live in the stable install root. For
source-checkout installs, they live in the repo root. The installer prints
their exact paths at startup and on failure.

```bash
# Source checkout fallback
# macOS / Linux
git clone https://github.com/ElefanteAI/elefante.git
cd elefante
git checkout v2.12.3
chmod +x install.sh && ./install.sh

# Windows
git clone https://github.com/ElefanteAI/elefante.git
cd elefante
git checkout v2.12.3
install.bat
```

The installer keeps the Elefante store under the user's local account, connects
detected compatible hosts, and writes one harmless seed memory for connection
verification.

**The 60-Second Proof of Work:**
1. Restart your IDE.
2. Open your AI Chat (Copilot, Cursor, etc).
3. Copy/paste exactly this question: 
   `What is my Elefante test passcode?`
4. If the host does not search automatically, ask it explicitly to search
   Elefante for the test passcode. The expected result is `Indigo-Echo`.

*Looking for manual setup or deep technical details? See the [Full Installation Guide](docs/how-to/install.md).*

---

## MCP Tools

16 tools + 2 prompts. Tool names follow `elefante-PascalCase`; prompt names are `elefante-context` and `elefante-grounding`.

| Category   | Tools                                                                                                                                   |
| ---------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Memory     | `elefante-Memory` (actions: `add` · `search` · `update` · `delete` · `consolidate`)                                                |
| Graph      | `elefante-GraphConnect`, `elefante-GraphQuery`                                                                                      |
| Context    | `elefante-ContextGet`, `elefante-SessionsList`                                                                                      |
| Tasks      | `elefante-TaskCreate`, `elefante-TaskUpdate`, `elefante-TaskGraph`                                                                |
| ETL        | `elefante-ETLProcess`, `elefante-ETLClassify`                                                                                       |
| Directives | `elefante-DirectiveAdd`, `elefante-DirectiveList`, `elefante-DirectiveRemove`                                                     |
| System     | `elefante-System`, `elefante-SystemStatusGet`, `elefante-DashboardOpen`                                                           |

Full reference with parameter schemas → [docs/reference/tools.md](docs/reference/tools.md)

## Specification And Directive Retrieval

Elefante keeps durable architecture rules out of the live prompt by separating lightweight agent instructions from retrieved knowledge:

1. **Keep the instruction file small.** Your `.cursorrules`,
   `copilot-instructions.md`, or equivalent should tell the agent to search
   Elefante when prior decisions, preferences, or project context may affect
   the task.
2. **Store durable rules in Elefante.** Architecture contracts, schemas, and team process belong in `specification` or `directive` memories rather than inside a giant prompt file.
3. **Retrieve only what is relevant.** When the agent searches, Elefante surfaces the specific rule needed for the current task instead of injecting an entire handbook into every prompt.

---

## Tech Stack

| Purpose      | Technology                       |
| ------------ | -------------------------------- |
| Vector store | SQLite (exact cosine)            |
| Graph store  | Kuzu 0.11.3                      |
| Embeddings   | sentence-transformers (gte-base) |
| Protocol     | MCP 1.28.1                       |
| Dashboard    | React + TypeScript + Vite        |
| Runtime      | Python 3.11–3.13                 |

---

## Repo Structure

```
src/              Core engine, MCP server, dashboard
docs/             Stable reference, how-to, and explanation
workspace/        Living plan, issues, postmortems, proposals
agents/           Developer constitution and specialist protocols
examples/         Agent tutorial and integration patterns
tests/            Unit, integration, and verification tests
scripts/          Setup, deployment, and maintenance tools
```

---

## Documentation

Three audiences, three surfaces:

| Audience | Start here |
| -------- | ---------- |
| **Using Elefante** as a memory engine | [docs/README.md](docs/README.md) |
| **Building or debugging Elefante** itself | [AGENTS.md](AGENTS.md) → [agents/orchestrator.md](agents/orchestrator.md) |
| **Loading an agent protocol** at the moment of failure | [agents/](agents/) |

### Agent dispatch (load when this happens)

| Symptom | Load |
| ------- | ---- |
| Building a feature, debugging Elefante itself | [agents/orchestrator.md](agents/orchestrator.md) |
| Any `elefante-Memory(action="add"\|"update"\|"delete")` | [agents/memory-janitor.md](agents/memory-janitor.md) |
| "What do I have stored?", export, audit | [agents/memory-inspector.md](agents/memory-inspector.md) |
| Install failed, broken venv, repair | [agents/installer.md](agents/installer.md) |
| MCP tools missing in IDE, server stuck | [agents/restarter.md](agents/restarter.md) |
| Backup, restore, factory reset, restart | [agents/operator.md](agents/operator.md) |
| Version bump, CHANGELOG, tag, release | [agents/release-manager.md](agents/release-manager.md) |
| Line of attack is suspect (RESEARCH mode) | [agents/researcher.md](agents/researcher.md) |
| Need to retune the rules themselves | [agents/puppeteer.md](agents/puppeteer.md) (`PRIVILEGED` only) |

### Product reference

- [Tool reference](docs/reference/tools.md) — parameter schemas for all 16 tools and 2 prompts
- [Behavioral Relevance](docs/reference/scoring.md) — how automatic scoring works
- [Installation](docs/how-to/install.md) — step-by-step setup
- [Architecture](docs/reference/architecture.md) — system design
- [Dashboard](docs/how-to/view-dashboard.md) — visualization and health monitoring
- [Docker](docs/how-to/docker.md) — containerized deployment
- [Debugging](workspace/ISSUES.md) — known issues tracker, compendium routing, and verification commands

## Release Notes

Every tagged Elefante release is documented in three places:

- [GitHub Releases](https://github.com/ElefanteAI/elefante/releases) — packaged binaries and release-specific notes
- [CHANGELOG.md](CHANGELOG.md) — the full historical ledger
- [README.md](README.md) — the current product surface, install path, and docs map

Release bodies are rendered from the matching `CHANGELOG.md` entry in CI, so new tags do not ship with empty GitHub release pages. `CHANGELOG.md` is the authoritative historical record for older releases as well, including legacy GitHub release pages that predate rendered release bodies.

Do not cut or push a `v*` tag until its matching `CHANGELOG.md` entry exists.

---

## Contributing & License

See [CONTRIBUTING.md](CONTRIBUTING.md).

**License:** [Business Source License 1.1](LICENSE) — free for non-competitive use. Converts to Apache 2.0 on 2029-02-10.

[Changelog](CHANGELOG.md) · [Full Documentation](docs/README.md)
