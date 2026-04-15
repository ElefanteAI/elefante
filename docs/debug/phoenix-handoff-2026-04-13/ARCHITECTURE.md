# Architecture

## High-Level Description

Elefante sits between an MCP-compatible IDE client and two local storage backends. The MCP server in `src/mcp/server.py` exposes 20 tools and 2 prompts. The orchestrator coordinates memory storage, retrieval, graph access, directives, tasks, ETL, and dashboard refresh. ChromaDB handles semantic retrieval, Kuzu holds structured entities and relationships, and the dashboard reads a serialized snapshot instead of talking to live Kuzu directly.

## Core Components

- `src/mcp/server.py`
  Exposes the MCP surface, enforces the compliance gate, injects routing/directives, handles dashboard refresh/open, and delegates to the orchestrator.
- `src/core/orchestrator.py`
  Central decision engine for storage, retrieval, scoring, baseline seeding, and context assembly.
- `src/core/graph_store.py`
  Safe Kuzu boundary for schema-aware writes, query execution, and close-time ownership rules.
- `src/core/vector_store.py`
  ChromaDB persistence and retrieval for semantic memory.
- `src/utils/dashboard_serializer.py`
  Single source of truth for converting memory objects into dashboard nodes and live scores.
- `src/utils/elefante_mode.py`
  Transaction-scoped write locking, mode state, and lock inspection.
- `scripts/verify/verify_e2e_tests.py`
  Authoritative isolated whole-system verifier for the live MCP server.
- `tests/test_developer_routing.py`
  Regression guard for active process docs, tool/prompt counts, and the self-protocol harness contract.
- `docs/debug/README.md`
  Formal bug index and debugging entrypoint for repository work.

## Data Flow

1. An IDE or MCP client sends a tool or prompt request over MCP stdio.
2. `src/mcp/server.py` validates the call, injects routing/directive context, and enforces search-before-write for gated mutations.
3. Write paths acquire `write_lock()` and hand work to the orchestrator.
4. The orchestrator stores semantic memory in ChromaDB and structured edges/nodes in Kuzu.
5. Read paths combine vector matches, graph context, and session context into the response.
6. Dashboard refresh serializes memory and graph state into `dashboard_snapshot.json` under the runtime data directory.
7. The dashboard server serves that snapshot to the browser on port `8000`.

## Dependencies

### Python Runtime

- Python `3.11+`
- `numpy>=1.26.0`
- `pydantic>=2.0.0,<3.0.0`
- `pyyaml>=6.0.0,<7.0.0`
- `chromadb==1.3.5`
- `fastapi==0.124.0`
- `uvicorn==0.38.0`
- `python-multipart>=0.0.9`
- `kuzu==0.11.3`
- `sentence-transformers==2.7.0`
- `mcp==1.23.1`
- `python-dotenv>=1.0.0,<2.0.0`
- `structlog>=24.1.0,<25.0.0`
- `aiosqlite>=0.19.0`
- `regex>=2023.12.25`

### Dev Tooling

- `pytest>=7.4.0,<8.0.0`
- `pytest-asyncio>=0.21.0,<0.22.0`
- `black>=23.0.0,<24.0.0`
- `mypy>=1.5.0,<2.0.0`
- `ruff>=0.1.0,<0.2.0`

### Frontend / Dashboard

- React
- TypeScript
- Vite

## Environment Variables

### Normal runtime / installation

- `ELEFANTE_DATA_DIR`
- `ELEFANTE_LOG_LEVEL`
- `ELEFANTE_CONFIG_PATH`
- `ELEFANTE_MCP_PORT`
- `ELEFANTE_EMBEDDING_MODEL`
- `ELEFANTE_DEVICE`

### Verification / isolation only

- `HOME`
- `USERPROFILE`
- `ELEFANTE_ALLOW_TEST_MEMORIES=1`
- `BROWSER=/usr/bin/true`

### Dangerous maintenance only

- `ELEFANTE_PRIVILEGED=1`

## Setup Commands

```bash
# install
./install.sh

# direct MCP server
.venv/bin/python -m src.mcp.server

# standard app entry
.venv/bin/python -m src.main --mcp

# restart / local health
.venv/bin/python scripts/lifecycle/restart_elefante.py --verify

# authoritative whole-system proof
.venv/bin/python scripts/verify/verify_e2e_tests.py

# full surface including dashboard side effects
.venv/bin/python scripts/verify/verify_e2e_tests.py --with-dashboard-open

# targeted process-doc regression guard
.venv/bin/python -m pytest tests/test_developer_routing.py -v

# targeted graph/session regression guard
.venv/bin/python -m pytest tests/test_memory_persistence.py -k "TestGraphToolContract" -v

# lint / types
ruff check . && mypy src
```

## Immediate Architectural Fact For The Next Session

The current blocker is not in the runtime storage or MCP layers. It is in the developer-process layer: `docs/technical/dev-sdd.md` is stale, and `tests/test_developer_routing.py` does not yet assert the live changelog heading contract.