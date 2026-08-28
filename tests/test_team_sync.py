"""Contract tests for signed, scope-bound, additive Team Sync."""

from datetime import datetime, timezone
from uuid import UUID

import pytest

from src.collaboration.team_sync import (
    TeamSyncError,
    apply_team_import,
    build_team_import_plan,
    create_signed_bundle,
    verify_signed_bundle,
)
from src.models.memory import Memory, MemoryMetadata


KEY = b"k" * 32


def _memory(
    content: str,
    *,
    scope: str = "project:elefante",
    memory_id=None,
) -> Memory:
    kwargs = {"id": memory_id} if memory_id is not None else {}
    return Memory(content=content, metadata=MemoryMetadata(scope=scope), **kwargs)


def _bundle(*memories: Memory, scope: str = "project:elefante") -> bytes:
    return create_signed_bundle(
        memories,
        source_id="team-device-a",
        scope=scope,
        memory_ids=[memory.id for memory in memories],
        key=KEY,
        exported_at=datetime(2026, 8, 28, tzinfo=timezone.utc),
    )


def test_bundle_is_deterministic_signed_and_contains_no_key():
    memory = _memory("The default vector store is SQLite.")
    first = _bundle(memory)
    second = _bundle(memory)

    assert first == second
    assert KEY not in first
    payload = verify_signed_bundle(first, key=KEY)
    assert payload["count"] == 1
    assert payload["records"][0]["memory"]["id"] == str(memory.id)
    assert "embedding" not in payload["records"][0]["memory"]


def test_signature_and_record_tampering_are_rejected():
    memory = _memory("The default vector store is SQLite.")
    bundle = bytearray(_bundle(memory))
    bundle[-2] = ord("0") if bundle[-2] != ord("0") else ord("1")
    with pytest.raises(TeamSyncError, match="signature|JSON"):
        verify_signed_bundle(bytes(bundle), key=KEY)
    with pytest.raises(TeamSyncError, match="signature"):
        verify_signed_bundle(_bundle(memory), key=b"x" * 32)


def test_export_requires_exact_scope_and_explicit_allowlist():
    memory = _memory("Scoped decision", scope="project:left")
    with pytest.raises(TeamSyncError, match="outside"):
        create_signed_bundle(
            [memory],
            source_id="device",
            scope="project:right",
            memory_ids=[memory.id],
            key=KEY,
        )
    with pytest.raises(TeamSyncError, match="explicitly allow"):
        create_signed_bundle(
            [memory],
            source_id="device",
            scope="project:left",
            memory_ids=[],
            key=KEY,
        )


def test_import_plan_skips_identical_and_withholds_id_and_semantic_conflicts():
    identical = _memory("The default vector store is SQLite.")
    id_conflict = _memory("The feature is enabled.")
    semantic_conflict = _memory("The server listens on port 8000.")
    safe = _memory("Backups are verified before migration.")
    payload = verify_signed_bundle(
        _bundle(identical, id_conflict, semantic_conflict, safe), key=KEY
    )
    changed_same_id = id_conflict.model_copy(deep=True)
    changed_same_id.content = "The feature is disabled."
    existing_port = _memory("The server listens on port 8765.")

    plan = build_team_import_plan(
        payload,
        [identical, changed_same_id, existing_port],
        accepted_scope="project:elefante",
    )

    assert plan.identical_ids == (str(identical.id),)
    assert set(plan.conflicting_ids) == {
        str(id_conflict.id),
        str(semantic_conflict.id),
    }
    assert [memory.id for memory in plan.importable] == [safe.id]
    assert plan.to_dict()["deletes"] == 0
    assert plan.to_dict()["overwrites"] == 0


class _Store:
    def __init__(self, fail=False):
        self.values = {}
        self.fail = fail

    async def add_memory(self, memory):
        if self.fail and self.values:
            raise RuntimeError("write failed")
        self.values[memory.id] = memory

    async def delete_memory(self, memory_id):
        return self.values.pop(memory_id, None) is not None


class _Embeddings:
    async def generate_embeddings_batch(self, texts):
        return [[float(index + 1)] for index, _text in enumerate(texts)]


@pytest.mark.asyncio
async def test_apply_is_user_directed_additive_and_stamps_source():
    first = _memory(
        "First safe memory.",
        memory_id=UUID("00000000-0000-0000-0000-000000000001"),
    )
    second = _memory(
        "Second safe memory.",
        memory_id=UUID("00000000-0000-0000-0000-000000000002"),
    )
    payload = verify_signed_bundle(_bundle(first, second), key=KEY)
    plan = build_team_import_plan(
        payload, [], accepted_scope="project:elefante"
    )
    store = _Store()

    with pytest.raises(TeamSyncError, match="user-directed"):
        await apply_team_import(
            plan,
            store,
            _Embeddings(),
            invocation_mode="workflow_managed",
            confirm_scope="project:elefante",
        )
    imported = await apply_team_import(
        plan,
        store,
        _Embeddings(),
        invocation_mode="user_directed",
        confirm_scope="project:elefante",
    )

    assert imported == (str(first.id), str(second.id))
    assert store.values[first.id].metadata.custom_metadata["team_sync_source"] == {
        "source_id": "team-device-a",
        "scope": "project:elefante",
    }


@pytest.mark.asyncio
async def test_partial_apply_rolls_back():
    first = _memory("First safe memory.")
    second = _memory("Second safe memory.")
    payload = verify_signed_bundle(_bundle(first, second), key=KEY)
    plan = build_team_import_plan(
        payload, [], accepted_scope="project:elefante"
    )
    store = _Store(fail=True)

    with pytest.raises(TeamSyncError, match="rolled back"):
        await apply_team_import(
            plan,
            store,
            _Embeddings(),
            invocation_mode="user_directed",
            confirm_scope="project:elefante",
        )
    assert store.values == {}
