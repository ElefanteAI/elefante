# ─────────────────────────────────────────────────────────────────────────────
# TEST    : tests/test_refinery.py
# VERSION : 2.5.2
# CHANGED : 2026-04-15
# PROVES  : Deterministic refinery plan generation: correct identification of
#           stale, low-score, and superseded memories for pruning.
# RUN     : pytest tests/test_refinery.py -v
# WHEN    : After any change to src/core/refinery.py staleness or scoring logic.
# ─────────────────────────────────────────────────────────────────────────────
from datetime import datetime, timedelta
from src.models.memory import Memory, MemoryMetadata, MemoryStatus


def _mem(
    content: str,
    *,
    title: str | None = None,
    category: str = "general",
    tags: list[str] | None = None,
    score: int = 100,
    access_count: int = 0,
    created_at: datetime | None = None,
    memory_type: str = "conversation",
):
    md = MemoryMetadata(
        category=category,
        tags=tags or [],
        score=score,
        access_count=access_count,
        created_at=created_at or datetime.utcnow(),
        memory_type=memory_type,
    )
    if title:
        md.custom_metadata["title"] = title
    return Memory(id=uuid4(), content=content, metadata=md)


def test_refinery_marks_duplicates_redundant():
    m1 = _mem("LAW 11 - NO EMOJIS", title="Self-Limit-Emojis", score=100, access_count=1)
    m2 = _mem("CRITICAL CONSTRAINT: Do NOT use emojis", title="Self-Limit-Emojis", score=90, access_count=20)

    plan = build_refinery_plan([m1, m2])

    # One winner, one redundant
    redundant_updates = [u for u in plan.updates if u.memory_id in {m1.id, m2.id} and u.updates.get("status") == MemoryStatus.REDUNDANT]
    assert len(redundant_updates) == 1

    assert plan.stats["duplicate_groups"] == 1
    assert plan.stats["redundant_marked"] == 1


def test_refinery_routes_test_namespace():
    m = _mem(
        "Elefante E2E Test Memory 123",
        title="E2E-Test-123",
        category="test",
        tags=["test", "e2e"],
    )

    plan = build_refinery_plan([m])

    # Should add namespace=test to custom metadata
    updates = {u.memory_id: u.updates for u in plan.updates}
    assert m.id in updates
    custom = updates[m.id]["custom_metadata"]
    assert custom["namespace"] == "test"
    assert custom["canonical_key"] == "e2e-test-123"


def test_refinery_canonicalizes_simple_concise_preference():
    m1 = _mem(
        "Preference: Agents should communicate in simple terms and be concise.",
        memory_type="preference",
        score=70,
    )
    m2 = _mem(
        "ALWAYS avoid jargon. Keep it concise. No fluff.",
        memory_type="preference",
        score=100,
    )

    plan = build_refinery_plan([m1, m2])

    assert plan.stats["duplicate_groups"] == 1
    # Both should be assigned the deterministic canonical key.
    updates = {u.memory_id: u.updates for u in plan.updates}
    assert updates[m1.id]["custom_metadata"]["canonical_key"] == "self-pref-communication-simple-concise"
    assert updates[m2.id]["custom_metadata"]["canonical_key"] == "self-pref-communication-simple-concise"
