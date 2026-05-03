# User Documentation

> **Audience:** People using Elefante as a persistent memory engine for their AI agents.
> Building or debugging Elefante itself? → [docs/developer/README.md](../developer/README.md).
> Loading an agent protocol? → [agents/](../../agents/).

---

## Where to start

| Question | Open |
| -------- | ---- |
| How do I install Elefante? | [docs/technical/ops-installation.md](../technical/ops-installation.md) *(migrating to docs/user/install.md in v2.10.x)* |
| How do I configure my IDE (VS Code, Cursor, Windsurf)? | [docs/technical/ops-ide-configuration.md](../technical/ops-ide-configuration.md) |
| What does the dashboard show? | [docs/technical/ops-dashboard.md](../technical/ops-dashboard.md) |
| How do I run Elefante in Docker? | [docs/technical/ops-docker.md](../technical/ops-docker.md) |
| What MCP tools are available to my agent? | [docs/technical/spec-tools.md](../technical/spec-tools.md) — tool reference |
| What does Elefante actually do? | [README.md](../../README.md) (repo root) |

## When something breaks

Load the matching specialist agent — they are designed to be loaded by your AI assistant at the moment of failure, not read by humans:

| Symptom | Load |
| ------- | ---- |
| Install failed | [agents/installer.md](../../agents/installer.md) |
| MCP tools not showing in IDE | [agents/restarter.md](../../agents/restarter.md) |
| "What do I have stored?" | [agents/memory-inspector.md](../../agents/memory-inspector.md) |
| Backup, restore, factory reset | [agents/operator.md](../../agents/operator.md) |

## Migration notice

`docs/user/` is the **v2.10.0 user-facing surface boundary**. Existing user-relevant content currently lives under `docs/technical/ops-*.md` and is being migrated here progressively across v2.10.x patches. Forwarding from old paths is preserved — every link above will continue to work.

See [docs/planning/spec-surface-split.md §0](../planning/spec-surface-split.md) for migration status.
