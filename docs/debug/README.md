# Debug Documentation Index

**Neural Registers & Debug Compendiums for Elefante v1.0.0**

> **Last Optimized:** 2025-12-06 | Unified post-mortem structure across all domains

---

## Architecture

```
docs/debug/
├── README.md                          ← You are here
├── 5 Neural Registers                 ← LAWS (start here when debugging)
├── 5 Domain Compendiums               ← SOURCE (scalable issue tracking)
└── Unified Post-Mortem Format         ← STRUCTURE (consistent across all)
```

---

## Neural Registers (System Immunity)

**What are Neural Registers?**  
Immutable "Laws" extracted from debugging sessions - the system's immune memory that prevents recurring failures.

| Register | Purpose | Key Laws |
|----------|---------|----------|
| [`installation-neural-register.md`](installation-neural-register.md) | Installation failure prevention | Kuzu Path Conflict, Pre-Flight Checks |
| [`database-neural-register.md`](database-neural-register.md) | Database failure prevention | Reserved Words, Single-Writer Lock |
| [`dashboard-neural-register.md`](dashboard-neural-register.md) | Dashboard failure prevention | Data Path Separation, Snapshot Pattern |
| [`mcp-code-neural-register.md`](mcp-code-neural-register.md) | MCP protocol enforcement | Mode Restrictions, Layer 5 Verification |
| [`memory-neural-register.md`](memory-neural-register.md) | Memory system reliability | Export Bypass, ChromaDB vs Kuzu |

**Format**: Laws → Failure Patterns → Safeguards → Metrics → Source Documents

---

## Domain Compendiums (One File Per Domain)

Each compendium follows the **Unified Post-Mortem Structure**:
- Critical Laws table
- Issues #1, #2, #3... (scalable)
- Each issue: Problem → Symptom → Root Cause → Solution → Lesson
- Methodology Failures section
- Prevention Protocol
- Appendix with issue template

| Domain | Compendium | Issues | Status |
|--------|-----------|--------|--------|
| Dashboard | [`dashboard/dashboard-compendium.md`](dashboard/dashboard-compendium.md) | 5 issues | ✅ Active |
| Database | [`database/database-compendium.md`](database/database-compendium.md) | 6 issues | ✅ Active |
| Installation | [`installation/installation-compendium.md`](installation/installation-compendium.md) | 4 issues | ✅ Active |
| Memory | [`memory/memory-compendium.md`](memory/memory-compendium.md) | 5 issues | ✅ Active |
| AI Behavior | [`general/ai-behavior-compendium.md`](general/ai-behavior-compendium.md) | 5 issues | ✅ Active |

---

## Unified Post-Mortem Structure

All compendiums follow this scalable format:

```markdown
# [Domain] Debug Compendium

> **Domain:** [Name]
> **Last Updated:** YYYY-MM-DD
> **Total Issues Documented:** N
> **Maintainer:** Add new issues following Issue #N template at bottom

---

## 🚨 CRITICAL LAWS (Extracted from Pain)

| # | Law | Violation Cost |
|---|-----|----------------|
| 1 | [Law statement] | [Cost in time/effort] |

---

## Issue #1: [Title]

**Date:** YYYY-MM-DD
**Duration:** X hours/minutes
**Severity:** LOW | MEDIUM | HIGH | CRITICAL
**Status:** 🔴 OPEN | 🟡 IN PROGRESS | ✅ FIXED | ⚠️ DOCUMENTED

### Problem
[One sentence]

### Symptom
[What user sees / error message]

### Root Cause
[Technical WHY]

### Solution
[Code changes or steps]

### Why This Took So Long
[Honest reflection]

### Lesson
> [One-line takeaway in blockquote]

---

## Appendix: Issue Template
[Copy-paste template for new issues]
```

---

## 🔑 How to Use This System

### When Debugging a New Issue

1. **Check Neural Register first** → Find relevant laws
2. **Search compendium** → Has this been seen before?
3. **If new issue** → Add to compendium using template
4. **If pattern emerges** → Extract new law to Neural Register

### When Adding New Issues

1. Open the relevant compendium
2. Copy the issue template from Appendix
3. Fill in all sections honestly
4. Add to Critical Laws table if significant
5. Update Neural Register if new law discovered

### When Reviewing Debug History

- **Start with Neural Registers** for quick rules
- **Dive into Compendiums** for full context
- **Check Methodology Failures** for meta-lessons
- **Use Prevention Protocols** proactively

---

## 📊 Consolidation Summary

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Total debug files | 29 | 10 | 66% reduction |
| Files per domain | 3-13 | 2 (register + compendium) | Standardized |
| Structure variations | 5+ | 1 unified | Consistent |
| Scalability | Poor (new files) | Good (append to compendium) | Maintainable |

---

## 🚫 Anti-Patterns to Avoid

| ❌ Don't | ✅ Do |
|----------|-------|
| Create new file per issue | Append to domain compendium |
| Write narrative prose | Use structured Issue #N format |
| Skip "Why This Took So Long" | Include honest reflection |
| Forget the Lesson blockquote | Extract actionable takeaway |
| Leave compendium outdated | Update after each debug session |

---

## 📁 Directory Structure

```
docs/debug/
├── README.md                              ← Index (you are here)
├── INSTALLATION_NEURAL_REGISTER.md        ← Laws: Installation
├── DATABASE_NEURAL_REGISTER.md            ← Laws: Database
├── DASHBOARD_NEURAL_REGISTER.md           ← Laws: Dashboard
├── MCP_CODE_NEURAL_REGISTER.md            ← Laws: MCP/Code
├── MEMORY_NEURAL_REGISTER.md              ← Laws: Memory
├── dashboard/
│   └── dashboard-compendium.md            ← Source: Dashboard issues
├── database/
│   └── database-compendium.md             ← Source: Database issues
├── installation/
│   └── installation-compendium.md         ← Source: Installation issues
├── memory/
│   └── memory-compendium.md               ← Source: Memory issues
└── general/
    └── ai-behavior-compendium.md          ← Source: AI behavior issues
```

---

*Last verified: 2025-12-06 | Elefante v1.0.0 | 10 active debug documents*
