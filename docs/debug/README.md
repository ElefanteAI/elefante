# Debug Documentation Index

**Neural Registers & Debug Compendiums for Elefante v1.6.2**

> **Last Updated:** 2025-12-28

---

## Structure

```
docs/debug/
├── README.md                        <- You are here (index)
├── *-neural-register.md             <- LAWS (start here when debugging)
└── *-compendium.md                  <- SOURCE (detailed issue tracking)
```

**All files at root level. No subfolders.**

---

## Neural Registers (System Immunity)

Immutable "Laws" extracted from debugging sessions - prevents recurring failures.

| Register | Purpose |
|----------|---------|
| [installation-neural-register.md](installation-neural-register.md) | Installation failure prevention |
| [database-neural-register.md](database-neural-register.md) | Database failure prevention |
| [dashboard-neural-register.md](dashboard-neural-register.md) | Dashboard failure prevention |
| [mcp-code-neural-register.md](mcp-code-neural-register.md) | MCP protocol enforcement |
| [memory-neural-register.md](memory-neural-register.md) | Memory system reliability |

---

## Domain Compendiums (Detailed Issues)

Each compendium follows the **Unified Post-Mortem Structure**:
- Problem -> Symptom -> Root Cause -> Solution -> Lesson

| Domain | Compendium |
|--------|-----------|
| Dashboard | [dashboard-compendium.md](dashboard-compendium.md) |
| Database | [database-compendium.md](database-compendium.md) |
| Installation | [installation-compendium.md](installation-compendium.md) |
| Memory | [memory-compendium.md](memory-compendium.md) |
| AI Behavior | [ai-behavior-compendium.md](ai-behavior-compendium.md) |

---

## Additional Reference

| File | Purpose |
|------|---------|
| [kuzu-reserved-words-issue.md](kuzu-reserved-words-issue.md) | Kuzu property naming conflicts |

---

## How to Use

| Task | Action |
|------|--------|
| **Debugging** | Check Neural Register first -> Search compendium |
| **New issue** | Add to relevant compendium using template |
| **New pattern** | Extract law to Neural Register |

---

## File Inventory

```
docs/debug/
├── README.md
├── ai-behavior-compendium.md
├── dashboard-compendium.md
├── dashboard-neural-register.md
├── database-compendium.md
├── database-neural-register.md
├── installation-compendium.md
├── installation-neural-register.md
├── kuzu-reserved-words-issue.md
├── mcp-code-neural-register.md
├── memory-compendium.md
└── memory-neural-register.md
```

**Total: 12 files (flat structure)**

---

*Last verified: 2025-12-29 | Elefante v1.6.2*
