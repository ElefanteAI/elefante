#!/usr/bin/env python3
"""Stage and verify a ChromaDB-to-SQLite vector-store migration.

The default is a non-persistent dry run: ChromaDB is copied into a temporary
snapshot, converted there, and checked for record, metadata, embedding, and
search parity. ``--apply`` still leaves ChromaDB and Elefante configuration
untouched; it only publishes the verified SQLite directory after an exact
backup match and explicit stopped-process confirmation.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.lifecycle.restore_elefante_data import read_verified_manifest  # noqa: E402
from src.core.sqlite_vector_store import SQLiteVectorStore  # noqa: E402
from src.core.vector_store import VectorStore  # noqa: E402
from src.models.memory import Memory  # noqa: E402


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _directory_manifest(directory: Path) -> dict[str, dict[str, Any]]:
    """Fingerprint regular files and reject links that could escape a snapshot."""
    manifest: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Refusing symlinked vector-store path: {path}")
        if path.is_file():
            manifest[path.relative_to(directory).as_posix()] = {
                "size": path.stat().st_size,
                "sha256": _sha256(path),
            }
    return manifest


def _verify_backup(archive_path: Path, source_manifest: dict[str, dict[str, Any]], prefix: str) -> None:
    manifest = read_verified_manifest(archive_path)
    normalized_prefix = prefix.strip("/")
    if not normalized_prefix:
        raise ValueError("Backup prefix must name the ChromaDB directory in the archive")
    prefix_with_separator = f"{normalized_prefix}/"
    archived = {
        entry["path"][len(prefix_with_separator):]: {
            "size": entry.get("size"),
            "sha256": entry.get("sha256"),
        }
        for entry in manifest["files"]
        if entry.get("path", "").startswith(prefix_with_separator)
    }
    if archived != source_manifest:
        raise ValueError("Verified backup does not exactly match the current ChromaDB files")


def _copy_stable_snapshot(source: Path, destination: Path) -> dict[str, dict[str, Any]]:
    before = _directory_manifest(source)
    if not before:
        raise ValueError(f"ChromaDB source contains no files: {source}")
    shutil.copytree(source, destination)
    after = _directory_manifest(source)
    copied = _directory_manifest(destination)
    if before != after or before != copied:
        raise RuntimeError("ChromaDB changed while its snapshot was being copied; stop Elefante and retry")
    return before


def _memory_contract(memory: Memory) -> dict[str, Any]:
    record = memory.to_dict()
    record["embedding"] = None
    return record


def _read_chroma_snapshot(snapshot: Path, collection_name: str) -> tuple[list[Memory], VectorStore]:
    store = VectorStore(collection_name=collection_name, persist_directory=str(snapshot))
    store._initialize_client()
    collection = store._collection
    if collection is None:
        raise RuntimeError("ChromaDB collection did not initialize")
    result = collection.get(include=["documents", "metadatas", "embeddings"])
    ids = result.get("ids") or []
    documents = result.get("documents") or []
    metadatas = result.get("metadatas") or []
    embeddings = result.get("embeddings")
    if embeddings is None or len(ids) != len(documents) or len(ids) != len(metadatas) or len(ids) != len(embeddings):
        raise ValueError("ChromaDB collection returned an incomplete record set")

    memories: list[Memory] = []
    for memory_id, content, metadata, embedding in zip(ids, documents, metadatas, embeddings):
        memory = store._reconstruct_memory(memory_id, content, metadata)
        vector = np.asarray(embedding, dtype=np.float32)
        if vector.ndim != 1 or vector.size == 0 or not np.isfinite(vector).all():
            raise ValueError(f"Memory {memory_id} has an invalid embedding")
        memory.embedding = vector.astype(float).tolist()
        memories.append(memory)
    memories.sort(key=lambda memory: str(memory.id))
    return memories, store


def _close_chroma_snapshot(store: VectorStore) -> None:
    """Stop and unregister only this migration's isolated Chroma system."""
    client = store._client
    if client is None:
        return
    identifier = getattr(client, "_identifier", None)
    system = client._system
    system.stop()
    systems = getattr(type(client), "_identifier_to_system", None)
    if isinstance(systems, dict) and systems.get(identifier) is system:
        systems.pop(identifier, None)
    store._collection = None
    store._client = None


