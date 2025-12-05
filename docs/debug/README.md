# Debug Documentation Index

This directory contains all debugging, troubleshooting, and protocol documentation for the Elefante project.

## 📁 Directory Structure

```
debug/
├── README.md (this file)
├── dashboard/          # Dashboard-specific issues
├── database/           # Database-specific issues
├── general/            # General debugging & protocols
├── installation/       # Installation issues
└── memory/            # Memory system issues
```

## 🎯 Quick Navigation

### Protocol Enforcement (START HERE)
- **[PROTOCOL-ENFORCEMENT-FINAL.md](general/PROTOCOL-ENFORCEMENT-FINAL.md)** ⭐ **READ THIS FIRST**
  - Complete guide to Bob's 5-layer protocol system
  - Prevents repeated mistakes
  - Enforces: Query → Verify → State → Execute → Verify → Store
  - **Status**: Production Ready

### Protocol Evolution
- [protocol-enforcement-v3.md](general/protocol-enforcement-v3.md) - Layer 5 addition (Forced Execution)
- [protocol-enforcement-v2.md](general/protocol-enforcement-v2.md) - Layer 4 addition (Memory Compliance)
- [protocol-enforcement.md](general/protocol-enforcement.md) - Original 3-layer system

### Root Cause Analysis
- [root-cause-self-analysis.md](root-cause-self-analysis.md) - Why errors occurred despite having knowledge
- [elefante-reinforcement-strategy.md](elefante-reinforcement-strategy.md) - Strategy for using Elefante effectively

### Temporal Decay Feature
- [temporal-decay-issues.md](temporal-decay-issues.md) - Issues found during implementation

## 📂 By Category

### Dashboard Issues
- [dashboard-build-failure-2025-11-28.md](dashboard/dashboard-build-failure-2025-11-28.md)
- [dashboard-postmortem.md](dashboard/dashboard-postmortem.md)

### Database Issues
- **[kuzu-reserved-words-issue.md](kuzu-reserved-words-issue.md)** ⭐ **CRITICAL** - Kuzu SQL/Cypher hybrid anomaly
- [database-corruption-2025-12-02.md](database/database-corruption-2025-12-02.md)
- [duplicate-entity-analysis.md](database/duplicate-entity-analysis.md)
- [kuzu-critical-discovery.md](database/kuzu-critical-discovery.md)
- [kuzu-lock-analysis.md](database/kuzu-lock-analysis.md)

### General Debugging
- [critical-analysis.md](general/critical-analysis.md)
- [current-status.md](general/current-status.md)
- [debug-handoff.md](general/debug-handoff.md)
- [dev-journal.md](general/dev-journal.md)
- [diagnosis.md](general/diagnosis.md)
- [fixes-applied.md](general/fixes-applied.md)
- [implementation-plan.md](general/implementation-plan.md)
- [problem-summary.md](general/problem-summary.md)
- [session-summary-2025-12-02.md](general/session-summary-2025-12-02.md)
- [task-roadmap.md](general/task-roadmap.md)
- [troubleshooting.md](general/troubleshooting.md)

### Installation Issues
- [installation-debug-2025-11-27.md](installation/installation-debug-2025-11-27.md)
- [installation-fix.md](installation/installation-fix.md)
- [installation-success-2025-11-27.md](installation/installation-success-2025-11-27.md)
- [never-again-guide.md](installation/never-again-guide.md)
- [root-cause-analysis.md](installation/root-cause-analysis.md)
- [visual-journey.md](installation/visual-journey.md)

### Memory System Issues
- [memory_retrieval_investigation.md](memory/memory_retrieval_investigation.md)

## 🔑 Key Concepts

### The 5-Layer Protocol System

1. **Layer 1**: Protocol Checklist - Reference document
2. **Layer 2**: Verification Triggers - Automatic keywords
3. **Layer 3**: Dual-Memory Protocol - Query conversation + Elefante
4. **Layer 4**: Memory Compliance - Apply retrieved knowledge
5. **Layer 5**: Action Verification - FORCED EXECUTION

### The Three Gaps

1. **Knowledge Gap**: Not having information → Fixed by Elefante
2. **Application Gap**: Not using retrieved information → Fixed by Layer 4
3. **Execution Gap**: Not acting on stated intentions → Fixed by Layer 5

### Critical Rules

1. Never assume - Always verify
2. Never "should" - Always do
3. Never claim done - Always prove
4. Never ask twice - Always check memory
5. Never analyze only - Always execute

## 📊 Documentation Standards

### File Naming
- Use kebab-case: `protocol-enforcement-v3.md`
- Include dates for time-specific docs: `session-summary-2025-12-02.md`
- Use descriptive names: `kuzu-lock-analysis.md` not `issue-1.md`

### Organization
- Group by topic (dashboard, database, general, installation, memory)
- Keep related files together
- Archive outdated docs to `../archive/`

### Content Structure
- Start with executive summary
- Include date and status
- Provide examples (wrong vs right)
- Link to related docs
- End with lessons learned

## 🎓 Learning from Mistakes

### Common Patterns
1. **Claiming done without verification** → Use Layer 2 triggers
2. **Ignoring stored preferences** → Use Layer 4 compliance
3. **Analysis without action** → Use Layer 5 execution
4. **Repeated questions** → Use Layer 3 dual-memory

### Success Metrics
- ✅ Elefante queried before responding
- ✅ Retrieved memories applied
- ✅ Actions executed immediately
- ✅ Success verified with proof
- ✅ New learnings stored

## 🔄 Maintenance

### When to Add New Docs
- New failure pattern discovered
- Protocol enhancement needed
- Major debugging session completed
- Lessons learned from mistakes

### When to Archive
- Doc superseded by newer version
- Issue permanently resolved
- Historical context only

### Review Schedule
- Protocol docs: After every 100 executions
- Issue docs: When issue recurs
- General docs: Quarterly

## 📞 Quick Reference

**Need to understand the protocol?**  
→ Read [PROTOCOL-ENFORCEMENT-FINAL.md](general/PROTOCOL-ENFORCEMENT-FINAL.md)

**Experiencing repeated mistakes?**  
→ Check [root-cause-self-analysis.md](root-cause-self-analysis.md)

**Want to use Elefante effectively?**  
→ Read [elefante-reinforcement-strategy.md](elefante-reinforcement-strategy.md)

**Debugging specific issue?**  
→ Check category subdirectories (dashboard/, database/, etc.)

---

**Last Updated**: 2025-12-04  
**Total Documents**: 30+  
**Status**: Active Development