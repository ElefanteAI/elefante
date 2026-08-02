# Elefante

<p align="center">
  <img src="docs/assets/Elefante Logo 1024 black 2.png" alt="Elefante" width="256">
</p>

**Elefante never forgets.**

AI agents start every conversation from zero. Your preferences, decisions, and discovered patterns don't carry over. Elefante gives any MCP-compatible agent a persistent, local second brain — memories are stored, scored automatically, and surfaced at the right moment without being asked.

**v2.12.0** — Release candidate; current published release: v2.11.1

```
┌─────────────────────────────────────────────────────────────┐
│ YOUR HOST (VS Code · Cursor · Codex · compatible MCP host)  │
└────────────────────────┬────────────────────────────────────┘
                         │ MCP stdio
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

Every memory stored. Every context surfaced. Nothing forgotten.

---

## What It Does

Elefante is a local-first persistent memory engine for AI agents, connected via the [Model Context Protocol](https://modelcontextprotocol.io/) (MCP).

- **Stores** facts, preferences, decisions, code patterns, and tasks
- **Searches** using hybrid retrieval — semantic vectors, knowledge graph, and session context
- **Scores** every memory automatically using 5 retrieval signals (semantic match, concept overlap, co-activation, authority, temporal freshness) — no manual ratings
- **Injects context** silently into every tool call — the agent gets relevant history without asking
- **Connects knowledge** through an entity-relationship graph
- **Enforces quality** via a compliance gate: search before write, no duplicates
- **Visualizes** brain health through a snapshot-driven dashboard

The Elefante store runs locally with no Elefante product telemetry. Context you
intentionally send to a connected AI client is governed by that provider's data
policy.

---

## How It Works

### Layer 1 — MCP Protocol

The interface between your IDE and the memory engine. 16 tools and 2 prompts let agents store, search, connect, and manage knowledge. A **Compliance Gate** prevents duplicates before they exist. **Context Injection** attaches relevant memories to every tool response. **Directives** enforce persistent behavioral rules that survive across sessions. **Token Intelligence** measures every response and tells the agent what each tool call costs — output tokens, protocol overhead, and signal ratio — so memory never becomes invisible bloat.

Full tool reference → [docs/reference/tools.md](docs/reference/tools.md)
IDE configuration → [docs/how-to/configure-ide.md](docs/how-to/configure-ide.md)

### Layer 2 — Intelligence Engine

Two local storage layers work together:

- **SQLite** — the dependency-free default vector store; it preserves complete memory JSON and float32 embeddings with deterministic exact-cosine retrieval.
- **Kuzu** — a knowledge graph that tracks entities, relationships, and structural context.
- **Behavioral Relevance** — a 5-signal scoring system that automatically surfaces the most useful memories. No manual importance ratings.

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

Verified installer adapters currently cover VS Code, Cursor, Kiro, Gemini CLI,
Claude Code, Codex, and OpenClaw. Other MCP-compatible clients can use the
standard bridge contract, but are not marketed as verified integrations.

---

## One-Click Installation (Zero Config)

**Requirements:** Python 3.11+ (tested up to 3.13). Git is only required for the source-checkout fallback path.

Our installer detects your OS, manages the repository virtual environment,
installs the locked dependencies, initializes local graph and vector databases,
and lets you select from the compatible hosts detected on the machine.

**Release bundle (preferred):** Download `elefante-installer-<OS>.zip` from GitHub Releases, extract it, then run the top-level `install.sh` or `install.bat`. The bootstrap places Elefante in a stable install root first, then delegates the real setup work to `scripts/setup/install.py`.

- macOS / Linux stable root: `~/.elefante/app/current`
- Windows stable root: `%LOCALAPPDATA%\Elefante\app\current`

On macOS builders with Swift available, the DMG ships a native AppKit installer surface. The legacy Python/Tk installer is fallback compatibility only.

If `.venv` already exists, the installer offers four paths:

- Delete existing `.venv` and install fresh (default)
- Backup existing `.venv` and install fresh
- Reuse existing `.venv`
- Abort installation

**If installation fails:** read the persisted installer files in this order:

1. `.elefante-install-summary.txt`
2. `.elefante-install-status.txt`
3. `.elefante-install.log`

For release bundles and the macOS DMG, those files live in the stable install root. For source-checkout installs, they live in the repo root. The installer prints their exact paths at startup and on failure.

```bash
# Source checkout fallback
# macOS / Linux
git clone https://github.com/elefante/elefante.git
cd elefante
chmod +x install.sh && ./install.sh

# Windows
git clone https://github.com/elefante/elefante.git
cd elefante
install.bat
```

You possess full local control. The installer automatically bridges into your IDE and injects a single "Seed Memory" to prove the connection.

**The 60-Second Proof of Work:**
1. Restart your IDE.
2. Open your AI Chat (Copilot, Cursor, etc).
3. Copy/paste exactly this question: 
   `What is my Elefante test passcode?`
4. Watch the AI hit your local memory, cure its amnesia, and return the secret code.

*Looking for manual setup or deep technical details? See the [Full Installation Guide](docs/how-to/install.md).*

---

## MCP Tools

16 tools + 2 prompts. All names follow `elefante-PascalCase` convention.

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

1. **Keep the instruction file small.** Your `.cursorrules`, `copilot-instructions.md`, or equivalent should tell the agent to search Elefante before writing code or declaring work complete.
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
| Runtime      | Python 3.11                      |

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
