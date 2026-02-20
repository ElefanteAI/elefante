# Requirements v1 — Elefante Session Distiller

[Phase: R | Versions: Rv1 Dv0 Tv0 | Open Questions: 3]

---

## 1. Spec Name & Summary

**Elefante Session Distiller** — An automated pipeline that extracts high-value knowledge (decisions, root causes, preferences, architecture) from ephemeral VS Code Copilot chat sessions and ingests them into Elefante's persistent memory, while discarding noise (debug logs, tool output, npm errors).

---

## 2. Context & Problem

### The Amnesia Tax
Every new LLM session starts from zero. Developers spend ~20% of each session re-explaining context. Chat sessions contain critical decisions and learnings, but they vanish when the session ends. VS Code stores them in SQLite/JSON files, but in a raw, unstructured format that is:
- **Not searchable** semantically.
- **Not classified** by relevance.
- **Not connected** to the knowledge graph.

### The Garbage-In Problem
Raw sessions are 90% noise (debug chatter, tool invocations, npm logs) and 10% signal (decisions, architecture choices, root causes). Blindly ingesting full transcripts into a vector database creates **search pollution** — the signal drowns in noise.

### Market Gap
No existing tool bridges the gap between "ephemeral chat history" and "persistent project intelligence." GitHub Copilot does not persist cross-session context. Cursor's memory is shallow. Windsurf/Cline have no graph-based knowledge structure.

### Prior Art (Internal)
- **Session Extraction Research (Feb 8, 2026)**: Proved that VS Code stores chat sessions in `~/Library/Application Support/Code/User/workspaceStorage/[UUID]/chatSessions/` as `.json` (snapshots) and `.jsonl` (streaming logs). Both formats can be parsed.
- **Elefante MCP Server**: Already provides `elefante-MemoryAdd` with intelligent dedup (REDUNDANT/CONTRADICTORY detection), `elefante-MemorySearch` for retrieval, and `elefante-GraphConnect` for structural relationships.
- **ZLCTP Handoff Protocol**: Manual proof-of-concept that structured context packages enable seamless agent handoffs.

---

## 3. Objectives (SMART)

| # | Objective | Measure | Target |
|---|-----------|---------|--------|
| O1 | Automatically extract knowledge from completed chat sessions | % of sessions processed | 100% of closed sessions |
| O2 | Achieve high signal-to-noise ratio in stored memories | Ratio of distilled insights to raw lines | ≥ 1:50 (1 insight per 50 lines of raw chat) |
| O3 | Zero manual intervention for standard ingestion | User actions required | 0 (fully automatic) |
| O4 | Cross-workspace support | Number of workspaces supported | All workspaces on the machine |
| O5 | LLM-agnostic distillation | Supported distillers | Local (Ollama), API (Kimi, OpenAI, Anthropic) |

---

## 4. Users / Stakeholders

| Role | Need |
|------|------|
| **Solo Developer (Primary)** | Persistent context across sessions without manual work. "I shouldn't have to re-explain my project every time." |
| **Future Agent (Consumer)** | Receives curated, high-score memories via `elefante-MemorySearch` at session start. |
| **Elefante System (Internal)** | Receives properly classified, deduplicated memories with full metadata (memory_type, domain, tags, entities). Behavioral relevance is computed automatically. |

---

## 5. Functional Requirements

| ID | Requirement |
|----|-------------|
| F1 | **Session Discovery**: Scan all VS Code workspace storage folders, identify chat session files (`.json` and `.jsonl`), and map them to their parent workspace via `workspace.json`. |
| F2 | **Session Parsing**: Parse both JSON (snapshot) and JSONL (streaming/incremental) formats into a normalized list of `{user_message, agent_response}` pairs. |
| F3 | **Distillation**: Pass the normalized transcript through an LLM with a structured extraction prompt that outputs only: Decisions, Root Causes, Preferences, Architecture Rules, New Facts. Each output item must include a suggested `memory_type`. The system computes behavioral relevance automatically. |
| F4 | **Dedup-Aware Ingestion**: Store distilled insights via `elefante-MemoryAdd`, leveraging Elefante's existing REDUNDANT/CONTRADICTORY detection. Do not create duplicate memories for the same decision across sessions. |
| F5 | **Raw Archive (Optional)**: Store a file reference to the raw transcript (not the full text) as a low-relevance memory with `memory_type=note` (high decay rate), for forensic retrieval only. |
| F6 | **Session Tracking**: Maintain a lightweight index (`processed_sessions.json`) that records which session UUIDs have already been ingested, to avoid reprocessing. |
| F7 | **CLI Interface**: Provide a command-line tool: `python -m elefante.distiller [--workspace PATH] [--all] [--dry-run]`. |
| F8 | **Distiller Prompt Engineering**: The extraction prompt must be tunable — stored as a separate `.md` or `.txt` file, not hardcoded. |

---

## 6. Non-Functional Requirements

| ID | Category | Requirement |
|----|----------|-------------|
| NF1 | **Performance** | Process a 500-message session in < 30 seconds (excluding LLM API latency). |
| NF2 | **Privacy** | All processing happens locally by default. No data leaves the machine unless the user explicitly configures an API-based distiller. Local Ollama is the default. |
| NF3 | **Portability** | macOS first (VS Code paths). Linux support as stretch goal. Windows deferred. |
| NF4 | **Resilience** | If the LLM distiller fails or is unavailable, fall back to storing the raw transcript reference only (F5). Never lose data. |
| NF5 | **Idempotency** | Running the distiller twice on the same session produces zero new memories (via F6 tracking + F4 dedup). |
| NF6 | **Transparency** | Dry-run mode must show exactly what would be stored, without storing anything. |

---

## 7. Out of Scope

- Real-time event interception (hooking into VS Code's internal chat API as messages arrive). The JSONL stream **can** be read mid-session — the distiller captures everything written to disk up to the moment of execution, which effectively provides "live snapshot" capability without needing a VS Code extension hook.
- Ingestion from non-Copilot sources (Cursor, Cline, Windsurf). Future roadmap.
- Team/shared memory sync. Separate spec.
- The VS Code extension UI itself. This spec covers the **backend pipeline** only.

---

## 8. Success Metrics

| KPI | Baseline | Target |
|-----|----------|--------|
| Context re-explanation messages per session | ~3-5 per session | 0-1 per session |
| Time to full context in new session | 2-5 minutes of manual pasting | < 5 seconds (automatic) |
| Unique insights stored per session | 0 (nothing persisted) | 3-8 per session |
| Developer satisfaction ("Does the agent remember?") | Low | High |

---

## 9. Open Questions

| # | Question | Priority | Blocking? |
|---|----------|----------|-----------|
| Q1 | Which local LLM is the default distiller? Ollama with which model (Llama 3, Mistral, Phi-3)? | High | Non-blocking (can default to Ollama + llama3) |
| Q2 | Should the distiller run automatically on VS Code exit, or be triggered manually via CLI? v1 = CLI, v2 = auto-hook. | Med | Non-blocking (CLI first) |
| Q3 | What is the maximum session size (in tokens) before we chunk and summarize incrementally? | Med | Non-blocking (default: 50K tokens → chunk) |

---

**Review Requirements v1. Reply with:**
1. **Approve** to proceed to Design
2. **Edits** (list changes)
3. **Rethink scope**
