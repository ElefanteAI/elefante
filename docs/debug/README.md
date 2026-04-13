# Debug Documentation Index

**Compendiums and pitfall reference for Elefante v2.2.3**

> **Last Updated:** 2026-04-12

---

## Structure

```
docs/debug/
├── README.md                   <- You are here (index)
├── dev-developer-agent.md          <- AI agent protocol for developing Elefante
└── *-compendium.md             <- Detailed post-mortems by domain
```

Debug and diagnostic scripts live in **[`scripts/debug/`](../../scripts/debug/)**.

---

## Domain Compendiums (Detailed Post-Mortems)

Each compendium follows the **Unified Post-Mortem Structure**:
Problem → Symptom → Root Cause → Solution → Lesson

| Domain       | Compendium                                               |
| ------------ | -------------------------------------------------------- |
| Dashboard    | [ops-dashboard-compendium.md](ops-dashboard-compendium.md)       |
| Database     | [ops-database-compendium.md](ops-database-compendium.md)         |
| Installation | [ops-installation-compendium.md](ops-installation-compendium.md) |
| Memory       | [ops-memory-compendium.md](ops-memory-compendium.md)             |
| AI Behavior  | [ops-ai-behavior-compendium.md](ops-ai-behavior-compendium.md)   |

### Developer Agent Protocol

[`dev-developer-agent.md`](dev-developer-agent.md) — Routing protocol for AI agents developing Elefante itself. Points to SDD gates, developer etiquette, and pitfall index. Not injected into normal user sessions.

---

## How to Use

| Task            | Action                                                                        |
| --------------- | ----------------------------------------------------------------------------- |
| **Deep dive**   | Open the relevant `*-compendium.md` for full post-mortems                     |
| **New issue**   | Add to relevant compendium using the template at the bottom of that file      |

---

## File Inventory

```
docs/debug/
├── README.md
├── dev-developer-agent.md
├── ops-ai-behavior-compendium.md
├── ops-dashboard-compendium.md
├── ops-database-compendium.md
├── ops-installation-compendium.md
└── ops-memory-compendium.md
```

**Total: 7 files (flat structure)**

---

_Last verified: 2026-02-26 | Elefante v2.2.3_
