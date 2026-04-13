"""
Tests for Passive Autonomous Co-Activation (Hebbian Learning)
"""
from pathlib import Path

import pytest
from src.core.orchestrator import MemoryOrchestrator
from src.core.directive_store import DirectiveStore, SYSTEM_DIRECTIVE_DEFINITIONS
from src.core.orchestrator import SYSTEM_SPECIFICATIONS
from src.models.query import QueryMode

@pytest.mark.asyncio
async def test_record_coactivation_boosts_score(isolated_orchestrator: MemoryOrchestrator):
    # 1. Add two distinct memories that don't semantically match each other
    m1 = await isolated_orchestrator.add_memory(
        content="The main production database runs on Postgres 15 at db.internal.prod.",
        memory_type="decision",
    )
    
    m2 = await isolated_orchestrator.add_memory(
        content="All project JWT tokens must be signed with RS256 algorithm.",
        memory_type="preference",
    )

    m1_id = str(m1.id)
    m2_id = str(m2.id)

    # 2. Search for "database" without any co-activation history
    results_before = await isolated_orchestrator.search_memories(
        query="production database credentials",
        mode=QueryMode.SEMANTIC,
        limit=5
    )
    
    m2_score_before = 0.0
    for r in results_before:
        if str(r.memory.id) == m2_id:
            m2_score_before = r.score
            if hasattr(r, 'explanation') and r.explanation:
                coact_val = 0.0
                for signal in r.explanation.get('signals', []):
                    if signal.get('name') == 'coactivation':
                        coact_val = signal.get('score', 0.0)
                assert coact_val == 0.0

    # 3. Simulate an MCP session where both were retrieved together
    await isolated_orchestrator.record_coactivation([m1_id, m2_id])

    # 4. Search again, but this time simulate that we just retrieved m1 in this session
    # We pass recent_memory_ids=[m1_id]. We expect m2 to receive a co-activation boost.
    results_after = await isolated_orchestrator.search_memories(
        query="production database credentials",
        mode=QueryMode.SEMANTIC,
        limit=5,
        recent_memory_ids=[m1_id]
    )

    m2_found_after = False
    m2_score_after = 0.0
    for r in results_after:
        if str(r.memory.id) == m2_id:
            m2_found_after = True
            m2_score_after = r.score
            if hasattr(r, 'explanation') and r.explanation:
                coact_val = 0.0
                for signal in r.explanation.get('signals', []):
                    if signal.get('name') == 'coactivation':
                        coact_val = signal.get('score', 0.0)
                assert coact_val > 0.0

    assert m2_score_after > m2_score_before, f"Expected boosted score > {m2_score_before}, got {m2_score_after}"


def test_directive_store_includes_system_sdd_baseline(tmp_path):
    store = DirectiveStore(path=tmp_path / "directives.json")

    directives = store.list_all()
    sdd_gate_count = sum(1 for directive in directives if directive["content"].startswith("SDD "))

    assert store.count() >= len(SYSTEM_DIRECTIVE_DEFINITIONS)
    assert sdd_gate_count >= 5
    assert any("STDOUT" in directive["content"] for directive in directives)


@pytest.mark.asyncio
async def test_orchestrator_bootstraps_system_specifications(isolated_orchestrator: MemoryOrchestrator):
    first = await isolated_orchestrator.ensure_system_baseline()
    second = await isolated_orchestrator.ensure_system_baseline()

    assert first["success"] is True
    assert second["success"] is True
    assert second["created"] == 0

    for specification in SYSTEM_SPECIFICATIONS:
        memory = await isolated_orchestrator.vector_store.find_by_title(specification["title"])
        assert memory is not None, f"Missing specification memory: {specification['title']}"
        memory_type = memory.metadata.memory_type.value if hasattr(memory.metadata.memory_type, "value") else str(memory.metadata.memory_type)
        assert memory_type == "specification"


def test_mcp_server_does_not_fire_and_forget_coactivation():
    server_path = Path(__file__).resolve().parents[1] / "src" / "mcp" / "server.py"
    source = server_path.read_text(encoding="utf-8")

    assert "asyncio.create_task(orchestrator.record_coactivation" not in source
    assert source.count("await orchestrator.record_coactivation") >= 2


def test_mcp_server_injects_entrypoint_protocol_on_success_and_error():
    server_path = Path(__file__).resolve().parents[1] / "src" / "mcp" / "server.py"
    source = server_path.read_text(encoding="utf-8")
    directive_source = (Path(__file__).resolve().parents[1] / "src" / "core" / "directive_store.py").read_text(encoding="utf-8")

    assert 'ENTRYPOINT_SEQUENCE_READ_THIS_FIRST' in source
    assert 'result = self._inject_entrypoint_protocol(result)' in source
    assert 'error_payload = self._inject_entrypoint_protocol(error_payload)' in source
    assert 'docs/debug/README.md' in source
    assert 'tests/README.md' in source
    assert 'ENTRYPOINT_SEQUENCE_READ_THIS_FIRST' in directive_source
