# Elefante Test Suite

> **Scope:** active developer source declaration 2.12.3; current public release v2.12.3; provenance and channel keep unreleased surfaces separate
> **Last Updated:** 2026-08-26

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

# Run the isolated 100-memory scoring + dashboard sandbox
./.venv/bin/python scripts/verify/verify_scoring_sandbox.py

# Verify the frozen Task Intelligence benchmark contract
./.venv/bin/python scripts/ci/verify_task_intelligence_benchmark.py

# Dry-plan the frozen three-repetition holdout protocol (no model calls)
./.venv/bin/python scripts/ci/run_task_intelligence_evaluation.py

# Report current local paired evidence; incomplete evidence cannot promote
./.venv/bin/python scripts/ci/summarize_task_intelligence_evaluation.py
```

The shipped self-protocol runs against an isolated temporary Elefante home/data directory so it validates the live MCP workflow without polluting the user's durable memory store. It explicitly enables the default-off Task Intelligence development surface and verifies 17/18 development tools plus both prompts; `--with-dashboard-open` is opt-in because that tool binds fixed port 8000 and is not fully self-contained. Normal public v2.12.3 discovery remains 16 tools; the unreleased customer candidate exposes 17 by default because Recall is enabled while Task Intelligence remains default-off.

Use the existing tests in this file before writing any ad hoc validation script. If a listed test no longer reflects current behavior, update that test first. Parallel scratch tests are noise unless the existing suite cannot express the failure mode.

---

## Test Files - What Each Does

### CRITICAL (Run on every PR)

| File | What It Tests | Why Critical |
| ---- | ------------- | ------------ |
| [test_memory_persistence.py](test_memory_persistence.py) | Memories persist, current Kuzu path/lock contract stays truthful, GraphStore close barrier works, live MCP shutdown regression stays alive | Without this, users lose memories, get routed through stale Kuzu recovery advice, or crash the server |
| [test_memory_guard.py](test_memory_guard.py) | `[test]` tagged memories blocked by default | Prevents test data polluting real memory DB |
| [test_autonomous_coactivation.py](test_autonomous_coactivation.py) | Legacy explicit reinforcement behavior, read-only retrieval boundary, built-in directive baseline, system specification bootstrap, entrypoint response-contract guard | Prevents retrieval exposure from mutating memory history and protects the embedded directive/specification baseline |
| [test_task_intelligence_ledger.py](test_task_intelligence_ledger.py) | Session-bound prepare/use/outcome traces, metadata-only storage, idempotency, retraction, shadow default, and pilot kill switch | Prevents observational Task Intelligence data from leaking content, crossing sessions, or silently changing ranking |
| [test_mcp_daemon.py](test_mcp_daemon.py) | Shared-daemon transport, governed answer delivery, authority, source-digest validation, and live runtime contracts | Prevents prompt, search, or opt-in delivery from bypassing governance or current-source checks |

### UNIT TESTS (Run during development)

| File | What It Tests | When to Run |
| ---- | ------------- | ----------- |
| [test_scoring.py](test_scoring.py) | Score normalization math, weight calculation | When changing `src/core/scoring.py` |
| [test_refinery.py](test_refinery.py) | Memory deduplication, canonical key assignment | When changing `src/core/refinery.py` |
| [test_developer_routing.py](test_developer_routing.py) | Active developer-routing paths, debug feedback-loop doc links, self-protocol verifier invariants, current doc references, MCP tool-count guidance | When changing developer process docs, the shipped self-protocol, or built-in SDD/directive text |
| [test_no_emojis.py](test_no_emojis.py) | Emoji policy enforcement across source files | When changing emoji policy |
| [test_v4_concept_overlap.py](test_v4_concept_overlap.py) | Concept overlap detection in memory schema | When changing concept fields |
| [test_dashboard_serializer.py](test_dashboard_serializer.py) | Dashboard node scoring, local-only launch/CORS safeguards, refresh restart contract, frontend retry backoff, and read-only GraphQuery validation | When changing dashboard serialization, dashboard launch/security, GraphQuery access, or frontend snapshot fetch behavior |
| [test_factory_reset.py](test_factory_reset.py) | Factory reset dry-run, safety gates, backup, idempotency | When changing `scripts/lifecycle/reset_factory.py` |
| [test_backup_restore.py](test_backup_restore.py) | Backup manifests, restore preflight, archive safety, integrity, and recoverable replacement | When changing `scripts/lifecycle/backup_elefante_data.py` or `restore_elefante_data.py` |
| [test_installer_bundle.py](test_installer_bundle.py) | Release-bundle bootstrap install root placement, delegated installer command wiring, and archive contents | When changing `scripts/setup/bootstrap_release_bundle.py` or `scripts/ci/build_installer_bundle.py` |
| [test_install_setup.py](test_install_setup.py) | Installer state, daemon service, MCP host adapters, safe uninstall ownership, and seed-memory guard | When changing `scripts/setup/` or `scripts/lifecycle/` installer paths |
| [test_task_intelligence_benchmark.py](test_task_intelligence_benchmark.py) | Historical task provenance, acceptance nodes, split isolation, leakage scanning, metadata-only outcomes, and fail-closed behavioral promotion readiness | When changing the Task Intelligence SDD, benchmark manifest, or evaluator |
| [test_task_intelligence_baseline.py](test_task_intelligence_baseline.py) | Historical snapshot isolation, hidden acceptance boundaries, model-profile outcome isolation, resume behavior, and cumulative token caps | When changing the no-Brief baseline runner |
| [test_task_intelligence.py](test_task_intelligence.py) | V1 reproducibility plus v2 lifecycle/scope/trust, independent relevance, abstention, conflict, provenance, stage, graph, and non-mutation contracts | When changing the Task Brief compiler or service |
| [test_task_intelligence_evaluation.py](test_task_intelligence_evaluation.py) | Pre-fix source isolation, lineage, declared-context preservation, source/stage diversity, sealed-fixture determinism, paired order, contract-bound outcome paths, and prompt leakage boundaries | When changing paired evaluation or retrieval audit |
| [test_task_intelligence_report.py](test_task_intelligence_report.py) | Protocol completeness, profile and task-contract isolation, clustered confidence, resource limits, stale-outcome rejection, and behavioral-contract promotion gate | When changing outcome reporting or promotion thresholds |

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
├── test_backup_restore.py        <- Unit test (backup and restore safety)
├── test_installer_bundle.py     <- Unit test (installer bundle)
├── test_install_setup.py        <- Unit test (install.py)
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
| Changed release pipeline or release-note rendering | `pytest tests/test_release_pipeline.py -v` |
| Changed installer bundle or stable-path bootstrap logic | `pytest tests/test_installer_bundle.py -v` |
| Changed install.py setup logic (dashboard bundling, state tracking, seed memory) | `pytest tests/test_install_setup.py -v` |
| Validate retrieval signals plus dashboard demo coverage in isolation | `./.venv/bin/python scripts/verify/verify_scoring_sandbox.py` |
| Changed dashboard serialization | `pytest tests/test_dashboard_serializer.py -v` |
| Verify factory reset safety | `pytest tests/test_factory_reset.py -v` |
| Verify backup and restore safety | `pytest tests/test_backup_restore.py -v` |
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
