# Manual Verification Scripts

These scripts require manual execution and may interact with live databases. They are **excluded from pytest** automatically.

## Why Manual?

These scripts:
- Interact with live production databases
- Require the MCP server to be running
- Need manual observation of results
- Test integration points that can't be isolated

## Scripts

| Script | Purpose | Prerequisites |
|--------|---------|---------------|
| `test_authoritative_mocked.py` | Tests authoritative 5-step pipeline with mocked components | None |
| `test_dedup_live.py` | Tests deduplication against live vector store | Elefante Mode disabled in IDE |
| `test_mcp_live.py` | Tests MCP server JSON-RPC communication | MCP server not running |
| `test_semantic_search.py` | Explores semantic search queries | Live ChromaDB populated |
| `test_title_live.py` | Tests semantic title generation | LLM service available |
| `test_auto_refresh.py` | Tests dashboard auto-refresh | Dashboard running |
| `test_integration_memory_persistence.py` | Tests memory persistence across sessions | Elefante Mode disabled |
| `test_end_to_end.py` | Full MCP session lifecycle test | MCP server not running |
| `test_tools.py` | Verifies tool registration in MCP server | None |
| `verify_m4_compatibility.py` | Verifies M4 Silicon library compatibility | macOS ARM64 |

## Running Scripts

```bash
# Run individual script
python tests/manual/test_end_to_end.py

# Run with write flag (some scripts)
python tests/manual/test_auto_refresh.py --write-test-memory
```

## Important Notes

1. **Database Locks**: Ensure Elefante Mode is disabled in all IDEs before running live tests
2. **Test Memories**: Most scripts set `ELEFANTE_ALLOW_TEST_MEMORIES=1` when needed
3. **Cleanup**: Some scripts may leave test data in databases

---