def _publish_sqlite_directory(staged: Path, destination: Path, collection_name: str) -> None:
    """Reserve a new destination and publish the closed SQLite database without replacement."""
    expected_database = staged / f"{collection_name}.sqlite3"
    staged_files = [path for path in staged.iterdir() if path.is_file()]
    if staged_files != [expected_database]:
        raise RuntimeError("Staged SQLite output contains unexpected files")
    destination.mkdir(parents=False, exist_ok=False)
    try:
        expected_database.rename(destination / expected_database.name)
        staged.rmdir()
    except Exception:
        # Never remove a non-empty destination: an external writer may have
        # claimed it after reservation. Configuration still points at Chroma.
        try:
            destination.rmdir()
        except OSError:
            pass
        raise


class _ProbeEmbeddings:
    def __init__(self, probes: dict[str, list[float]]):
        self._probes = probes

    async def generate_embedding(self, text: str) -> list[float]:
        return self._probes[text.splitlines()[0]]

    def get_embedding_dimension(self) -> int:
        return len(next(iter(self._probes.values()))) if self._probes else 0


async def _write_and_verify(
    memories: list[Memory],
    source_collection: Any,
    destination: Path,
    collection_name: str,
    *,
    probe_count: int,
    minimum_search_overlap: float,
) -> dict[str, Any]:
    if not memories:
        raise ValueError("ChromaDB collection is empty")
    store = SQLiteVectorStore(collection_name=collection_name, persist_directory=str(destination))
    try:
        for memory in memories:
            await store.add_memory(memory.model_copy(deep=True))

        recovered = await store.get_all(limit=len(memories) + 1)
        source_by_id = {str(memory.id): memory for memory in memories}
        target_by_id = {str(memory.id): memory for memory in recovered}
        if set(source_by_id) != set(target_by_id):
            raise ValueError("SQLite UUID set does not match ChromaDB")

        dimensions: set[int] = set()
        for memory_id, source_memory in source_by_id.items():
            target_memory = target_by_id[memory_id]
            if _memory_contract(source_memory) != _memory_contract(target_memory):
                raise ValueError(f"SQLite memory JSON differs for {memory_id}")
            source_vector = np.asarray(source_memory.embedding, dtype=np.float32)
            target_vector = np.asarray(target_memory.embedding, dtype=np.float32)
            dimensions.add(int(source_vector.size))
            if source_vector.shape != target_vector.shape or not np.array_equal(source_vector, target_vector):
                raise ValueError(f"SQLite embedding differs for {memory_id}")

        selected = memories if probe_count >= len(memories) else [
            memories[index]
            for index in np.linspace(0, len(memories) - 1, num=max(1, probe_count), dtype=int)
        ]
        probes = {f"probe:{memory.id}": list(memory.embedding or []) for memory in selected}
        store._embedding_service = _ProbeEmbeddings(probes)
        overlaps: list[float] = []
        result_limit = min(10, len(memories))
        for probe, embedding in probes.items():
            source_result = source_collection.query(
                query_embeddings=[embedding],
                n_results=result_limit,
                include=["distances"],
            )
            source_ids = source_result.get("ids", [[]])[0]
            target_result = await store.search(
                probe,
                limit=result_limit,
                min_similarity=0.0,
                apply_temporal_decay=False,
            )
            target_ids = [str(result.memory.id) for result in target_result]
            overlaps.append(len(set(source_ids) & set(target_ids)) / result_limit)
        lowest_overlap = min(overlaps)
        if lowest_overlap < minimum_search_overlap:
            raise ValueError(
                f"Search overlap {lowest_overlap:.3f} is below required {minimum_search_overlap:.3f}"
            )
        return {
            "records": len(memories),
            "uuid_sets_equal": True,
            "memory_json_equal": True,
            "embeddings_equal": True,
            "embedding_dimensions": sorted(dimensions),
            "search_probes": len(overlaps),
            "lowest_search_overlap": round(lowest_overlap, 6),
            "mean_search_overlap": round(sum(overlaps) / len(overlaps), 6),
        }
    finally:
        store.close()


