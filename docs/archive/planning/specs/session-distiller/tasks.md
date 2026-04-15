# Elefante Session Distiller — Task List (Phase T v2)

> ⚠️ **ARCHIVED** — Implementation task list, all items completed. Historical record only. For current implementation see `src/modules/distiller/`.

## T1: Infrastructure & Core Pipeline
- [x] **T1.1**: Create module structure `src/modules/distiller/`
- [x] **T1.2**: Define typed models — `ResponseChunk`, `ChatTurn`, `ChatSession`, `DistilledInsight`
- [x] **T1.3**: Build parser — JSON/JSONL → `ChatSession` (3-strategy extraction)
- [x] **T1.4**: Build scanner — cross-platform discovery, workspace name resolution, buffered search
- [x] **T1.5**: Build privacy filter — 11-pattern regex scrubber
- [x] **T1.6**: Build session tracker — `processed_sessions.json` + content-hash change detection
- [x] **T1.7**: Build CLI — `list`, `search`, `distill`, `stats` commands
- [x] **T1.8**: Smoke test — 12/12 passing

## T2: Integration with Elefante Memory
- [x] **T2.1**: Create `ingester.py` — `ChatSession` → `elefante-MemoryAdd` bridge
- [x] **T2.2**: Raw archive storage (memory_type=note with high decay, session reference only)
- [x] **T2.3**: Wire CLI `distill` command to call ingester (`--store` flag)

## T3: The LLM Distiller Engine (Pro Tier)
- [x] **T3.1**: Create tunable extraction prompt (`prompts/extract_signal.md`)
- [x] **T3.2**: Create `engine.py` — `ChatSession.to_flat_text()` → LLM → `DistillationResult`
- [x] **T3.3**: Support multiple LLM backends: Ollama, OpenAI, Anthropic, LM Studio
- [x] **T3.4**: Implement `store_insights()` — memory_type=decision/fact/insight (system-scored)
- [x] **T3.5**: Wire distill command: `--engine ollama|openai|anthropic|lmstudio`

## T4: Live Mode & Polish
- [ ] **T4.1**: Background watcher thread — tail JSONL for near-real-time capture
- [ ] **T4.2**: `distill all --auto` — process all unprocessed sessions in one command
- [ ] **T4.3**: Progress bars and formatted output for CLI

## T5: Profit Features
- [ ] **T5.1**: Team Sync API stub
- [ ] **T5.2**: "Knowledge Gained" dashboard metric
- [ ] **T5.3**: Export to portable format (JSON/Markdown archive)
