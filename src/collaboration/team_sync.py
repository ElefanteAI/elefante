"""Signed, scope-bound, conflict-safe Team Sync bundle API.

This is a local transport contract, not a hosted service.  Callers choose the
transport (shared folder, encrypted message, device copy), while Elefante owns
canonical serialization, HMAC authenticity, exact-scope enforcement, dry-run
planning, additive import, embedding regeneration, and rollback.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Protocol
from uuid import UUID

from src.core.conflict_detection import ConflictOutcome, assess_conflict
from src.models.memory import Memory


TEAM_SYNC_FORMAT = "elefante-team-sync"
TEAM_SYNC_VERSION = 1
MAX_TEAM_RECORDS = 10_000
MAX_BUNDLE_BYTES = 50 * 1024 * 1024


class TeamSyncError(ValueError):
    """Raised when a bundle or import request violates the sync contract."""


class _VectorStore(Protocol):
    async def add_memory(self, memory: Memory) -> Any: ...

    async def delete_memory(self, memory_id: UUID) -> bool: ...


class _EmbeddingService(Protocol):
    async def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]: ...


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _record(memory: Memory) -> dict[str, Any]:
    payload = memory.to_dict()
    payload.pop("embedding", None)
    payload.pop("similarity_score", None)
    payload.pop("relevance_score", None)
    return payload


def _record_digest(record: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(record)).hexdigest()


def _scope_values(memory: Memory) -> set[str]:
    metadata = memory.metadata
    return {
        str(value or "").strip()
        for value in (metadata.scope, metadata.project, metadata.workspace)
        if str(value or "").strip()
    }


def _validate_key(key: bytes) -> None:
    if not isinstance(key, bytes) or len(key) < 32:
        raise TeamSyncError("Team Sync HMAC key must contain at least 32 bytes")


def create_signed_bundle(
    memories: Iterable[Memory],
    *,
    source_id: str,
    scope: str,
    memory_ids: Iterable[UUID | str],
    key: bytes,
    exported_at: datetime | None = None,
) -> bytes:
    """Create a canonical signed bundle from an explicit scoped allowlist."""
    _validate_key(key)
    source_id = str(source_id or "").strip()
    scope = str(scope or "").strip()
    if not source_id:
        raise TeamSyncError("source_id is required")
    if not scope:
        raise TeamSyncError("An exact non-empty scope is required")
    allowed_ids = {str(value) for value in memory_ids}
    if not allowed_ids:
        raise TeamSyncError("memory_ids must explicitly allow at least one record")

    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for memory in memories:
        memory_id = str(memory.id)
        if memory_id not in allowed_ids:
            continue
        if memory_id in seen:
            raise TeamSyncError(f"Duplicate memory id in source: {memory_id}")
        seen.add(memory_id)
        if scope not in _scope_values(memory):
            raise TeamSyncError(
                f"Memory {memory_id} is outside the exact export scope {scope!r}"
            )
        record = _record(memory)
        selected.append({"digest": _record_digest(record), "memory": record})

    missing = sorted(allowed_ids - seen)
    if missing:
        raise TeamSyncError("Allowed memory IDs were not found: " + ", ".join(missing))
    if len(selected) > MAX_TEAM_RECORDS:
        raise TeamSyncError(f"Bundle exceeds {MAX_TEAM_RECORDS} records")
    selected.sort(key=lambda item: item["memory"]["id"])
    created = exported_at or datetime.now(timezone.utc)
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    payload = {
        "format": TEAM_SYNC_FORMAT,
        "format_version": TEAM_SYNC_VERSION,
        "source_id": source_id,
        "scope": scope,
        "exported_at": created.astimezone(timezone.utc).isoformat(),
        "count": len(selected),
        "records": selected,
    }
    payload_bytes = _canonical_json(payload)
    envelope = {
        "payload": payload,
        "signature": {
            "algorithm": "HMAC-SHA256",
            "value": hmac.new(key, payload_bytes, hashlib.sha256).hexdigest(),
        },
    }
    bundle = _canonical_json(envelope)
    if len(bundle) > MAX_BUNDLE_BYTES:
        raise TeamSyncError(f"Bundle exceeds {MAX_BUNDLE_BYTES} bytes")
    return bundle


def verify_signed_bundle(bundle: bytes, *, key: bytes) -> dict[str, Any]:
    """Authenticate and fully validate one bundle without mutating state."""
    _validate_key(key)
    if not isinstance(bundle, bytes) or not bundle or len(bundle) > MAX_BUNDLE_BYTES:
        raise TeamSyncError("Team Sync bundle size is invalid")
    try:
        envelope = json.loads(bundle.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TeamSyncError("Team Sync bundle must be UTF-8 JSON") from error
    if not isinstance(envelope, dict):
        raise TeamSyncError("Team Sync envelope must be an object")
    payload = envelope.get("payload")
    signature = envelope.get("signature")
    if not isinstance(payload, dict) or not isinstance(signature, dict):
        raise TeamSyncError("Team Sync envelope is incomplete")
    if signature.get("algorithm") != "HMAC-SHA256":
        raise TeamSyncError("Unsupported Team Sync signature algorithm")
    expected = hmac.new(key, _canonical_json(payload), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(str(signature.get("value") or ""), expected):
        raise TeamSyncError("Team Sync signature verification failed")
    if payload.get("format") != TEAM_SYNC_FORMAT:
        raise TeamSyncError("Unsupported Team Sync format")
    if payload.get("format_version") != TEAM_SYNC_VERSION:
        raise TeamSyncError("Unsupported Team Sync format version")
    if not isinstance(payload.get("scope"), str) or not payload["scope"].strip():
        raise TeamSyncError("Team Sync scope is missing")
    records = payload.get("records")
    if not isinstance(records, list) or len(records) > MAX_TEAM_RECORDS:
        raise TeamSyncError("Team Sync records are invalid")
    if payload.get("count") != len(records):
        raise TeamSyncError("Team Sync record count does not match")
    seen: set[str] = set()
    for index, item in enumerate(records):
        if not isinstance(item, dict) or not isinstance(item.get("memory"), dict):
            raise TeamSyncError(f"Team Sync record {index} is invalid")
        memory = item["memory"]
        memory_id = str(memory.get("id") or "")
        if not memory_id or memory_id in seen:
            raise TeamSyncError(f"Team Sync record {index} has invalid identity")
        seen.add(memory_id)
        if not hmac.compare_digest(str(item.get("digest") or ""), _record_digest(memory)):
            raise TeamSyncError(f"Team Sync record {index} digest failed")
        try:
            parsed = Memory.from_dict(dict(memory))
        except Exception as error:
            raise TeamSyncError(f"Team Sync record {index} failed schema validation") from error
        if payload["scope"] not in _scope_values(parsed):
            raise TeamSyncError(f"Team Sync record {index} is outside the bundle scope")
    return payload


@dataclass(frozen=True)
class TeamSyncImportPlan:
    """Non-mutating additive import decision."""

    source_id: str
    scope: str
    importable: tuple[Memory, ...]
    identical_ids: tuple[str, ...]
    conflicting_ids: tuple[str, ...]
    semantic_conflicts: tuple[tuple[str, str], ...]

    @property
    def can_apply(self) -> bool:
        return bool(self.importable)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "scope": self.scope,
            "importable_ids": [str(memory.id) for memory in self.importable],
            "identical_ids": list(self.identical_ids),
            "conflicting_ids": list(self.conflicting_ids),
            "semantic_conflicts": [list(pair) for pair in self.semantic_conflicts],
            "can_apply": self.can_apply,
            "deletes": 0,
            "overwrites": 0,
        }


def build_team_import_plan(
    payload: Mapping[str, Any],
    existing_memories: Iterable[Memory],
    *,
    accepted_scope: str,
) -> TeamSyncImportPlan:
    """Build an additive plan; ID and semantic conflicts are withheld."""
    scope = str(payload.get("scope") or "").strip()
    if scope != str(accepted_scope or "").strip():
        raise TeamSyncError("accepted_scope must exactly match the signed bundle scope")
    existing = list(existing_memories)
    by_id = {str(memory.id): memory for memory in existing}
    importable: list[Memory] = []
    identical: list[str] = []
    conflicting: list[str] = []
    semantic_conflicts: list[tuple[str, str]] = []
    for item in payload.get("records", []):
        memory = Memory.from_dict(dict(item["memory"]))
        memory.embedding = None
        memory_id = str(memory.id)
        current = by_id.get(memory_id)
        if current is not None:
            if _record_digest(_record(current)) == item["digest"]:
                identical.append(memory_id)
            else:
                conflicting.append(memory_id)
            continue
        conflicts = [
            current_memory
            for current_memory in existing
            if scope in _scope_values(current_memory)
            and assess_conflict(memory.content, current_memory.content).outcome
            is ConflictOutcome.CONFLICT
        ]
        if conflicts:
            conflicting.append(memory_id)
            semantic_conflicts.extend(
                (memory_id, str(current_memory.id)) for current_memory in conflicts
            )
            continue
        importable.append(memory)
    return TeamSyncImportPlan(
        source_id=str(payload.get("source_id") or ""),
        scope=scope,
        importable=tuple(importable),
        identical_ids=tuple(sorted(identical)),
        conflicting_ids=tuple(sorted(conflicting)),
        semantic_conflicts=tuple(sorted(semantic_conflicts)),
    )


async def apply_team_import(
    plan: TeamSyncImportPlan,
    store: _VectorStore,
    embedding_service: _EmbeddingService,
    *,
    invocation_mode: str,
    confirm_scope: str,
) -> tuple[str, ...]:
    """Apply only non-conflicting additions and roll back partial writes."""
    if invocation_mode != "user_directed":
        raise TeamSyncError("Team Sync import must be user-directed")
    if confirm_scope != plan.scope:
        raise TeamSyncError("confirm_scope must exactly match the signed bundle scope")
    if not plan.importable:
        return ()
    embeddings = await embedding_service.generate_embeddings_batch(
        [memory.content for memory in plan.importable]
    )
    if len(embeddings) != len(plan.importable):
        raise TeamSyncError("Embedding service returned the wrong vector count")
    imported: list[UUID] = []
    try:
        for source_memory, embedding in zip(plan.importable, embeddings):
            if not isinstance(embedding, (list, tuple)) or not embedding:
                raise TeamSyncError("Embedding service returned an invalid vector")
            memory = source_memory.model_copy(deep=True)
            memory.embedding = [float(value) for value in embedding]
            custom = dict(memory.metadata.custom_metadata or {})
            custom["team_sync_source"] = {
                "source_id": plan.source_id,
                "scope": plan.scope,
            }
            memory.metadata.custom_metadata = custom
            await store.add_memory(memory)
            imported.append(memory.id)
    except Exception as error:
        rollback_failures: list[str] = []
        for memory_id in reversed(imported):
            try:
                if not await store.delete_memory(memory_id):
                    rollback_failures.append(str(memory_id))
            except Exception:
                rollback_failures.append(str(memory_id))
        if rollback_failures:
            raise TeamSyncError(
                "Team Sync import failed and rollback was incomplete for: "
                + ", ".join(rollback_failures)
            ) from error
        raise TeamSyncError("Team Sync import failed; partial writes were rolled back") from error
    return tuple(str(memory_id) for memory_id in imported)


__all__ = [
    "TEAM_SYNC_FORMAT",
    "TEAM_SYNC_VERSION",
    "TeamSyncError",
    "TeamSyncImportPlan",
    "apply_team_import",
    "build_team_import_plan",
    "create_signed_bundle",
    "verify_signed_bundle",
]
