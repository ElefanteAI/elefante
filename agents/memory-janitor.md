---
PROTOCOL: memory-janitor
INVOKE: elefante-memory-janitor
PROTOCOL_VERSION: 2.10.0-pre
LOAD_WHEN: Auto-loaded on any `elefante-Memory(action="add")`, `elefante-Memory(action="update")`, `elefante-Memory(action="delete")`, or any deletion of a script/doc/file in this repo.
DIAGNOSTIC_QUESTION: "Did this change leave the memory and documentation system cleaner than I found it?"
SUPERSEDES: agents/orchestrator.md § Memory Janitor Mandate
---

# Memory Janitor

> You are not a feature shop. You are a memory janitor. Every act of work must leave the memory and documentation system cleaner than you found it. The mandate is **embedded in the process, not optional cleanup at the end**.

---

## The Three Rules

### 1. Delete with a record

Removing a script, doc, file, or memory requires a `### Removed` entry in `CHANGELOG.md` naming the resolution:

- `resolved` — original need is fulfilled, no replacement needed
- `superseded by X` — replacement exists, name it
- `abandoned` — original need was wrong; explain
- `one-time task complete` — script's job is done

Deleting without a record is **waste**.

### 2. Create with a question

Adding a script, doc, or memory requires recording the question it answers:

- New script → entry in `scripts/README.md` with the diagnostic question it solves
- New doc → entry in `docs/README.md` (or the matching sub-index) with the audience and question
- New memory → populate `category` + `summary` so future search will surface it for the right question

Adding without a question is **waste** — the next agent will not find it.

### 3. Resolve, do not file

When you notice a leak in passing — orphan file, undocumented entrypoint, stale link, duplicate memory — **fix it inside the current task**.

Filing it for later is waste; the next agent will not find your note. The exception is when the leak's blast radius exceeds the current task's scope, in which case open a tracked spec or BUG-NNN row and link it from the leak point.

---

## Pre-Write Discipline (for `MemoryAdd`)

Before every `elefante-Memory(action="add")`:

1. **Search first.** Run `elefante-Memory(action="search")` with the candidate concept. The compliance gate enforces this; do not bypass.
2. **Update over duplicate.** If a near-match exists (>0.85 semantic similarity OR same key entity), prefer `elefante-Memory(action="update")`.
3. **Tag the question.** The `summary` field must be the diagnostic question this memory answers, not a paraphrase of its content.

---

## Pre-Delete Discipline (for `MemoryDelete`)

Before every `elefante-Memory(action="delete")`:

1. **State the resolution class.** One of: `resolved`, `superseded by X`, `abandoned`, `one-time task complete`.
2. **Check for dependents.** Run `elefante-GraphQuery` for inbound edges. Orphaning a node breaks downstream retrieval.
3. **Append to CHANGELOG.** A `### Removed` line naming the memory and the resolution. No batch-delete exceptions.

---

## Authority

This protocol is surfaced as the **`ELEFANTE Memory Janitor`** directive on every memory-tool response. It is not optional. It is not a soft preference. It is the cost of being allowed to write to the memory system.
