# Elefante User Documentation

> **v2.12.1** · Published user documentation. The GitHub release and installers
> are public.

Use this index to install, configure, operate, and understand the released
Elefante product. Development plans, bugs, postmortems, release procedures, and
draft contracts are intentionally outside this user-documentation surface.

| Folder | Type | Question it answers | When to read |
|--------|------|---------------------|--------------|
| [`reference/`](reference/) | **SPEC** — what the system IS | "What is the contract?" | Looking up a frozen contract |
| [`how-to/`](how-to/) | **OPS** — what to DO | "How do I accomplish X?" | Performing a task |
| [`explanation/`](explanation/) | **CONCEPT** — WHY | "Why does this exist?" | Understanding design |

---

## Reference (`reference/`) — what the system IS

| Doc | Contract |
|-----|----------|
| [`architecture.md`](reference/architecture.md) | System design, triple-layer brain, retrieval workflow |
| [`tools.md`](reference/tools.md) | MCP tool reference (16 tools, 2 prompts) — full schemas |
| [`scoring.md`](reference/scoring.md) | 5-signal cognitive scoring (vector / concept / co-activation / authority / temporal) |
| [`ingestion.md`](reference/ingestion.md) | 5-step pipeline (Extract → Classify → Integrity → Write → Reinforce) |
| [`memory-schema.md`](reference/memory-schema.md) | V4 cognitive fields + V5 knowledge topology |
| [`dashboard-snapshot.md`](reference/dashboard-snapshot.md) | Dashboard JSON schema |
| [`self-protocol.md`](reference/self-protocol.md) | Whole-system MCP self-protocol verification contract |
| [`token-intelligence.md`](reference/token-intelligence.md) | Token-budget layer (TOKEN_STATS, type budgets, density warnings) — shipped v2.5.0 |

Source-of-truth for every spec is `src/`; specs lag. When formula and spec disagree, source wins.

## How-to (`how-to/`) — what to DO

| Doc | Procedure |
|-----|-----------|
| [`install.md`](how-to/install.md) | Full install + Python version details |
| [`configure-ide.md`](how-to/configure-ide.md) | IDE and CLI-agent MCP setup (VS Code, Cursor, Bob, Antigravity, Kiro, Gemini CLI, Claude Code, Codex, OpenClaw) |
| [`run-mcp-server.md`](how-to/run-mcp-server.md) | Manual server startup + handshake verification |
| [`view-dashboard.md`](how-to/view-dashboard.md) | Dashboard launch + verification |
| [`restart.md`](how-to/restart.md) | Graceful restart, lock cleanup, force-kill |
| [`rollback.md`](how-to/rollback.md) | Backup + restore |
| [`docker.md`](how-to/docker.md) | Docker deployment |
| [`kuzu-troubleshooting.md`](how-to/kuzu-troubleshooting.md) | Kuzu reserved words, locking, troubleshooting |
| [`agent-handoff.md`](how-to/agent-handoff.md) | Autonomous agent integration |

## Explanation (`explanation/`) — WHY

| Doc | Concept |
|-----|---------|
| [`vision.md`](explanation/vision.md) | Thesis, Four Laws, released architecture, and product boundary |

---

## Boundaries (Diátaxis-pure)

- **`reference/` is for what the system IS.** No how-to steps, no rationale paragraphs.
- **`how-to/` is for procedures.** Goal-oriented. Numbered steps. No conceptual deep-dives.
- **`explanation/` is for WHY.** Design rationale, philosophy, thesis. No commands, no schemas.
- **Developer state is not user documentation.** Drafts, bugs, postmortems, and
  release procedures are maintained separately and are not linked from this
  index.

A file in the wrong folder is a structural bug. The forbidden-pattern guard (`tests/test_developer_routing.py`) catches some drift; type purity is enforced by code review.
