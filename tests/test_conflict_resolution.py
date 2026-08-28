# ─────────────────────────────────────────────────────────────────────────────
# TEST    : tests/test_conflict_resolution.py
# PROVES  : Smart merge and conflict repair remain deterministic, reversible,
#           authority-gated, scope-safe, and protective of locked memories.
# RUN     : pytest tests/test_conflict_resolution.py -v
# ─────────────────────────────────────────────────────────────────────────────

import pytest

from src.core.conflict_resolution import (
    ConflictResolutionError,
    ResolutionAction,
    plan_conflict_resolution,
    resolve_memory_pair,
)
from src.models.memory import Memory, MemoryMetadata, MemoryStatus, RetentionPolicy


def _memory(content: str, **metadata) -> Memory:
    return Memory(content=content, metadata=MemoryMetadata(**metadata))


class _Store:
    def __init__(self, *memories: Memory, fail_on_replace: int | None = None):
        self.memories = {memory.id: memory.model_copy(deep=True) for memory in memories}
        self.replace_count = 0
        self.fail_on_replace = fail_on_replace

    async def get_memory(self, memory_id):
        memory = self.memories.get(memory_id)
        return memory.model_copy(deep=True) if memory else None

    async def replace_memory(self, memory):
        self.replace_count += 1
        if self.fail_on_replace == self.replace_count:
            return False
        self.memories[memory.id] = memory.model_copy(deep=True)
        return True


def test_equivalent_assertions_auto_plan_a_stable_consolidation():
    older = _memory("The default vector store is SQLite.", tags=["storage"])
    newer = _memory("the DEFAULT vector store is sqlite", tags=["runtime"])

    plan = plan_conflict_resolution(older, newer)

    assert plan.action is ResolutionAction.CONSOLIDATE
    assert plan.winner_memory_id == str(older.id)
    assert plan.loser_memory_id == str(newer.id)
    assert plan.applicable is True


def test_unresolved_conflict_requires_an_authoritative_winner():
    left = _memory("The default vector store is ChromaDB.")
    right = _memory("The default vector store is SQLite.")

    plan = plan_conflict_resolution(left, right)

    assert plan.action is ResolutionAction.BLOCKED
    assert plan.requires_user_winner is True


def test_sole_protected_assertion_is_the_automatic_winner():
    governing = _memory(
        "The feature is enabled.",
        retention_policy=RetentionPolicy.PERMANENT,
    )
    observation = _memory("The feature is disabled.")

    plan = plan_conflict_resolution(governing, observation)

    assert plan.action is ResolutionAction.SUPERSEDE
    assert plan.winner_memory_id == str(governing.id)
    assert plan.loser_memory_id == str(observation.id)


def test_different_scopes_are_never_collapsed():
    left = _memory("The feature is enabled.", scope="project:left")
    right = _memory("The feature is disabled.", scope="project:right")

    plan = plan_conflict_resolution(left, right, winner_memory_id=left.id)

    assert plan.action is ResolutionAction.BLOCKED
    assert "Different declared scopes" in plan.reason


def test_protected_loser_requires_explicit_confirmation():
    left = _memory("The feature is enabled.")
    right = _memory("The feature is disabled.", user_locked=True)

    plan = plan_conflict_resolution(left, right, winner_memory_id=left.id)

    assert plan.action is ResolutionAction.BLOCKED
    assert plan.protected_loser is True


@pytest.mark.asyncio
async def test_dry_run_is_non_mutating_and_apply_archives_loser_recoverably():
    winner = _memory("The default vector store is SQLite.", tags=["storage"])
    loser = _memory("The default vector store is ChromaDB.", tags=["legacy"])
    winner.metadata.conflict_ids = [loser.id]
    loser.metadata.conflict_ids = [winner.id]
    store = _Store(winner, loser)

    dry_run = await resolve_memory_pair(
        store,
        winner.id,
        loser.id,
        winner_memory_id=winner.id,
    )
    assert dry_run.applied is False
    assert store.replace_count == 0

    result = await resolve_memory_pair(
        store,
        winner.id,
        loser.id,
        winner_memory_id=winner.id,
        apply=True,
        invocation_mode="user_directed",
        reason="Current source verifies SQLite as the default.",
    )

    assert result.applied is True
    repaired_winner = store.memories[winner.id]
    repaired_loser = store.memories[loser.id]
    assert repaired_winner.metadata.status == MemoryStatus.VERIFIED.value
    assert repaired_winner.metadata.conflict_ids == []
    assert repaired_loser.metadata.status == MemoryStatus.ARCHIVED.value
    assert repaired_loser.metadata.archived is True
    assert repaired_loser.metadata.superseded_by_id == winner.id
    assert repaired_winner.metadata.custom_metadata["conflict_resolution_history"][-1][
        "reason"
    ].startswith("Current source")


@pytest.mark.asyncio
async def test_apply_requires_user_authority_and_reason():
    left = _memory("The feature is enabled.")
    right = _memory("The feature is disabled.")
    store = _Store(left, right)

    with pytest.raises(ConflictResolutionError, match="user-directed"):
        await resolve_memory_pair(
            store,
            left.id,
            right.id,
            winner_memory_id=left.id,
            apply=True,
            reason="verified",
        )
    with pytest.raises(ConflictResolutionError, match="audit reason"):
        await resolve_memory_pair(
            store,
            left.id,
            right.id,
            winner_memory_id=left.id,
            apply=True,
            invocation_mode="user_directed",
        )


@pytest.mark.asyncio
async def test_second_write_failure_rolls_both_records_back():
    left = _memory("The feature is enabled.")
    right = _memory("The feature is disabled.")
    store = _Store(left, right, fail_on_replace=2)

    with pytest.raises(ConflictResolutionError, match="rolled back"):
        await resolve_memory_pair(
            store,
            left.id,
            right.id,
            winner_memory_id=left.id,
            apply=True,
            invocation_mode="user_directed",
            reason="verified",
        )

    assert store.memories[left.id].metadata.archived is False
    assert store.memories[right.id].metadata.archived is False
    assert store.memories[left.id].metadata.supersedes_id is None
    assert store.memories[right.id].metadata.superseded_by_id is None


def test_unknown_pair_is_blocked_instead_of_force_merged():
    left = _memory("The service stores memory decisions.")
    right = _memory("The service stores graph relationships.")

    plan = plan_conflict_resolution(left, right)

    assert plan.action is ResolutionAction.BLOCKED
    assert plan.assessment == "ABSTAIN"
