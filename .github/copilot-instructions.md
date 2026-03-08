# Elefante Memory System

This repository uses **Elefante**, a persistent memory and behavioral system via MCP.

## One Rule

Before answering questions about user preferences, past decisions, or project conventions: **call `elefante-MemorySearch` first**. Queries must be explicit and standalone (no pronouns).

## Compliance Stamp

After searching, include one stamp in your response:
- `[ELEFANTE] Searched: Found {N} relevant memories`
- `[ELEFANTE] Searched: No relevant memories found`

## Tool Response Contract

Every Elefante MCP tool response contains up to three injected sections. You MUST read and act on all of them:

### `MANDATORY_PROTOCOLS_READ_THIS_FIRST`
Critical protocols and known pitfalls injected into every response. These are non-negotiable rules: check for duplicates before creating memories, read Neural Registers before debugging, do not rely on internal knowledge for project specifics. Context-specific warnings appear for specific tools (e.g., search bias warnings on MemorySearch, graph consistency on GraphConnect).

### `DIRECTIVES`
User-managed, persistent behavioral constraints. These are unconditional rules set by the user (e.g., "never claim success without user confirmation"). They are not suggestions — read and follow them on every turn. Stored separately from memories. Cannot be outcompeted by similarity scores.

### `RELEVANT_CONTEXT`
Auto-surfaced memories relevant to the current operation. Appears when applicable (not on search/system tools). Contains the top 3 most similar memories with similarity scores. This gives you ambient context without requiring an explicit `elefante-MemorySearch` call.

## Developer Etiquette (Native SDD)

Before you ever mark a task or feature implementation as "Complete" or "Done", you MUST read the `docs/technical/developer-etiquette.md` Specification and execute its exact sequence (Delete Leftovers, Update Documentation, and Semantic Versioning). Failure to do so is a violation of the Native SDD framework.
