# Developer Documentation

> **Audience:** People building, debugging, or extending Elefante itself.
> Using Elefante as a memory engine? → [docs/user/README.md](../user/README.md).
> Loading an agent protocol? → [agents/](../../agents/) (start with [agents/orchestrator.md](../../agents/orchestrator.md) for build work).

---

## Where to start

The single operational authority for build/debug work is **[agents/orchestrator.md](../../agents/orchestrator.md)**. Read it before anything else.

## Reference (current locations; migration in progress)

### Architecture & specs

| Question | Open |
| -------- | ---- |
| How is the system architected? | [docs/technical/spec-architecture.md](../technical/spec-architecture.md) |
| How does the 5-signal scoring work? | [docs/technical/spec-scoring.md](../technical/spec-scoring.md) |
| What MCP tools exist and what's their schema? | [docs/technical/spec-tools.md](../technical/spec-tools.md) |
| What's the vision and the Four Laws? | [docs/planning/spec-vision.md](../planning/spec-vision.md) |
| What is the v2.10.0 surface split spec? | [docs/planning/spec-surface-split.md](../planning/spec-surface-split.md) |

### Process & workflow

| Question | Open |
| -------- | ---- |
| How do I work through a bug? | [docs/debug/README.md](../debug/README.md) — Known Issues + verification commands |
| Where do compendiums live? | [docs/debug/](../debug/) — `ops-*-compendium.md` files |
| What are the etiquette rules (semver, CHANGELOG)? | [docs/technical/dev-etiquette.md](../technical/dev-etiquette.md) |
| When should I stop and challenge my own line of attack? | [agents/orchestrator.md](../../agents/orchestrator.md) — `RESEARCH` mode, plus [docs/planning/spec-surface-split.md §1.6.1](../planning/spec-surface-split.md) |
| When may I retune the rules themselves? | [agents/puppeteer.md](../../agents/puppeteer.md) — dangerous `PRIVILEGED` control-plane surgery; explicit authorization required |
| How do I write a new agent? | [docs/planning/spec-surface-split.md §1.5](../planning/spec-surface-split.md) (Swarm Law) + [§2.2.1](../planning/spec-surface-split.md) (Naming Convention) |

### Scripts

| Need | Open |
| ---- | ---- |
| Script catalog | [scripts/README.md](../../scripts/README.md) |
| Verification scripts | `scripts/verify/*.py` — always start here when diagnosing |
| CI / release scripts | `scripts/ci/*.py` — see [agents/release-manager.md](../../agents/release-manager.md) |
| Lifecycle (backup/restore/restart) | `scripts/lifecycle/*.py` — see [agents/operator.md](../../agents/operator.md) |

### Tests

[tests/README.md](../../tests/README.md) — test catalog. Update existing tests before creating parallel ones.

## Migration notice

`docs/developer/` is the **v2.10.0 developer-facing surface boundary**. Existing developer content currently lives under `docs/technical/`, `docs/debug/`, `docs/planning/` and is being migrated here progressively across v2.10.x patches. Forwarding from old paths is preserved — every link above will continue to work.

See [docs/planning/spec-surface-split.md §0](../planning/spec-surface-split.md) for migration status.
