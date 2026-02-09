# Contributing to Elefante

Thank you for your interest in contributing to Elefante!

## Development Philosophy

**1. Cleanliness**: Leave the repo cleaner than you found it. No temp files, no dead code.
**2. Memory First**: New features must be memory-aware. Use `elefante-grounding` prompt principles.
**3. Behavioral Relevance**: We do not assign "importance" to memories manually. Scores (0-100) are computed by the system based on usage.

## Code Standards

- **Python 3.11+**
- **Type Hints**: Required for all new code.
- **Naming**:
  - Tools: `elefante-PascalCase` (e.g., `elefante-MemoryAdd`)
  - Internal functions: `snake_case`
  - Classes: `PascalCase`

## Project Structure

```
src/
  mcp/          # MCP Server & Tools
  core/         # Logic (Orchestrator, Vector/Graph stores)
  models/       # Pydantic models (v1.10.0 schema)
  dashboard/    # React/Vite app
  etl/          # Topology processing
scripts/        # Maintenance
docs/           # Documentation
tests/          # Pytest suite
```

## Pull Request Etiquette

1. **Title**: Structured (feat:, fix:, docs:, chore:).
2. **Context**: Explain *why*, not just what.
3. **Tests**: Must pass locally.
4. **Docs**: Update `docs/technical/usage.md` if you change tool signatures.
