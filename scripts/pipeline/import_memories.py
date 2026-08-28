#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────
# NAME    : import_memories.py
# PURPOSE : Dry-run-first portable JSON memory import.
# WHEN    : Moving a memory corpus between Elefante installations or storage
#           backends. The source JSON is an analysis export; embeddings are
#           regenerated locally with the active configured model.
# USAGE   : python scripts/pipeline/import_memories.py EXPORT.json
#            python scripts/pipeline/import_memories.py EXPORT.json --apply \
#              --confirm-stopped STOPPED
# NOTES   : This is additive only. Existing IDs are rejected, and a verified
#           binary backup is required before writing into a non-empty store.
#           The analysis export has no graph snapshot, so graph topology is not
#           restored by this command.
# ─────────────────────────────────────────────────────────────────────────────
"""Import a portable Elefante JSON memory export safely.

``export_memories.py`` intentionally omits embeddings because they are tied to
the configured local model. This importer validates the complete export before
doing any work, regenerates embeddings in one batch, and only writes after an
explicit ``--apply``. It never replaces an existing memory ID.

The JSON format contains vector-memory records, not a graph snapshot. Memory
IDs and metadata (including related IDs) are preserved, but entities and graph
edges that were not present in the export are outside this command's contract.
Use the checksummed binary backup/restore path when a full durable-data
recovery is required.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Protocol
from uuid import UUID

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.models.memory import Memory  # noqa: E402


MAX_IMPORT_RECORDS = 1_000_000
ALL_MEMORIES_LIMIT = 1_000_000
EXPORT_FORMAT = "elefante-memory-export"
EXPORT_FORMAT_VERSION = 1


class ImportValidationError(ValueError):
    """Raised when an export cannot be imported without ambiguity."""


class ImportApplyError(RuntimeError):
    """Raised when an apply fails, including the rollback result."""


class VectorStoreLike(Protocol):
    async def get_all(self, limit: int = 100, offset: int = 0) -> list[Memory]: ...

    async def add_memory(self, memory: Memory) -> str: ...

    async def get_memory(self, memory_id: UUID) -> Memory | None: ...

    async def delete_memory(self, memory_id: UUID) -> bool: ...


class EmbeddingServiceLike(Protocol):
    async def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]: ...

    def get_embedding_dimension(self) -> int: ...


@dataclass(frozen=True)
class ImportPlan:
    """Validated source records plus the read-only target inspection."""

    source: Path
    memories: tuple[Memory, ...]
    target_count: int
    existing_ids: tuple[str, ...]
    target_store_type: str
    target_store_path: str

    @property
    def can_apply(self) -> bool:
        """Whether additive ID safety checks pass for this target."""
        return not self.existing_ids


@dataclass(frozen=True)
class ImportResult:
    """Apply result with explicit IDs written and rollback status."""

    imported_ids: tuple[str, ...]
    regenerated_embeddings: int
    rolled_back_ids: tuple[str, ...] = ()


def _record_error(index: int, message: str) -> ImportValidationError:
    return ImportValidationError(f"memory record {index}: {message}")


def _load_json(path: Path) -> dict[str, Any]:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"import file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as source:
            payload = json.load(source)
    except UnicodeDecodeError as error:
        raise ImportValidationError("import file is not UTF-8 JSON") from error
    except json.JSONDecodeError as error:
        raise ImportValidationError(f"import file is not valid JSON: {error.msg}") from error
    if not isinstance(payload, dict):
        raise ImportValidationError("import root must be a JSON object")
    if payload.get("format") not in (None, EXPORT_FORMAT):
        raise ImportValidationError(
            f"unsupported import format: {payload.get('format')!r}"
        )
    if payload.get("format_version") not in (None, EXPORT_FORMAT_VERSION):
        raise ImportValidationError(
            f"unsupported import format version: {payload.get('format_version')!r}"
        )
    return payload


def _parse_memory(record: Any, index: int) -> Memory:
    if not isinstance(record, dict):
        raise _record_error(index, "must be a JSON object")
    if not isinstance(record.get("id"), str) or not record["id"].strip():
        raise _record_error(index, "requires a string id so identity can be preserved")
    if not isinstance(record.get("content"), str) or not record["content"].strip():
        raise _record_error(index, "requires non-empty string content")
    if not isinstance(record.get("metadata"), dict):
        raise _record_error(index, "requires a metadata object")

    candidate = copy.deepcopy(record)
    # Embeddings in an ad-hoc input are never trusted: the active local model
    # must regenerate them so the vector space matches the target store.
    candidate.pop("embedding", None)
    candidate["embedding"] = None
    try:
        memory = Memory.from_dict(candidate)
    except Exception as error:
        raise _record_error(index, f"failed schema validation: {error}") from error
    return memory


def load_import_memories(path: Path) -> tuple[Memory, ...]:
    """Load and fully validate the portable JSON record set."""
    path = path.expanduser().resolve()
    payload = _load_json(path)
    records = payload.get("memories")
    if not isinstance(records, list):
        raise ImportValidationError("import object requires a memories array")
    if len(records) > MAX_IMPORT_RECORDS:
        raise ImportValidationError(
            f"import contains {len(records)} records; maximum is {MAX_IMPORT_RECORDS}"
        )
    declared_count = payload.get("count")
    if declared_count is not None and (
        isinstance(declared_count, bool)
        or not isinstance(declared_count, int)
        or declared_count != len(records)
    ):
        raise ImportValidationError(
            f"declared count {declared_count!r} does not match {len(records)} records"
        )

    memories: list[Memory] = []
    seen_ids: set[str] = set()
    for index, record in enumerate(records):
        memory = _parse_memory(record, index)
        memory_id = str(memory.id)
        if memory_id in seen_ids:
            raise _record_error(index, f"duplicate id {memory_id}")
        seen_ids.add(memory_id)
        memories.append(memory)
    return tuple(memories)


async def build_import_plan(path: Path, vector_store: VectorStoreLike) -> ImportPlan:
    """Validate the source and inspect the target without generating or writing."""
    memories = load_import_memories(path)
    existing = await vector_store.get_all(limit=ALL_MEMORIES_LIMIT)
    existing_ids = {str(memory.id) for memory in existing}
    source_ids = {str(memory.id) for memory in memories}
    conflicts = tuple(sorted(source_ids & existing_ids))
    config = getattr(vector_store, "config", None)
    elefante_config = getattr(config, "elefante", None)
    vector_config = getattr(elefante_config, "vector_store", None)
    target_store_type = str(
        getattr(vector_config, "type", vector_store.__class__.__name__)
    )
    target_store_path = str(getattr(vector_store, "persist_directory", "unknown"))
    return ImportPlan(
        source=path.expanduser().resolve(),
        memories=memories,
        target_count=len(existing),
        existing_ids=conflicts,
        target_store_type=target_store_type,
        target_store_path=target_store_path,
    )


def _validate_embeddings(
    embeddings: Iterable[Any],
    expected_count: int,
    expected_dimension: int | None,
) -> list[list[float]]:
    values = list(embeddings)
    if len(values) != expected_count:
        raise ImportApplyError(
            f"embedding service returned {len(values)} vectors for {expected_count} memories"
        )
    normalized: list[list[float]] = []
    for index, vector in enumerate(values):
        if not isinstance(vector, (list, tuple)) or not vector:
            raise ImportApplyError(f"embedding {index} is not a non-empty vector")
        if expected_dimension is not None and len(vector) != expected_dimension:
            raise ImportApplyError(
                f"embedding {index} has dimension {len(vector)}; "
                f"configured model requires {expected_dimension}"
            )
        try:
            numeric = [float(value) for value in vector]
        except (TypeError, ValueError) as error:
            raise ImportApplyError(f"embedding {index} contains a non-numeric value") from error
        if not all(math.isfinite(value) for value in numeric):
            raise ImportApplyError(f"embedding {index} contains a non-finite value")
        normalized.append(numeric)
    return normalized


async def apply_import(
    plan: ImportPlan,
    vector_store: VectorStoreLike,
    embedding_service: EmbeddingServiceLike,
    *,
    backup_verified: bool = False,
    stopped_confirmation: str = "",
) -> ImportResult:
    """Regenerate embeddings and add records, rolling back partial writes."""
    if stopped_confirmation != "STOPPED":
        raise ImportValidationError("--apply requires --confirm-stopped STOPPED")
    if plan.existing_ids:
        raise ImportValidationError(
            "refusing to overwrite existing memory IDs: " + ", ".join(plan.existing_ids)
        )
    if plan.target_count > 0 and not backup_verified:
        raise ImportValidationError(
            "target store is non-empty; provide a verified binary backup before --apply"
        )
    if not plan.memories:
        return ImportResult(imported_ids=(), regenerated_embeddings=0)

    raw_embeddings = await embedding_service.generate_embeddings_batch(
        [memory.content for memory in plan.memories]
    )
    expected_dimension = None
    get_dimension = getattr(embedding_service, "get_embedding_dimension", None)
    if callable(get_dimension):
        dimension = get_dimension()
        if dimension is not None:
            expected_dimension = int(dimension)
    embeddings = _validate_embeddings(raw_embeddings, len(plan.memories), expected_dimension)

    imported_ids: list[str] = []
    try:
        for source_memory, embedding in zip(plan.memories, embeddings):
            memory = source_memory.model_copy(deep=True)
            memory.embedding = embedding
            await vector_store.add_memory(memory)
            imported_ids.append(str(memory.id))
    except Exception as error:
        rolled_back: list[str] = []
        rollback_errors: list[str] = []
        for memory_id in reversed(imported_ids):
            try:
                if await vector_store.delete_memory(UUID(memory_id)):
                    rolled_back.append(memory_id)
            except Exception as rollback_error:
                rollback_errors.append(f"{memory_id}: {rollback_error}")
        detail = f"import failed after {len(imported_ids)} writes: {error}"
        if rollback_errors:
            detail += "; rollback incomplete: " + ", ".join(rollback_errors)
        else:
            detail += f"; rolled back {len(rolled_back)} writes"
        raise ImportApplyError(detail) from error

    return ImportResult(
        imported_ids=tuple(imported_ids),
        regenerated_embeddings=len(embeddings),
    )


def _verified_backup(path: Path) -> dict[str, Any]:
    """Validate a checksummed binary backup without extracting or mutating it."""
    from scripts.lifecycle.restore_elefante_data import read_verified_manifest

    try:
        return read_verified_manifest(path)
    except (FileNotFoundError, OSError, ValueError) as error:
        raise ImportValidationError(f"backup verification failed: {error}") from error


def _print_plan(plan: ImportPlan) -> None:
    print(f"[dry-run] source: {plan.source}")
    print(f"[dry-run] records: {len(plan.memories)}")
    print(f"[dry-run] target records: {plan.target_count}")
    print(f"[dry-run] target store: {plan.target_store_type} ({plan.target_store_path})")
    print("[dry-run] embeddings: regenerate with the configured local model")
    if plan.existing_ids:
        print("[error] existing IDs would be overwritten; no records can be imported:")
        for memory_id in plan.existing_ids:
            print(f"  - {memory_id}")
    else:
        print("[dry-run] identity check: pass (no existing IDs collide)")
    print("[note] graph entities and relationships are not included in analysis JSON")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import a portable Elefante JSON memory export")
    parser.add_argument("source", type=str, help="JSON file produced by export_memories.py")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Regenerate embeddings and write after the dry-run checks",
    )
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Only validate and inspect the target (the default)",
    )
    parser.add_argument(
        "--backup-archive",
        type=str,
        default="",
        help="Verified binary backup required when the target store is non-empty",
    )
    parser.add_argument(
        "--confirm-stopped",
        default="",
        help="Must be exactly STOPPED with --apply",
    )
    args = parser.parse_args(argv)

    vector_store = None
    try:
        from src.core.vector_store import get_vector_store

        vector_store = get_vector_store()
        plan = asyncio.run(build_import_plan(Path(args.source), vector_store))
        _print_plan(plan)
        if not args.apply:
            return 1 if plan.existing_ids else 0

        if plan.existing_ids:
            return 1
        backup_verified = False
        if args.backup_archive:
            manifest = _verified_backup(Path(args.backup_archive))
            backup_verified = True
            print(
                f"[ok] verified backup: {len(manifest.get('files', []))} files "
                f"({manifest.get('created_at', 'unknown')})"
            )
        elif plan.target_count > 0:
            print("[error] --backup-archive is required before writing to a non-empty store")
            return 1

        from src.core.embeddings import get_embedding_service

        embedding_service = get_embedding_service()
        # The standalone command loads the local model before entering asyncio,
        # matching the runtime's cold-start contract.
        embedding_service._load_model()
        result = asyncio.run(
            apply_import(
                plan,
                vector_store,
                embedding_service,
                backup_verified=backup_verified,
                stopped_confirmation=args.confirm_stopped,
            )
        )
        print(
            f"[ok] imported {len(result.imported_ids)} memories; "
            f"regenerated {result.regenerated_embeddings} embeddings"
        )
        print("[note] vector-memory records were imported; graph topology was not restored")
        return 0
    except (FileNotFoundError, ImportValidationError, ImportApplyError, OSError) as error:
        print(f"[error] {error}")
        return 1
    finally:
        if vector_store is not None and hasattr(vector_store, "close"):
            vector_store.close()


if __name__ == "__main__":
    raise SystemExit(main())
