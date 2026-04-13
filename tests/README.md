# Elefante Test Suite

> **Version:** 2.2.3  
> **Last Updated:** 2026-04-12

## Quick Reference

```bash
# Run all automated tests
pytest tests/ -v

# Run only critical regression tests
pytest tests/test_memory_persistence.py tests/test_memory_guard.py -v

# Run the live MCP regression subset
pytest tests/test_autonomous_coactivation.py tests/test_memory_persistence.py -v

# Run smoke test (takes ~30s, needs DB)
pytest tests/test_integration_smoke.py -v

# Run the shipped MCP end-to-end harness
./.venv/bin/python scripts/verify_e2e_tests.py
```

The shipped E2E harness runs against an isolated temporary Elefante home/data directory so it validates the live MCP workflow without polluting the user's durable memory store.

---

## Test Files - What Each Does

### CRITICAL (Run on every PR)

| File                                                     | What It Tests                                      | Why Critical                                |
| -------------------------------------------------------- | -------------------------------------------------- | ------------------------------------------- |
| [test_memory_persistence.py](test_memory_persistence.py) | Memories persist, GraphStore close barrier works, live MCP shutdown regression stays alive | Without this, users lose all their memories or crash the server |
| [test_memory_guard.py](test_memory_guard.py)             | `[test]` tagged memories blocked by default        | Prevents test data polluting real memory DB |
| [test_autonomous_coactivation.py](test_autonomous_coactivation.py) | Co-activation scoring, built-in directive baseline, system specification bootstrap | Prevents regressions in automatic graph maintenance and SDD baseline |

### UNIT TESTS (Run during development)

| File                                 | What It Tests                                  | When to Run                          |
| ------------------------------------ | ---------------------------------------------- | ------------------------------------ |
| [test_scoring.py](test_scoring.py)   | Score normalization math, weight calculation   | When changing `src/core/scoring.py`  |
| [test_refinery.py](test_refinery.py) | Memory deduplication, canonical key assignment | When changing `src/core/refinery.py` |
| [test_no_emojis.py](test_no_emojis.py) | Emoji policy enforcement across source files | When changing emoji policy |
| [test_v4_concept_overlap.py](test_v4_concept_overlap.py) | Concept overlap detection in memory schema | When changing concept fields |

### INTEGRATION (Run before release)

| File                                                   | What It Tests                              | Prerequisites                           |
| ------------------------------------------------------ | ------------------------------------------ | --------------------------------------- |
| [test_integration_smoke.py](test_integration_smoke.py) | Full ADD -> SEARCH cycle with 10 scenarios | Set `ELEFANTE_ALLOW_TEST_MEMORIES=true` |

---

## Directory Structure

```
tests/
├── README.md                    <- You are here
├── conftest.py                  <- Shared pytest fixtures
├── pytest.ini                   <- pytest configuration
│
├── test_memory_persistence.py   <- CRITICAL
├── test_memory_guard.py         <- CRITICAL
├── test_autonomous_coactivation.py <- CRITICAL
├── test_scoring.py              <- Unit test
├── test_refinery.py             <- Unit test
├── test_no_emojis.py            <- Unit test (policy)
├── test_v4_concept_overlap.py   <- Unit test (schema)
├── test_integration_smoke.py    <- Integration
├── test_end_to_end.py           <- Convenience shim → manual/test_end_to_end.py
│
├── manual/                      <- Require human observation
│   ├── README.md                    <- Instructions for each
│   ├── test_mcp_live.py             <- MCP server JSON-RPC
│   ├── test_end_to_end.py           <- Full session lifecycle
│   └── ...
│
└── verification/                <- CI smoke tests
    └── test_mcp_server.py           <- MCP server starts without errors
```

---

## When to Run What

| Scenario                        | Command                                                                 |
| ------------------------------- | ----------------------------------------------------------------------- |
| Before any commit               | `pytest tests/test_memory_persistence.py tests/test_memory_guard.py -v` |
| Verify the crash regression fix | `pytest tests/test_autonomous_coactivation.py tests/test_memory_persistence.py -v` |
| Changed scoring/retrieval logic | `pytest tests/test_scoring.py tests/test_refinery.py -v`                |
| Before release                  | `pytest tests/ -v`                                                      |
| Debugging search issues         | `python tests/manual/test_semantic_search.py`                           |
| Verify MCP server works         | `python tests/verification/test_mcp_server.py`                          |
| Verify real IDE-like workflow   | `./.venv/bin/python scripts/verify_e2e_tests.py`                |

---

---

## Environment Variables

| Variable                       | Purpose                              | Default |
| ------------------------------ | ------------------------------------ | ------- |
| `ELEFANTE_ALLOW_TEST_MEMORIES` | Allow `[test]` tagged memories in DB | `false` |

---