async def migrate_chroma_to_sqlite(
    source: Path,
    destination: Path,
    *,
    collection_name: str = "memories",
    apply: bool = False,
    stopped_confirmation: str = "",
    backup_archive: Path | None = None,
    backup_prefix: str = "chroma",
    probe_count: int = 20,
    minimum_search_overlap: float = 0.8,
    temporary_parent: Path | None = None,
) -> dict[str, Any]:
    """Run a temporary parity proof or publish a verified SQLite directory."""
    source = source.expanduser().resolve()
    destination = destination.expanduser().resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"ChromaDB source directory not found: {source}")
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError("Source and destination must be disjoint directories")
    if destination.exists():
        raise FileExistsError(f"SQLite destination already exists: {destination}")
    if probe_count < 1:
        raise ValueError("Probe count must be at least 1")
    if not 0.0 <= minimum_search_overlap <= 1.0:
        raise ValueError("Minimum search overlap must be between 0 and 1")
    if apply:
        if stopped_confirmation != "STOPPED":
            raise ValueError("--apply requires --confirm-stopped STOPPED")
        if backup_archive is None:
            raise ValueError("--apply requires a verified --backup archive")

    temporary_directory: str | None = None
    if apply:
        if not destination.parent.is_dir():
            raise FileNotFoundError(f"SQLite destination parent does not exist: {destination.parent}")
        temporary_directory = str(destination.parent)
    elif temporary_parent is not None:
        temporary_parent = temporary_parent.expanduser().resolve()
        temporary_parent.mkdir(parents=True, exist_ok=True)
        temporary_directory = str(temporary_parent)
    with tempfile.TemporaryDirectory(
        prefix=".elefante-vector-migration-",
        dir=temporary_directory,
    ) as temporary:
        temporary_root = Path(temporary)
        snapshot = temporary_root / "chroma-snapshot"
        staged_destination = temporary_root / "sqlite"
        source_manifest = _copy_stable_snapshot(source, snapshot)
        if apply:
            assert backup_archive is not None
            _verify_backup(backup_archive.expanduser().resolve(), source_manifest, backup_prefix)
        memories, source_store = _read_chroma_snapshot(snapshot, collection_name)
        try:
            parity = await _write_and_verify(
                memories,
                source_store._collection,
                staged_destination,
                collection_name,
                probe_count=probe_count,
                minimum_search_overlap=minimum_search_overlap,
            )
        finally:
            _close_chroma_snapshot(source_store)
        if _directory_manifest(source) != source_manifest:
            raise RuntimeError("ChromaDB changed during migration verification; no output was published")
        if apply:
            _publish_sqlite_directory(staged_destination, destination, collection_name)
        return {
            "mode": "apply" if apply else "dry-run",
            "source": str(source),
            "destination": str(destination),
            "collection": collection_name,
            **parity,
            "backup_verified": apply,
            "source_unchanged": True,
            "configuration_changed": False,
            "applied": apply,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(Path.home() / ".elefante/data/chroma"))
    parser.add_argument("--destination", default=str(Path.home() / ".elefante/data/vector"))
    parser.add_argument("--collection", default="memories")
    parser.add_argument("--probe-count", type=int, default=20)
    parser.add_argument("--minimum-search-overlap", type=float, default=0.8)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--backup-prefix", default="chroma")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-stopped", default="")
    args = parser.parse_args(argv)
    try:
        report = asyncio.run(
            migrate_chroma_to_sqlite(
                Path(args.source),
                Path(args.destination),
                collection_name=args.collection,
                apply=args.apply,
                stopped_confirmation=args.confirm_stopped,
                backup_archive=args.backup,
                backup_prefix=args.backup_prefix,
                probe_count=args.probe_count,
                minimum_search_overlap=args.minimum_search_overlap,
            )
        )
    except (FileNotFoundError, FileExistsError, RuntimeError, ValueError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, sort_keys=True))
        return 1
    print(json.dumps({"ok": True, **report}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
