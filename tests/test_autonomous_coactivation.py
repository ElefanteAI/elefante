"""
Tests for Passive Autonomous Co-Activation (Hebbian Learning)
"""
import pytest
from src.core.orchestrator import MemoryOrchestrator
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
