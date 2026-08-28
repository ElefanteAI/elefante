"""Focused fake-backed tests for the local Team Sync CLI."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from scripts.pipeline import team_sync
from src.collaboration.team_sync import create_signed_bundle
from src.models.memory import Memory, MemoryMetadata


KEY = b"team-sync-test-key-0123456789012345"
SCOPE = "project:elefante"
EXPORTED_AT = datetime(2026, 8, 28, tzinfo=timezone.utc)


def _memory(
    content: str, *, memory_id: UUID | None = None, scope: str = SCOPE
) -> Memory:
    return Memory(
        id=memory_id or uuid4(),
        content=content,
        metadata=MemoryMetadata(scope=scope),
    )


def _key_file(tmp_path: Path, *, value: bytes = KEY, mode: int = 0o600) -> Path:
    path = tmp_path / "team-sync.key"
    path.write_bytes(value)
    path.chmod(mode)
    return path


def _write_bundle(path: Path, *memories: Memory, scope: str = SCOPE) -> None:
    path.write_bytes(
        create_signed_bundle(
            memories,
            source_id="source-a",
            scope=scope,
            memory_ids=[memory.id for memory in memories],
            key=KEY,
            exported_at=EXPORTED_AT,
        )
    )


class FakeStore:
    def __init__(
        self,
        memories: list[Memory] | None = None,
        *,
        fail_on_add: int | None = None,
    ) -> None:
        self.memories = {str(memory.id): memory for memory in memories or []}
        self.fail_on_add = fail_on_add
        self.add_calls = 0
        self.delete_calls: list[str] = []
        self.closed = False
        self.config = SimpleNamespace(
            elefante=SimpleNamespace(vector_store=SimpleNamespace(type="fake"))
        )

    async def get_memory(self, memory_id: UUID) -> Memory | None:
        return self.memories.get(str(memory_id))

    async def get_all(self, *, limit: int = 100, offset: int = 0) -> list[Memory]:
        values = list(self.memories.values())
        return values[offset : offset + limit]

    async def add_memory(self, memory: Memory) -> str:
        self.add_calls += 1
        if self.fail_on_add is not None and self.add_calls == self.fail_on_add:
            raise RuntimeError("simulated write failure")
        self.memories[str(memory.id)] = memory
        return str(memory.id)

    async def delete_memory(self, memory_id: UUID) -> bool:
        key = str(memory_id)
        self.delete_calls.append(key)
        return self.memories.pop(key, None) is not None

    def close(self) -> None:
        self.closed = True


class FakeEmbeddingService:
    def __init__(self) -> None:
        self.loaded = False
        self.calls: list[list[str]] = []

    def _load_model(self) -> None:
        self.loaded = True

    async def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[float(index + 1)] for index, _text in enumerate(texts)]


def _run_export(
    monkeypatch: pytest.MonkeyPatch,
    store: FakeStore,
    key_file: Path,
    output: Path,
    *memory_ids: UUID,
) -> int:
    monkeypatch.setattr(team_sync, "get_configured_vector_store", lambda: store)
    args = [
        "export",
        "--scope",
        SCOPE,
        "--source-id",
        "source-a",
        "--key-file",
        str(key_file),
        "--output",
        str(output),
        "--exported-at",
        EXPORTED_AT.isoformat(),
    ]
    for memory_id in memory_ids:
        args.extend(["--memory-id", str(memory_id)])
    return team_sync.main(args)


def test_key_loader_rejects_symlink_insecure_permissions_and_short_keys(tmp_path: Path):
    secure = _key_file(tmp_path)
    assert team_sync.load_hmac_key(secure) == KEY

    insecure = tmp_path / "insecure.key"
    insecure.write_bytes(KEY)
    insecure.chmod(0o644)
    with pytest.raises(team_sync.TeamSyncCliError, match="permissions"):
        team_sync.load_hmac_key(insecure)

    short = _key_file(tmp_path, value=b"too-short")
    with pytest.raises(team_sync.TeamSyncCliError, match="at least 32"):
        team_sync.load_hmac_key(short)

    if os.name == "posix":
        linked = tmp_path / "linked.key"
        linked.symlink_to(secure)
        with pytest.raises(team_sync.TeamSyncCliError, match="symlink"):
            team_sync.load_hmac_key(linked)


def test_export_and_inspect_are_deterministic_and_close_the_store(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    first = _memory("First", memory_id=UUID("00000000-0000-0000-0000-000000000002"))
    second = _memory("Second", memory_id=UUID("00000000-0000-0000-0000-000000000001"))
    key_file = _key_file(tmp_path)
    output = tmp_path / "team-sync.bundle"

    first_store = FakeStore([first, second])
    assert (
        _run_export(monkeypatch, first_store, key_file, output, first.id, second.id)
        == 0
    )
    first_bytes = output.read_bytes()
    first_result = json.loads(capsys.readouterr().out)
    assert first_store.closed
    assert first_result["count"] == 2
    assert first_result["memory_ids"] == [str(second.id), str(first.id)]

    second_store = FakeStore([second, first])
    assert (
        _run_export(monkeypatch, second_store, key_file, output, second.id, first.id)
        == 0
    )
    second_bytes = output.read_bytes()
    assert second_store.closed
    assert first_bytes == second_bytes
    capsys.readouterr()

    inspect_result = team_sync.main(
        ["inspect", str(output), "--key-file", str(key_file)]
    )
    assert inspect_result == 0
    inspected = json.loads(capsys.readouterr().out)
    assert inspected["signature_verified"] is True
    assert inspected["memory_ids"] == [str(second.id), str(first.id)]


def test_import_dry_run_withholds_id_conflict_without_writing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    source = _memory(
        "Incoming value", memory_id=UUID("00000000-0000-0000-0000-000000000010")
    )
    existing = _memory("Current value", memory_id=source.id)
    bundle = tmp_path / "bundle.json"
    _write_bundle(bundle, source)
    store = FakeStore([existing])
    monkeypatch.setattr(team_sync, "get_configured_vector_store", lambda: store)

    result = team_sync.main(
        [
            "import",
            str(bundle),
            "--key-file",
            str(_key_file(tmp_path)),
            "--scope",
            SCOPE,
        ]
    )

    assert result == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["dry_run"] is True
    assert summary["conflicting_count"] == 1
    assert summary["conflicting_ids"] == [str(source.id)]
    assert summary["importable_count"] == 0
    assert store.add_calls == 0
    assert store.closed


def test_apply_requires_exact_scope_and_stopped_confirmations(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    source = _memory("Safe incoming value")
    bundle = tmp_path / "bundle.json"
    _write_bundle(bundle, source)
    key_file = _key_file(tmp_path)
    store = FakeStore()
    embeddings = FakeEmbeddingService()
    monkeypatch.setattr(team_sync, "get_configured_vector_store", lambda: store)
    monkeypatch.setattr(
        team_sync, "get_configured_embedding_service", lambda: embeddings
    )

    missing_stopped = team_sync.main(
        [
            "import",
            str(bundle),
            "--key-file",
            str(key_file),
            "--scope",
            SCOPE,
            "--apply",
            "--confirm-scope",
            SCOPE,
        ]
    )
    assert missing_stopped == 1
    assert store.add_calls == 0
    assert embeddings.calls == []
    capsys.readouterr()

    missing_scope = team_sync.main(
        [
            "import",
            str(bundle),
            "--key-file",
            str(key_file),
            "--scope",
            SCOPE,
            "--apply",
            "--confirm-stopped",
            "STOPPED",
        ]
    )
    assert missing_scope == 1
    assert store.add_calls == 0
    assert embeddings.calls == []
    capsys.readouterr()


def test_apply_verifies_backup_and_delegates_embedding_and_source_stamping(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    source = _memory("Safe incoming value")
    existing = _memory("Unrelated existing value")
    bundle = tmp_path / "bundle.json"
    _write_bundle(bundle, source)
    key_file = _key_file(tmp_path)
    backup = tmp_path / "verified-backup.zip"
    backup.write_bytes(b"fake backup handled by verifier")
    store = FakeStore([existing])
    embeddings = FakeEmbeddingService()
    verified_paths: list[Path] = []
    monkeypatch.setattr(team_sync, "get_configured_vector_store", lambda: store)
    monkeypatch.setattr(
        team_sync, "get_configured_embedding_service", lambda: embeddings
    )
    monkeypatch.setattr(
        team_sync,
        "verify_binary_backup",
        lambda path: verified_paths.append(Path(path)) or {"files": []},
    )

    result = team_sync.main(
        [
            "import",
            str(bundle),
            "--key-file",
            str(key_file),
            "--scope",
            SCOPE,
            "--apply",
            "--confirm-scope",
            SCOPE,
            "--confirm-stopped",
            "STOPPED",
            "--backup-archive",
            str(backup),
        ]
    )

    assert result == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["applied"] is True
    assert summary["backup_verified"] is True
    assert verified_paths == [backup]
    assert embeddings.loaded is True
    assert embeddings.calls == [[source.content]]
    imported = store.memories[str(source.id)]
    assert imported.metadata.custom_metadata["team_sync_source"] == {
        "source_id": "source-a",
        "scope": SCOPE,
    }
    assert imported.embedding == [1.0]
    assert store.closed


def test_apply_rolls_back_partial_writes_through_existing_api(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    first = _memory("First safe incoming value")
    second = _memory("Second safe incoming value")
    bundle = tmp_path / "bundle.json"
    _write_bundle(bundle, first, second)
    key_file = _key_file(tmp_path)
    store = FakeStore(fail_on_add=2)
    embeddings = FakeEmbeddingService()
    monkeypatch.setattr(team_sync, "get_configured_vector_store", lambda: store)
    monkeypatch.setattr(
        team_sync, "get_configured_embedding_service", lambda: embeddings
    )

    result = team_sync.main(
        [
            "import",
            str(bundle),
            "--key-file",
            str(key_file),
            "--scope",
            SCOPE,
            "--apply",
            "--confirm-scope",
            SCOPE,
            "--confirm-stopped",
            "STOPPED",
        ]
    )

    assert result == 1
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "error"
    assert "rolled back" in summary["error"]
    assert store.memories == {}
    expected_first = min((first, second), key=lambda memory: str(memory.id))
    assert store.delete_calls == [str(expected_first.id)]
    expected_order = sorted((first, second), key=lambda memory: str(memory.id))
    assert embeddings.calls == [[memory.content for memory in expected_order]]
    assert store.closed


def test_cli_output_never_contains_hmac_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    secret = b"do-not-print-team-sync-secret-0123456789"
    key_file = _key_file(tmp_path, value=secret)
    memory = _memory("No secret in this output")
    bundle = tmp_path / "bundle.json"
    bundle.write_bytes(
        create_signed_bundle(
            [memory],
            source_id="source-a",
            scope=SCOPE,
            memory_ids=[memory.id],
            key=secret,
            exported_at=EXPORTED_AT,
        )
    )

    assert team_sync.main(["inspect", str(bundle), "--key-file", str(key_file)]) == 0
    captured = capsys.readouterr()
    assert secret.decode() not in captured.out
    assert secret.decode() not in captured.err
    assert json.loads(captured.out)["signature_verified"] is True


def test_inspect_output_is_bounded_to_verified_metadata(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    memory = _memory("Inspect me")
    key_file = _key_file(tmp_path)
    bundle_path = tmp_path / "bundle.json"
    bundle = create_signed_bundle(
        [memory],
        source_id="source-a",
        scope=SCOPE,
        memory_ids=[memory.id],
        key=KEY,
        exported_at=EXPORTED_AT,
    )
    bundle_path.write_bytes(bundle)

    assert (
        team_sync.main(["inspect", str(bundle_path), "--key-file", str(key_file)]) == 0
    )
    output = capsys.readouterr().out
    summary = json.loads(output)
    assert summary["signature_verified"] is True
    assert "Inspect me" not in output
    assert "content" not in summary
