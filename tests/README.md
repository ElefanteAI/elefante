# Elefante Test Suite

> **Version:** 1.6.1  
> **Last Updated:** 2025-12-29

## Quick Reference

```bash
# Run all automated tests
pytest tests/ -v

# Run only critical regression tests
pytest tests/test_memory_persistence.py tests/test_memory_guard.py -v

# Run smoke test (takes ~30s, needs DB)
pytest tests/test_integration_smoke.py -v
```

---

## Test Files - What Each Does

### CRITICAL (Run on every PR)

| File | What It Tests | Why Critical |
|------|---------------|--------------|
| [test_memory_persistence.py](test_memory_persistence.py) | Memories written to ChromaDB/Kuzu actually persist | Without this, users lose all their memories |
| [test_memory_guard.py](test_memory_guard.py) | `[test]` tagged memories blocked by default | Prevents test data polluting real memory DB |

### UNIT TESTS (Run during development)

| File | What It Tests | When to Run |
|------|---------------|-------------|
| [test_scoring.py](test_scoring.py) | Score normalization math, weight calculation | When changing `src/core/scoring.py` |
| [test_refinery.py](test_refinery.py) | Memory deduplication, canonical key assignment | When changing `src/core/refinery.py` |

### INTEGRATION (Run before release)

| File | What It Tests | Prerequisites |
|------|---------------|---------------|
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
├── test_scoring.py              <- Unit test
├── test_refinery.py             <- Unit test
├── test_integration_smoke.py    <- Integration
│
├── archive/                     <- Old tests, kept for reference
│   ├── test_compliance_gate.py      ← v1.6 feature (shipped)
│   ├── test_v5_explanation.py       ← v5 retrieval (shipped)
│   ├── test_v5_health.py            ← v5 health analyzer (shipped)
│   ├── test_v5_proactive.py         ← v5 proactive surfacing (shipped)
│   ├── test_trigger_words.py        ← Merged into integration smoke
│   ├── test_semantic_agnostic.py    ← Embedding quality (one-time)
│   └── ... (more historical tests)
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
|----------|---------|
| Before any commit | `pytest tests/test_memory_persistence.py tests/test_memory_guard.py -v` |
| Changed scoring/retrieval logic | `pytest tests/test_scoring.py tests/test_refinery.py -v` |
| Before release | `pytest tests/ -v` |
| Debugging search issues | `python tests/manual/test_semantic_search.py` |
| Verify MCP server works | `python tests/verification/test_mcp_server.py` |

---

## Archive Policy

Tests move to `archive/` when:
- The feature they validate is **shipped and stable** (e.g., v5, compliance gate)
- They were **one-time validation** tests (e.g., embedding quality)
- They're **superseded** by a better test

Archived tests can still run: `pytest tests/archive/ -v`

---

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `ELEFANTE_ALLOW_TEST_MEMORIES` | Allow `[test]` tagged memories in DB | `false` |

---

