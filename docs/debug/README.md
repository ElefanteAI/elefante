# Debug Documentation Index

**Compendiums and pitfall reference for Elefante v2.2.1**

> **Last Updated:** 2026-02-26

---

## Structure

```
docs/debug/
├── README.md                   <- You are here (index)
└── *-compendium.md             <- Detailed post-mortems by domain
```

Operational quick-reference (pitfalls, LAWs) lives in **[`docs/pitfall-index.md`](../pitfall-index.md)**.  
Archived neural registers are in `docs/archive/deprecated-registers/`.

---

## Domain Compendiums (Detailed Post-Mortems)

Each compendium follows the **Unified Post-Mortem Structure**:
Problem → Symptom → Root Cause → Solution → Lesson

| Domain       | Compendium                                               |
| ------------ | -------------------------------------------------------- |
| Dashboard    | [dashboard-compendium.md](dashboard-compendium.md)       |
| Database     | [database-compendium.md](database-compendium.md)         |
| Installation | [installation-compendium.md](installation-compendium.md) |
| Memory       | [memory-compendium.md](memory-compendium.md)             |
| AI Behavior  | [ai-behavior-compendium.md](ai-behavior-compendium.md)   |

---

## How to Use

| Task            | Action                                                                        |
| --------------- | ----------------------------------------------------------------------------- |
| **Quick debug** | Search [`docs/pitfall-index.md`](../pitfall-index.md) for `pitfall: [domain]` |
| **Deep dive**   | Open the relevant `*-compendium.md` for full post-mortems                     |
| **New issue**   | Add to relevant compendium using the template at the bottom of that file      |

---

## File Inventory

```
docs/debug/
├── README.md
├── ai-behavior-compendium.md
├── dashboard-compendium.md
├── database-compendium.md
├── installation-compendium.md
└── memory-compendium.md
```

**Total: 6 files (flat structure)**

---

_Last verified: 2026-02-26 | Elefante v2.2.1_
