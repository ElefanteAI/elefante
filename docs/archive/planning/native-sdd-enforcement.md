# Specification: Native SDD Enforcement Engine (v1.0)

> ⚠️ **ARCHIVED** — SDD enforcement spec, shipped as part of v2.2.x. For current SDD process see [docs/technical/dev-sdd.md](../../technical/dev-sdd.md).

## 1. Overview
The objective is to evolve Elefante from a passive structured memory database into an active **Spec-Driven Development (SDD) runtime engine**. Elefante will natively store technical specifications as high-authority system entities and actively enforce agent compliance via pre-flight MCP injection and rigorous gate checks, entirely eradicating agent drift.

## 2. Technical Requirements
- **Framework:** Existing Elefante Python MCP Server (`mcp` library).
- **Storage:** Leverage existing ChromaDB and Kuzu architectures, but introduce a distinct entity/memory class for `Specification` and `Directive`.
- **Pre-Flight Injection:** The MCP server must be capable of identifying the "Active Specification" for a given workspace and serving it immediately upon client initialization.

## 3. The Enforcement Flow (Three-Phase)

### Phase 1: Storage and Schema (Native Entities)
- **Specification Entity:** Add a new `MemoryType` or `EntityType` specifically for Specifications. These must carry an absolute maximum `authority_score` to guarantee retrieval.
- **Relational Binding:** Specifications must be linked via Kuzu graph edges to the modules or tasks they govern (e.g., `(Spec)-[GOVERNS]->(Task)`).

### Phase 2: Pre-Flight MCP Injection
- When an IDE client connects, Elefante checks if there is an active `Specification` for the current workspace context.
- If an active specification exists, Elefante prepends the `SDD-Anchor` directive into the context, mandating the agent read the formal specification before proceeding.

### Phase 3: The Hard Gate (Runtime Verification)
- Utilizing the JSON format gate: agents must formally output a compliance check block.
- Any tool use (code generation, file editing) attempted by the agent without completing the JSON gate or completing the `elefante-MemorySearch` precondition must result in a system-rejected prompt.

## 4. Pitfall Awareness
- **Context Window Bloat:** Injecting full specifications on every MCP initialization could exhaust context limits. The system must inject the *pointer* or a highly condensed summary, forcing the agent to fetch the full text on demand.
- **Schema Conflicts:** Ensure the new `Specification` type does not break the existing V4 Cognitive Schema (`authority_score` calculations, `surfaces_when` triggers) defined in `src/utils/curation.py`.
