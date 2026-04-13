# Elefante Session Distiller — Design Specification (Dv2)

[Phase: D | Version: Dv2 | Supersedes: Dv1]

---

## 1. What Changed from v1

| Area | v1 (Bad) | v2 (Fixed) |
|------|----------|------------|
| **Parser output** | `List[Dict]` — raw VS Code JSON leaked everywhere | `ChatSession` → `ChatTurn` → `ResponseChunk` — fully typed end-to-end |
| **Response handling** | Only `text`, `markdown`, `thinking` | All 8 response kinds: text, markdown, thinking, codeBlock, toolInvocation, inlineReference, command, progress |
| **Privacy** | Mentioned in design, zero code | `PrivacyFilter` with 11 regex patterns — API keys, tokens, SSH keys, connection strings, passwords |
| **Idempotency** | None — rerun = duplicate memories | `SessionTracker` with `processed_sessions.json` + content hash change detection |
| **Workspace mapping** | Unknown — file paths only | `workspace.json` resolution → human-readable project names |
| **Error handling** | `except: pass` everywhere | `logging.warning()` with context — no silent failures |
| **Memory safety** | Full file read for keyword search | Buffered 4MB chunk search with overlap handling |
| **CLI** | Nonexistent | `list`, `search`, `distill`, `stats` commands with `--dry-run` |
| **Models used** | Pydantic models existed, never used | Models are the ONLY output — no raw dicts |

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────┐
│                    CLI (__main__.py)                 │
│   list │ search │ distill │ stats                   │
└────┬───────┬────────┬──────────┬────────────────────┘
     │       │        │          │
     ▼       │        ▼          ▼
┌─────────┐  │  ┌──────────┐  ┌──────────┐
│ Scanner │  │  │  Parser   │  │ Tracker  │
│ (find)  │──┘  │ (parse)  │  │ (dedup)  │
└────┬────┘     └────┬─────┘  └────┬─────┘
     │               │             │
     │               ▼             │
     │         ┌──────────┐        │
     │         │ Privacy  │        │
     │         │ (scrub)  │        │
     │         └────┬─────┘        │
     │              │              │
     │              ▼              │
     │    ┌─────────────────┐      │
     └───►│   ChatSession   │◄─────┘
          │  (typed model)  │
          └────────┬────────┘
                   │
          ┌────────┴────────┐
          │  Elefante Memory │  ← Phase T3 (next)
          │  (store)         │
          └─────────────────┘
```

---

## 3. Module Inventory

| Module | LOC | Responsibility | Status |
|--------|-----|----------------|--------|
| `models.py` | 200 | All typed data structures: `ResponseChunk`, `ChatTurn`, `ChatSession`, `DistilledInsight`, `DistillationResult` | DONE |
| `parser.py` | 170 | JSON/JSONL → `ChatSession`. 3-strategy extraction (dict pattern, list pattern, deep search). | DONE |
| `scanner.py` | 165 | Cross-platform session discovery. Workspace name resolution. Buffered keyword search. File watcher. | DONE |
| `privacy.py` | 100 | 11-pattern regex scrubber. AWS, OpenAI, GitHub, Anthropic, SSH, passwords, connection strings, env secrets, internal IPs. | DONE |
| `tracker.py` | 70 | `processed_sessions.json` management. Content-hash-based change detection for re-processing on update. | DONE |
| `__main__.py` | 170 | CLI: `list`, `search`, `distill` (with `--dry-run`), `stats`. | DONE |

---

## 4. Data Flow (Concrete Example)

```
Input:  ~/.../workspaceStorage/0638fc.../chatSessions/4dec24d1.jsonl
                                │
                ┌───────────────┴───────────────┐
                │ Scanner.list_sessions()       │
                │ → SessionInfo(                │
                │     workspace_name="Chile2026"│
                │     session_id="4dec24d1..."  │
                │     size_bytes=5925KB         │
                │   )                           │
                └───────────────┬───────────────┘
                                │
                ┌───────────────┴───────────────┐
                │ Parser.parse("/path/to.jsonl")│
                │ → ChatSession(                │
                │     turns=[                   │
                │       ChatTurn(               │
                │         user_text="Fix bug..",│
                │         response_chunks=[     │
                │           ResponseChunk(      │
                │             kind=MARKDOWN,    │
                │             value="Here..."   │
                │           ),                  │
                │           ResponseChunk(      │
                │             kind=CODE_BLOCK,  │
                │             value="def fix..",│
                │             language="python" │
                │           ),                  │
                │         ]                     │
                │       ),                      │
                │     ],                        │
                │     content_hash="fd789f09.." │
                │   )                           │
                └───────────────┬───────────────┘
                                │
                ┌───────────────┴───────────────┐
                │ Tracker.is_processed(         │
                │   "4dec24d1", "fd789f09")      │
                │ → False (first run)           │
                └───────────────┬───────────────┘
                                │
                ┌───────────────┴───────────────┐
                │ PrivacyFilter.scrub(text)     │
                │ → "sk-abc..." → [REDACTED]    │
                │ → "password=hunter2" → [RED]  │
                └───────────────┬───────────────┘
                                │
                ┌───────────────┴───────────────┐
                │ session.to_flat_text()        │
                │ → Ready for LLM distillation  │
                │    OR                         │
                │ session.to_markdown()         │
                │ → Ready for human review      │
                └───────────────────────────────┘
```

---

## 5. Profit Architecture

| Tier | Capability | Implementation |
|------|-----------|----------------|
| **Free** | `list`, `search`, `distill --dry-run`, raw markdown export | All current code |
| **Pro** | Auto-distillation via LLM, Knowledge Graph ingestion | `distiller.py` (T3 — next phase) |
| **Pro+** | Cross-project intelligence, Team Sync, Dashboard metrics | Future spec |

The value gate is clear: **Free gives you the data. Pro gives you the insights.**

---

## 6. Verification

```
=== Elefante Session Distiller v2 — Smoke Test ===

[Scanner]  ✓ Scanner init  ✓ Scanner list sessions  ✓ Scanner workspace name resolution
[Parser]   ✓ Parser returns ChatSession  ✓ Parser turns are typed  ✓ Parser content hash deterministic
[Privacy]  ✓ Privacy scrubs API keys  ✓ Privacy preserves clean text  ✓ Privacy catches GitHub tokens
[Tracker]  ✓ Tracker idempotency  ✓ Tracker stats
[Integration]  ✓ Full pipeline: scan→parse→scrub→track

Results: 12/12 passed
```

---

**Status**: VERIFIED — All core modules implemented and tested.
**Next**: Phase T3 — The LLM Distiller Engine (the money maker).
