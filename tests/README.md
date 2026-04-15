# Elefante Test Suite

> **Version:** 2.5.2  
> **Last Updated:** 2026-04-13

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

# Run the shipped self-Elefante protocol
./.venv/bin/python scripts/verify/verify_e2e_tests.py
```

The shipped self-protocol runs against an isolated temporary Elefante home/data directory so it validates the live MCP workflow without polluting the user's durable memory store. By default it verifies 19/20 tools plus both prompts; `--with-dashboard-open` is opt-in because that tool binds fixed port 8000 and is not fully self-contained.

Use the existing tests in this file before writing any ad hoc validation script. If a listed test no longer reflects current behavior, update that test first. Parallel scratch tests are noise unless the existing suite cannot express the failure mode.

---

## Test Files - What Each Does

### CRITICAL (Run on every PR)

| File | What It Tests | Why Critical |
| ---- | ------------- | ------------ |
| [test_memory_persistence.py](test_memory_persistence.py) | Memories persist, current Kuzu path/lock contract stays truthful, GraphStore close barrier works, live MCP shutdown regression stays alive | Without this, users lose memories, get routed through stale Kuzu recovery advice, or crash the server |
| [test_memory_guard.py](test_memory_guard.py) | `[test]` tagged memories blocked by default | Prevents test data polluting real memory DB |
| [test_autonomous_coactivation.py](test_autonomous_coactivation.py) | Co-activation scoring, built-in directive baseline, system specification bootstrap, entrypoint response-contract guard | Prevents regressions in automatic graph maintenance and the embedded directive/specification baseline |

### UNIT TESTS (Run during development)

| File | What It Tests | When to Run |
| ---- | ------------- | ----------- |
| [test_scoring.py](test_scoring.py) | Score normalization math, weight calculation | When changing `src/core/scoring.py` |
| [test_refinery.py](test_refinery.py) | Memory deduplication, canonical key assignment | When changing `src/core/refinery.py` |
| [test_developer_routing.py](test_developer_routing.py) | Active developer-routing paths, debug feedback-loop doc links, self-protocol verifier invariants, current doc references, MCP tool-count guidance | When changing developer process docs, the shipped self-protocol, or built-in SDD/directive text |
| [test_no_emojis.py](test_no_emojis.py) | Emoji policy enforcement across source files | When changing emoji policy |
| [test_v4_concept_overlap.py](test_v4_concept_overlap.py) | Concept overlap detection in memory schema | When changing concept fields |
| [test_dashboard_serializer.py](test_dashboard_serializer.py) | Dashboard node scoring, launch/open safeguards, refresh restart contract, and frontend retry backoff | When changing dashboard serialization, dashboard open flow, or frontend snapshot fetch behavior |
| [test_factory_reset.py](test_factory_reset.py) | Factory reset dry-run, safety gates, backup, idempotency | When changing `scripts/lifecycle/reset_factory.py` |

### INTEGRATION (Run before release)

| File | What It Tests | Prerequisites |
| ---- | ------------- | ------------- |
| [test_integration_smoke.py](test_integration_smoke.py) | Full ADD -> SEARCH cycle with 10 scenarios | Set `ELEFANTE_ALLOW_TEST_MEMORIES=true` |

---

## Directory Structure

```text
tests/
├── README.md                    <- You are here
├── conftest.py                  <- Shared pytest fixtures
├── pytest.ini                   <- pytest configuration
│
├── test_memory_persistence.py   <- CRITICAL
├── test_memory_guard.py         <- CRITICAL
├── test_autonomous_coactivation.py <- CRITICAL
├── test_developer_routing.py    <- Unit test (developer process routing)
├── test_scoring.py              <- Unit test
├── test_refinery.py             <- Unit test
├── test_no_emojis.py            <- Unit test (policy)
├── test_v4_concept_overlap.py   <- Unit test (schema)
├── test_factory_reset.py        <- Unit test (lifecycle)
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

| Scenario | Command |
| -------- | ------- |
| Before any commit | `pytest tests/test_memory_persistence.py tests/test_memory_guard.py -v` |
| Verify Kuzu path + lock contract | `pytest tests/test_memory_persistence.py -k "TestKuzuLockContract" -v` |
| Verify graph/session tool contract | `pytest tests/test_memory_persistence.py -k "TestGraphToolContract" -v` |
| Verify dashboard launch contract | `pytest tests/test_dashboard_serializer.py -k "dashboard" -v` |
| Verify self-protocol harness contract | `pytest tests/test_developer_routing.py -k "TestSelfProtocolContract" -v` |
| Verify the crash regression fix | `pytest tests/test_autonomous_coactivation.py tests/test_memory_persistence.py -v` |
| Verify developer routing references | `pytest tests/test_developer_routing.py -v` |
| Changed scoring/retrieval logic | `pytest tests/test_scoring.py tests/test_refinery.py -v` |
| Changed dashboard serialization | `pytest tests/test_dashboard_serializer.py -v` |
| Verify factory reset safety | `pytest tests/test_factory_reset.py -v` |
| Before release | `pytest tests/ -v` |
| Debugging search issues | `python tests/manual/test_semantic_search.py` |
| Verify MCP server works | `pytest tests/verification/test_mcp_server.py -v` |
| Verify real IDE-like workflow | `./.venv/bin/python scripts/verify/verify_e2e_tests.py` |
| Verify whole-system MCP surface | `./.venv/bin/python scripts/verify/verify_e2e_tests.py --with-dashboard-open` |

---

## Environment Variables

| Variable                       | Purpose                              | Default |
| ------------------------------ | ------------------------------------ | ------- |
| `ELEFANTE_ALLOW_TEST_MEMORIES` | Allow `[test]` tagged memories in DB | `false` |

---
