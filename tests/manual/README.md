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
| ------ | ------- | ------------- |
| `test_mcp_live.py` | Tests MCP server JSON-RPC communication | MCP server not running |
| `test_auto_refresh.py` | Tests dashboard auto-refresh | Dashboard running |
| `test_integration_memory_persistence.py` | Tests memory persistence across sessions | Elefante Mode disabled |
| `test_end_to_end.py` | Full MCP session lifecycle test | MCP server not running |
| `test_engine_parser.py` | Tests distiller engine response parsing | None |
| `test_distiller_v2.py` | Distiller v2 smoke test | None |
| `test_tools.py` | Verifies live MCP tool and prompt registration directly from `src/mcp/server.py` | None |
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
